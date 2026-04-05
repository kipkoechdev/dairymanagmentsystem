import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dairy_project.settings')

app = Celery('dairy_project')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()


@app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    # Send pending SMS reminders every day at 7 AM
    sender.add_periodic_task(
        crontab(hour=7, minute=0),
        send_daily_reminders.s(),
        name='Send daily SMS reminders'
    )

    # Check for upcoming events daily at 6 AM
    sender.add_periodic_task(
        crontab(hour=6, minute=0),
        check_upcoming_events.s(),
        name='Check upcoming farm events'
    )


@app.task
def send_daily_reminders():
    """Send all pending SMS reminders scheduled for today or earlier."""
    from cows.sms_utils import send_bulk_reminders
    results = send_bulk_reminders()
    return f"Processed {len(results)} reminders"


@app.task
def check_upcoming_events():
    """Auto-create SMS reminders for events in the next 7 days."""
    from cows.models import Farm, Cow, SMSReminder
    from datetime import date, timedelta

    today = date.today()
    created = 0

    for farm in Farm.objects.all():
        for cow in Cow.objects.filter(farm=farm, is_active=True):
            events = cow.days_to_next_event()
            for event_type, days, event_date in events:
                if 5 <= days <= 7:  # 5-7 days out — create reminder
                    exists = SMSReminder.objects.filter(
                        farm=farm, cow=cow,
                        reminder_type=event_type.lower(),
                        scheduled_date__range=[today, today + timedelta(days=2)]
                    ).exists()
                    if not exists:
                        msg = _build_message(cow, event_type, event_date)
                        SMSReminder.objects.create(
                            farm=farm, cow=cow,
                            reminder_type=event_type.lower(),
                            message=msg,
                            phone_number=farm.phone,
                            scheduled_date=today
                        )
                        created += 1

    return f"Created {created} new reminders"


def _build_message(cow, event_type, event_date):
    from datetime import date
    days = (event_date - date.today()).days
    if event_type == 'Insemination':
        return (f"🐄 DAIRY ALERT [{cow.farm.name}]: {cow.name} ({cow.tag_number}) "
                f"is due for insemination in {days} days on "
                f"{event_date.strftime('%d %b %Y')}. "
                f"Please arrange your AI technician.")
    elif event_type == 'Delivery':
        return (f"🍼 DAIRY ALERT [{cow.farm.name}]: {cow.name} ({cow.tag_number}) "
                f"is expected to calve in {days} days on "
                f"{event_date.strftime('%d %b %Y')}. "
                f"Prepare the calving pen and have your vet on standby.")
    return (f"📅 DAIRY REMINDER [{cow.farm.name}]: "
            f"Check {cow.name} ({cow.tag_number}) — {event_type} in {days} days.")
