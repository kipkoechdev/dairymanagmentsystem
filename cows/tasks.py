"""
tasks.py — Celery beat tasks for automatic SMS reminders
=========================================================
Use this if your project has Celery + a broker (Redis/RabbitMQ).
If you don't have Celery, use the management command instead (send_due_reminders).

Setup steps:
1. pip install celery redis
2. Add to settings.py:
       CELERY_BROKER_URL = 'redis://localhost:6379/0'
       CELERY_BEAT_SCHEDULE = {
           'send-due-reminders-daily': {
               'task': 'cows.tasks.send_due_reminders_task',
               'schedule': crontab(hour=7, minute=0),  # fires at 7:00 AM every day
           },
       }
3. Run workers:
       celery -A your_project worker --loglevel=info
       celery -A your_project beat   --loglevel=info
"""

from celery import shared_task
from datetime import date

from .models import SMSReminder
from .sms_utils import send_sms_reminder


@shared_task(name='cows.tasks.send_due_reminders_task')
def send_due_reminders_task():
    """
    Celery task: send all pending SMS reminders due today or earlier.
    Scheduled daily via Celery Beat.
    """
    today = date.today()
    due = SMSReminder.objects.filter(status='pending', scheduled_date__lte=today)
    sent, failed = 0, 0
    for reminder in due:
        success, _ = send_sms_reminder(reminder)
        if success:
            sent += 1
        else:
            failed += 1
    return {'sent': sent, 'failed': failed, 'date': str(today)}
