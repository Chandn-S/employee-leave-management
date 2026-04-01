from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from .models import LeaveRequest, LeaveBalance, Employee
from .serializers import (
    LeaveRequestSerializer,
    LeaveBalanceSerializer,
    ApproveLeaveSerializer,
    RejectLeaveSerializer
)


# ─── Helper: Get Employee from request ────────────────────────
def get_employee(request):
    """Get the Employee object for the logged in user"""
    try:
        return request.user.employee
    except Employee.DoesNotExist:
        return None


# ═══════════════════════════════════════════════════════════════
#  EMPLOYEE APIS
# ═══════════════════════════════════════════════════════════════

# ─── List own leaves / Apply for leave ────────────────────────
class LeaveListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Employee views their own leave requests"""
        employee = get_employee(request)
        if not employee:
            return Response({"error": "Employee profile not found."}, status=404)

        leaves = LeaveRequest.objects.filter(employee=employee).order_by('-applied_at')
        serializer = LeaveRequestSerializer(leaves, many=True)
        return Response(serializer.data)

    def post(self, request):
        """Employee applies for leave"""
        employee = get_employee(request)
        if not employee:
            return Response({"error": "Employee profile not found."}, status=404)

        serializer = LeaveRequestSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            # Save with employee set automatically
            serializer.save(employee=employee, status='PENDING')
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ─── Cancel a leave request ────────────────────────────────────
class LeaveCancelView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        """Employee cancels their own leave request"""
        employee = get_employee(request)
        if not employee:
            return Response({"error": "Employee profile not found."}, status=404)

        try:
            leave = LeaveRequest.objects.get(pk=pk, employee=employee)
        except LeaveRequest.DoesNotExist:
            return Response({"error": "Leave request not found."}, status=404)

        # Cannot cancel already rejected or cancelled leave
        if leave.status in ['REJECTED', 'CANCELLED']:
            return Response({"error": f"Cannot cancel a {leave.status} leave."}, status=400)

        # Cannot cancel APPROVED leave if start_date has already passed
        if leave.status == 'APPROVED' and leave.start_date <= timezone.now().date():
            return Response({"error": "Cannot cancel approved leave after start date has passed."}, status=400)

        # If APPROVED and cancelled before start_date → restore balance
        if leave.status == 'APPROVED':
            try:
                balance = LeaveBalance.objects.get(
                    employee=employee,
                    leave_type=leave.leave_type,
                    year=leave.start_date.year
                )
                balance.used_days -= leave.num_days
                balance.save()
            except LeaveBalance.DoesNotExist:
                pass

        leave.status = 'CANCELLED'
        leave.save()
        return Response({"message": "Leave request cancelled successfully."})


# ─── View own leave balances ───────────────────────────────────
class LeaveBalanceView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Employee views their own leave balances"""
        employee = get_employee(request)
        if not employee:
            return Response({"error": "Employee profile not found."}, status=404)

        current_year = timezone.now().year
        balances = LeaveBalance.objects.filter(employee=employee, year=current_year)
        serializer = LeaveBalanceSerializer(balances, many=True)
        return Response(serializer.data)


# ═══════════════════════════════════════════════════════════════
#  MANAGER APIS
# ═══════════════════════════════════════════════════════════════

# ─── Helper: Check if user is a manager ───────────────────────
def is_manager(request):
    """Check if the logged in user is a manager"""
    employee = get_employee(request)
    return employee and employee.is_manager


# ─── List pending requests from own department ─────────────────
class ManagerPendingView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Manager views all pending leave requests from their department"""
        if not is_manager(request):
            return Response({"error": "Only managers can access this."}, status=403)

        manager = get_employee(request)
        # Get pending requests from same department only
        pending = LeaveRequest.objects.filter(
            status='PENDING',
            employee__department=manager.department
        ).order_by('applied_at')

        serializer = LeaveRequestSerializer(pending, many=True)
        return Response(serializer.data)


# ─── Approve a leave request ───────────────────────────────────
class ManagerApproveView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        """Manager approves a leave request"""
        if not is_manager(request):
            return Response({"error": "Only managers can access this."}, status=403)

        manager = get_employee(request)

        try:
            leave = LeaveRequest.objects.get(pk=pk, status='PENDING', employee__department=manager.department)
        except LeaveRequest.DoesNotExist:
            return Response({"error": "Leave request not found."}, status=404)

        serializer = ApproveLeaveSerializer(data=request.data)
        if serializer.is_valid():
            # Deduct from leave balance
            try:
                balance = LeaveBalance.objects.get(
                    employee=leave.employee,
                    leave_type=leave.leave_type,
                    year=leave.start_date.year
                )
                balance.used_days += leave.num_days
                balance.save()
            except LeaveBalance.DoesNotExist:
                return Response({"error": "Leave balance not found."}, status=400)

            # Update leave request
            leave.status = 'APPROVED'
            leave.reviewed_by = manager
            leave.reviewed_at = timezone.now()
            leave.save()

            return Response({"message": "Leave request approved successfully."})
        return Response(serializer.errors, status=400)


# ─── Reject a leave request ────────────────────────────────────
class ManagerRejectView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        """Manager rejects a leave request"""
        if not is_manager(request):
            return Response({"error": "Only managers can access this."}, status=403)

        manager = get_employee(request)

        try:
            leave = LeaveRequest.objects.get(pk=pk, status='PENDING', employee__department=manager.department)
        except LeaveRequest.DoesNotExist:
            return Response({"error": "Leave request not found."}, status=404)

        serializer = RejectLeaveSerializer(data=request.data)
        if serializer.is_valid():
            # No balance change on rejection
            leave.status = 'REJECTED'
            leave.reviewed_by = manager
            leave.reviewed_at = timezone.now()
            leave.rejection_reason = serializer.validated_data['rejection_reason']
            leave.save()

            return Response({"message": "Leave request rejected."})
        return Response(serializer.errors, status=400)