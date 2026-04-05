from django.conf import settings
from django.utils import timezone
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

def send_notification(reminder):
    """
    Send a WhatsApp via Twilio for a given SMSReminder instance.
    """
    # 1. Guard: skip if no phone number
    if not reminder.phone_number or not reminder.phone_number.strip():
        return False, "No phone number set on this reminder."

    # 2. Normalise phone number to E.164 (+254...)
    phone = _normalise_phone(reminder.phone_number)
    
    # 3. Get Credentials from settings
    # Make sure these are in your settings.py!
    account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', 'AC47178366f2fead69604045b7a4b49a9b')
    auth_token  = getattr(settings, 'TWILIO_AUTH_TOKEN',  '353aec3059954e43ed3f3e6ad5784d24')
    
    # Twilio Sandbox number (replace with your specific one if different)
    from_whatsapp = 'whatsapp:+14155238886' 

    try:
        client = Client(account_sid, auth_token)

        # 4. Create the WhatsApp message
        message = client.messages.create(
            from_=from_whatsapp,
            body=f"🐄 *Salron Dairy Alert*\n{reminder.message}",
            to=f"whatsapp:{phone}"
        )

        # 5. Update reminder status in DB
        reminder.status = 'sent'
        reminder.sent_at = timezone.now()
        reminder.save()
        return True, f'Sent — SID: {message.sid}'
    
    except Exception as e:
        reminder.status = 'failed'
        reminder.error_message = str(e)
        reminder.save()
        return False, str(e)


def _normalise_phone(phone: str) -> str:
    """Convert local Kenyan numbers to E.164 (+254...)."""
    phone = phone.strip().replace(' ', '').replace('-', '')
    if phone.startswith('+'):
        return phone
    if phone.startswith('0'):
        return '+254' + phone[1:]
    if phone.startswith('254'):
        return '+' + phone
    return phone


def send_bulk_due_reminders(farm=None):
    from .models import SMSReminder
    from datetime import date

    qs = SMSReminder.objects.filter(status='pending', scheduled_date__lte=date.today())
    if farm:
        qs = qs.filter(farm=farm)

    sent, failed = 0, 0
    for reminder in qs:
        success, _ = send_notification(reminder)
        if success:
            sent += 1
        else:
            failed += 1
    return sent, failed

# --- DO NOT PUT ANY CODE BELOW THIS LINE THAT IS NOT INSIDE A FUNCTION ---