"""
Management command: python manage.py send_reminders

Sends all pending SMS reminders scheduled for today or earlier.
Can be run manually or via a cron job as an alternative to Celery.

Example cron (daily at 7 AM):
    0 7 * * * cd /path/to/dairy_farm && python manage.py send_reminders >> /var/log/dairy_reminders.log 2>&1
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import date
from cows.models import SMSReminder
from cows.sms_utils import send_sms_reminder


class Command(BaseCommand):
    help = 'Send all pending SMS reminders scheduled for today or earlier'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be sent without actually sending',
        )
        parser.add_argument(
            '--farm-id',
            type=int,
            help='Only send reminders for a specific farm ID',
        )

    def handle(self, *args, **options):
        today = date.today()
        dry_run = options['dry_run']
        farm_id = options.get('farm_id')

        qs = SMSReminder.objects.filter(
            status='pending',
            scheduled_date__lte=today
        ).select_related('cow', 'farm')

        if farm_id:
            qs = qs.filter(farm_id=farm_id)

        total = qs.count()
        self.stdout.write(f"\n{'[DRY RUN] ' if dry_run else ''}Found {total} pending reminder(s) to send\n")
        self.stdout.write("-" * 60)

        sent = 0
        failed = 0

        for reminder in qs:
            cow_name = reminder.cow.name if reminder.cow else "Farm-wide"
            self.stdout.write(
                f"\n→ {reminder.get_reminder_type_display()} | {cow_name} | "
                f"To: {reminder.phone_number} | Scheduled: {reminder.scheduled_date}"
            )
            self.stdout.write(f"  Message: {reminder.message[:80]}...")

            if not dry_run:
                success, msg = send_sms_reminder(reminder)
                if success:
                    sent += 1
                    self.stdout.write(self.style.SUCCESS(f"  ✅ Sent: {msg}"))
                else:
                    failed += 1
                    self.stdout.write(self.style.ERROR(f"  ❌ Failed: {msg}"))
            else:
                self.stdout.write(self.style.WARNING("  [Would send]"))

        self.stdout.write("\n" + "=" * 60)
        if dry_run:
            self.stdout.write(self.style.WARNING(f"DRY RUN complete. {total} reminder(s) would be sent."))
        else:
            self.stdout.write(
                self.style.SUCCESS(f"Done. Sent: {sent} | Failed: {failed} | Total: {total}")
            )
