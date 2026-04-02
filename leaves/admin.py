from django.contrib import admin
from .models import Department, Employee, LeaveType, LeaveBalance, LeaveRequest, Holiday

# Register all models so we can manage them in Django admin panel

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ['name', 'head']

@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ['user', 'department', 'designation', 'is_manager', 'date_of_joining']

@admin.register(LeaveType)
class LeaveTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'max_days_per_year', 'is_paid', 'carry_forward']

@admin.register(LeaveBalance)
class LeaveBalanceAdmin(admin.ModelAdmin):
    list_display = ['employee', 'leave_type', 'year', 'allocated_days', 'used_days']

@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ['employee', 'leave_type', 'start_date', 'end_date', 'num_days', 'status']

@admin.register(Holiday)
class HolidayAdmin(admin.ModelAdmin):
    list_display = ['name', 'date']