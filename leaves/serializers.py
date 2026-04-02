from rest_framework import serializers
from django.utils import timezone
from .models import LeaveRequest, LeaveBalance, LeaveType, Employee, Department


# simple serializer for department, just need id and name
class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ['id', 'name']


# employee serializer with some extra read only fields
# i added username and full_name so the response looks better
class EmployeeSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    full_name = serializers.CharField(source='user.get_full_name', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)

    class Meta:
        model = Employee
        fields = ['id', 'username', 'full_name', 'department_name', 'designation', 'is_manager']


# serializer for leave types like casual, sick, earned, unpaid
class LeaveTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveType
        fields = ['id', 'name', 'max_days_per_year', 'is_paid', 'carry_forward']


# leave balance serializer
# remaining_days is a property in the model so i made it read only here
class LeaveBalanceSerializer(serializers.ModelSerializer):
    leave_type_name = serializers.CharField(source='leave_type.name', read_only=True)
    remaining_days = serializers.IntegerField(read_only=True)

    class Meta:
        model = LeaveBalance
        fields = ['id', 'leave_type', 'leave_type_name', 'year', 'allocated_days', 'used_days', 'remaining_days']


# this is the main serializer for leave requests
# it handles both creating and viewing leave requests
class LeaveRequestSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.user.get_full_name', read_only=True)
    leave_type_name = serializers.CharField(source='leave_type.name', read_only=True)

    class Meta:
        model = LeaveRequest
        fields = [
            'id', 'employee', 'employee_name', 'leave_type', 'leave_type_name',
            'start_date', 'end_date', 'num_days', 'reason',
            'status', 'applied_at', 'reviewed_by', 'reviewed_at', 'rejection_reason'
        ]
        # these fields should not be set by the user
        # they are set automatically by the system
        read_only_fields = ['employee', 'num_days', 'status', 'applied_at', 'reviewed_by', 'reviewed_at', 'rejection_reason']

    def validate(self, data):
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        leave_type = data.get('leave_type')
        request = self.context.get('request')
        employee = request.user.employee

        # check 1 - start date should be before end date
        if start_date and end_date:
            if start_date > end_date:
                raise serializers.ValidationError("Start date must be before end date.")

        # check 2 - make sure there are no overlapping leaves
        # we check both pending and approved leaves
        overlapping = LeaveRequest.objects.filter(
            employee=employee,
            status__in=['PENDING', 'APPROVED'],
            start_date__lte=end_date,
            end_date__gte=start_date
        )
        if overlapping.exists():
            raise serializers.ValidationError("You already have a leave request for these dates.")

        # check 3 - make sure employee has enough leave balance
        current_year = timezone.now().year
        try:
            balance = LeaveBalance.objects.get(
                employee=employee,
                leave_type=leave_type,
                year=current_year
            )
            from .models import count_working_days
            num_days = count_working_days(start_date, end_date)

            if num_days > balance.remaining_days:
                raise serializers.ValidationError(
                    f"Insufficient leave balance. You have {balance.remaining_days} days remaining."
                )
        except LeaveBalance.DoesNotExist:
            raise serializers.ValidationError("No leave balance found for this leave type.")

        return data


# simple serializer for approving leave
# note is optional, manager can add a comment if they want
class ApproveLeaveSerializer(serializers.Serializer):
    note = serializers.CharField(required=False, allow_blank=True)


# serializer for rejecting leave
# rejection_reason is required, manager must give a reason
class RejectLeaveSerializer(serializers.Serializer):
    rejection_reason = serializers.CharField(required=True)