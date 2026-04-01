from django.core.management.base import BaseCommand
from django.db import IntegrityError
from leaves.models import Employee, LeaveType, LeaveBalance


class Command(BaseCommand):
    # This text shows when you run: python manage.py help allocate_yearly_leave
    help = 'Allocate yearly leave balance for all employees'

    def add_arguments(self, parser):
        # This adds the --year argument
        # Usage: python manage.py allocate_yearly_leave --year 2026
        parser.add_argument(
            '--year',
            type=int,
            required=True,
            help='The year for which to allocate leave balances'
        )

    def handle(self, *args, **options):
        year = options['year']
        employees = Employee.objects.all()
        leave_types = LeaveType.objects.all()

        self.stdout.write(f"Allocating leave for year {year}...")

        created_count = 0
        skipped_count = 0

        # Loop through every employee and every leave type
        for employee in employees:
            for leave_type in leave_types:
                try:
                    # Create a LeaveBalance record if it doesn't exist
                    LeaveBalance.objects.create(
                        employee=employee,
                        leave_type=leave_type,
                        year=year,
                        allocated_days=leave_type.max_days_per_year,
                        used_days=0
                    )
                    created_count += 1
                except IntegrityError:
                    # unique_together will raise IntegrityError if already exists
                    skipped_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Done! Created: {created_count} balances, Skipped: {skipped_count} (already existed)"
            )
        )