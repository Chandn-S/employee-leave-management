from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from .models import LeaveRequest, LeaveBalance, Employee
from .serializers import (
    LeaveRequestSerializer,
    LeaveBalanceSerializer,
    ApproveLeaveSerializer,
    RejectLeaveSerializer
)
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from datetime import datetime


# ─── Helper: Get Employee from request ────────────────────────
def get_employee(request):
    try:
        return request.user.employee
    except Employee.DoesNotExist:
        return None


# ─── Helper: Check if user is a manager ───────────────────────
def is_manager(request):
    employee = get_employee(request)
    return employee and employee.is_manager


# ═══════════════════════════════════════════════════════════════
#  EMPLOYEE APIS
# ═══════════════════════════════════════════════════════════════

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
            leave = serializer.save(employee=employee, status='PENDING')

            # ── Send email notification to manager ─────────────
            try:
                manager = Employee.objects.filter(
                    department=employee.department,
                    is_manager=True
                ).first()

                if manager and manager.user.email:
                    send_mail(
                        subject=f"New Leave Request from {employee.user.get_full_name()}",
                        message=f"Hi {manager.user.get_full_name()},\n\n{employee.user.get_full_name()} has applied for {leave.leave_type.name} leave.\n\nFrom: {leave.start_date}\nTo: {leave.end_date}\nDays: {leave.num_days}\nReason: {leave.reason}\n\nPlease login to approve or reject.",
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[manager.user.email],
                        fail_silently=True
                    )
            except Exception:
                pass

            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


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

        if leave.status in ['REJECTED', 'CANCELLED']:
            return Response({"error": f"Cannot cancel a {leave.status} leave."}, status=400)

        if leave.status == 'APPROVED' and leave.start_date <= timezone.now().date():
            return Response({"error": "Cannot cancel approved leave after start date has passed."}, status=400)

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

class ManagerPendingView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Manager views all pending leave requests from their department"""
        if not is_manager(request):
            return Response({"error": "Only managers can access this."}, status=403)
        manager = get_employee(request)
        pending = LeaveRequest.objects.filter(
            status='PENDING',
            employee__department=manager.department
        ).order_by('applied_at')
        serializer = LeaveRequestSerializer(pending, many=True)
        return Response(serializer.data)


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

            leave.status = 'APPROVED'
            leave.reviewed_by = manager
            leave.reviewed_at = timezone.now()
            leave.save()
            return Response({"message": "Leave request approved successfully."})
        return Response(serializer.errors, status=400)


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
            leave.status = 'REJECTED'
            leave.reviewed_by = manager
            leave.reviewed_at = timezone.now()
            leave.rejection_reason = serializer.validated_data['rejection_reason']
            leave.save()
            return Response({"message": "Leave request rejected."})
        return Response(serializer.errors, status=400)
    
# ─── Calendar View ─────────────────────────────────────────────
@login_required
def calendar_view(request):
    """Simple calendar view showing team leave schedule"""
    current_year = datetime.now().year
    current_month = datetime.now().strftime('%B')

    # Get all leave requests for current year
    leave_requests = LeaveRequest.objects.filter(
        start_date__year=current_year
    ).order_by('start_date')

    context = {
        'leave_requests': leave_requests,
        'current_year': current_year,
        'current_month': current_month,
        'department': 'All Departments',
        'total_leaves': leave_requests.count(),
        'approved_count': leave_requests.filter(status='APPROVED').count(),
        'pending_count': leave_requests.filter(status='PENDING').count(),
        'rejected_count': leave_requests.filter(status='REJECTED').count(),
    }
    return render(request, 'leaves/calendar.html', context)