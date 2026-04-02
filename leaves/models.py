from django.db import models
from django.contrib.auth.models import User
from datetime import date, timedelta


# i wrote this function to count only working days
# it skips saturdays, sundays and public holidays
def count_working_days(start, end):
    # first get all holidays between start and end date
    holiday_dates = set(
        Holiday.objects.filter(
            date__gte=start,
            date__lte=end
        ).values_list('date', flat=True)
    )
    
    days = 0
    current = start
    while current <= end:
        # weekday() returns 0-4 for monday to friday
        # so if its less than 5, its a working day
        if current.weekday() < 5 and current not in holiday_dates:
            days += 1
        current += timedelta(days=1)
    return days


# Department has a name and optionally a head (who is an employee)
# head can be null because when we first create a department
# we might not have assigned a head yet
class Department(models.Model):
    name = models.CharField(max_length=100)
    head = models.ForeignKey(
        'Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='headed_department'
    )

    def __str__(self):
        return self.name


# Employee is linked to Django's User model using OneToOne
# this way we get login functionality for free
# is_manager field is used to check if employee can approve leaves
class Employee(models.Model):
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


# LeaveType stores different types of leaves like casual, sick etc
# max_days_per_year tells how many days are allowed per year
class LeaveType(models.Model):
    name = models.CharField(max_length=50)
    max_days_per_year = models.PositiveIntegerField()
    is_paid = models.BooleanField(default=True)
    carry_forward = models.BooleanField(default=False)

    def __str__(self):
        return self.name


# LeaveBalance tracks how many leaves each employee has used
# remaining_days is not stored in db, its calculated automatically
# unique_together makes sure there is only one record per
# employee per leave type per year
class LeaveBalance(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    leave_type = models.ForeignKey(LeaveType, on_delete=models.CASCADE)
    year = models.IntegerField()
    allocated_days = models.PositiveIntegerField(default=0)
    used_days = models.PositiveIntegerField(default=0)

    @property
    def remaining_days(self):
        # simple calculation, no need to store this in db
        return self.allocated_days - self.used_days

    class Meta:
        unique_together = ('employee', 'leave_type', 'year')

    def __str__(self):
        return f"{self.employee} - {self.leave_type} ({self.year})"


# LeaveRequest is the main model of this project
# it stores all leave applications made by employees
# status can be PENDING, APPROVED, REJECTED or CANCELLED
class LeaveRequest(models.Model):

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
    num_days = models.PositiveIntegerField(default=0)
    reason = models.TextField()
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING'
    )
    applied_at = models.DateTimeField(auto_now_add=True)
    # this will be filled when manager approves or rejects
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
        # i overrode save() so that num_days gets calculated
        # automatically whenever a leave request is saved
        if self.start_date and self.end_date:
            self.num_days = count_working_days(self.start_date, self.end_date)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.employee} - {self.leave_type} ({self.start_date} to {self.end_date})"


# Holiday model stores public holidays
# these dates are excluded when counting working days
class Holiday(models.Model):
    name = models.CharField(max_length=100)
    date = models.DateField(unique=True)

    def __str__(self):
        return f"{self.name} ({self.date})"