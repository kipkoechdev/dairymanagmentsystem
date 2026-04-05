"""
SMS Reminder utility using Africa's Talking API.
Install: pip install africastalking
"""
from django.conf import settings
from django.utils import timezone


def send_sms_reminder(reminder):
    """
    Send an SMS reminder via Africa's Talking.
    Returns (success: bool, message: str)
    """
    try:
        import africastalking
        africastalking.initialize(
            username=settings.AFRICASTALKING_USERNAME,
            api_key=settings.AFRICASTALKING_API_KEY
        )
        sms = africastalking.SMS
        phone = reminder.phone_number
        if not phone.startswith('+'):
            # Assume Kenya number
            if phone.startswith('0'):
                phone = '+254' + phone[1:]
            else:
                phone = '+254' + phone

        response = sms.send(
            message=reminder.message,
            recipients=[phone],
            sender_id=getattr(settings, 'AFRICASTALKING_SENDER_ID', None)
        )
        reminder.status = 'sent'
        reminder.sent_at = timezone.now()
        reminder.save()
        return True, 'SMS sent successfully'

    except ImportError:
        # africastalking not installed — log as sent in demo mode
        print(f"[DEMO SMS] To: {reminder.phone_number}\nMessage: {reminder.message}")
        reminder.status = 'sent'
        reminder.sent_at = timezone.now()
        reminder.save()
        return True, 'Demo mode: SMS logged to console'

    except Exception as e:
        reminder.status = 'failed'
        reminder.error_message = str(e)
        reminder.save()
        return False, str(e)


def send_bulk_reminders():
    """Called by Celery beat to send pending reminders for today."""
    from .models import SMSReminder
    from datetime import date
    today = date.today()
    pending = SMSReminder.objects.filter(status='pending', scheduled_date__lte=today)
    results = []
    for reminder in pending:
        success, msg = send_sms_reminder(reminder)
        results.append((reminder, success, msg))
    return results
