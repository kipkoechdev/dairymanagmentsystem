"""
Management command: send_due_reminders
=======================================
Finds all pending SMSReminder records whose scheduled_date is today or earlier
and fires the SMS via send_sms_reminder().

Usage:
    python manage.py send_due_reminders

Schedule this to run once daily using one of:

  1. CRON (Linux/Mac) — add to crontab with `crontab -e`:
       0 7 * * * /path/to/venv/bin/python /path/to/manage.py send_due_reminders >> /var/log/dairy_reminders.log 2>&1

  2. Windows Task Scheduler — create a task that runs:
       python C:\\path\\to\\manage.py send_due_reminders

  3. Celery Beat — see tasks.py for the Celery version.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import date

from cows.models import SMSReminder
from cows.sms_utils import send_sms_reminder


class Command(BaseCommand):
    help = 'Send all pending SMS reminders that are due today or overdue.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview reminders that would be sent without actually sending them.',
        )

    def handle(self, *args, **options):
        today = date.today()
        dry_run = options.get('dry_run', False)

        due_reminders = SMSReminder.objects.filter(
            status='pending',
            scheduled_date__lte=today,
        ).select_related('cow', 'farm')

        total = due_reminders.count()

        if total == 0:
            self.stdout.write(self.style.SUCCESS('No pending reminders due today.'))
            return

        self.stdout.write(f'Found {total} reminder(s) due on or before {today}.')

        if dry_run:
            self.stdout.write(self.style.WARNING('-- DRY RUN: no SMS will be sent --'))
            for r in due_reminders:
                self.stdout.write(
                    f'  [{r.scheduled_date}] {r.cow.name} | {r.reminder_type} | {r.phone_number} | {r.message[:60]}...'
                )
            return

        sent, failed = 0, 0
        for reminder in due_reminders:
            success, msg = send_sms_reminder(reminder)
            if success:
                sent += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f'  ✅ Sent to {reminder.phone_number} — {reminder.cow.name} ({reminder.reminder_type})'
                    )
                )
            else:
                failed += 1
                self.stdout.write(
                    self.style.ERROR(
                        f'  ❌ Failed for {reminder.cow.name} ({reminder.reminder_type}): {msg}'
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(f'\nDone. Sent: {sent} | Failed: {failed}')
        )
