from django.db import models
from django.contrib.auth.models import User
from datetime import date, timedelta


# ─── Helper Function ───────────────────────────────────────────
def count_working_days(start, end):
    """Count working days between two dates, 
    excluding weekends and public holidays"""
    # Get all holiday dates in this range
    holiday_dates = set(
        Holiday.objects.filter(
            date__gte=start,
            date__lte=end
        ).values_list('date', flat=True)
    )
    
    days = 0
    current = start
    while current <= end:
        # Exclude weekends AND holidays
        if current.weekday() < 5 and current not in holiday_dates:
            days += 1
        current += timedelta(days=1)
    return days


# ─── Department Model ──────────────────────────────────────────
class Department(models.Model):
    name = models.CharField(max_length=100)
    # head is nullable because department may not have a head yet
    head = models.ForeignKey(
        'Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='headed_department'
    )

    def __str__(self):
        return self.name


# ─── Employee Model ────────────────────────────────────────────
class Employee(models.Model):
    # OneToOne with Django's built-in User model
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    designation = models.CharField(max_length=100)
    date_of_joining = models.DateField()
    is_manager = models.BooleanField(default=False)

    def __str__(self):
        return self.user.get_full_name() or self.user.username


# ─── LeaveType Model ───────────────────────────────────────────
class LeaveType(models.Model):
    name = models.CharField(max_length=50)  # Casual, Sick, Earned, Unpaid
    max_days_per_year = models.PositiveIntegerField()
    is_paid = models.BooleanField(default=True)
    carry_forward = models.BooleanField(default=False)

    def __str__(self):
        return self.name


# ─── LeaveBalance Model ────────────────────────────────────────
class LeaveBalance(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    leave_type = models.ForeignKey(LeaveType, on_delete=models.CASCADE)
    year = models.IntegerField()
    allocated_days = models.PositiveIntegerField(default=0)
    used_days = models.PositiveIntegerField(default=0)

    # remaining_days is a property — auto calculated, not stored in DB
    @property
    def remaining_days(self):
        return self.allocated_days - self.used_days

    class Meta:
        # One balance record per employee per leave type per year
        unique_together = ('employee', 'leave_type', 'year')

    def __str__(self):
        return f"{self.employee} - {self.leave_type} ({self.year})"


# ─── LeaveRequest Model ────────────────────────────────────────
class LeaveRequest(models.Model):

    # Status choices
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('CANCELLED', 'Cancelled'),
    ]

    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name='leave_requests'
    )
    leave_type = models.ForeignKey(LeaveType, on_delete=models.CASCADE)
    start_date = models.DateField()
    end_date = models.DateField()
    # num_days is auto calculated when saving
    num_days = models.PositiveIntegerField(default=0)
    reason = models.TextField()
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING'
    )
    applied_at = models.DateTimeField(auto_now_add=True)
    # Manager who reviewed the request
    reviewed_by = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_requests'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, null=True)

    def save(self, *args, **kwargs):
        # Auto calculate num_days excluding weekends
        if self.start_date and self.end_date:
            self.num_days = count_working_days(self.start_date, self.end_date)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.employee} - {self.leave_type} ({self.start_date} to {self.end_date})"
    

# ─── Holiday Model ─────────────────────────────────────────────
class Holiday(models.Model):
    """Public holidays — these are excluded from working day count"""
    name = models.CharField(max_length=100)
    date = models.DateField(unique=True)

    def __str__(self):
        return f"{self.name} ({self.date})"