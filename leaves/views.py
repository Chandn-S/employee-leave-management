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


# helper function to get the employee object from the logged in user
# returns None if the user doesn't have an employee profile
def get_employee(request):
    try:
        return request.user.employee
    except Employee.DoesNotExist:
        return None


# helper function to check if the logged in user is a manager
def is_manager(request):
    employee = get_employee(request)
    return employee and employee.is_manager


# this view handles two things:
# GET - employee can see their own leave requests
# POST - employee can apply for a new leave
class LeaveListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        employee = get_employee(request)
        if not employee:
            return Response({"error": "Employee profile not found."}, status=404)

        # get all leaves for this employee, latest first
        leaves = LeaveRequest.objects.filter(employee=employee).order_by('-applied_at')
        serializer = LeaveRequestSerializer(leaves, many=True)
        return Response(serializer.data)

    def post(self, request):
        employee = get_employee(request)
        if not employee:
            return Response({"error": "Employee profile not found."}, status=404)

        # pass request to serializer so it can access the employee
        serializer = LeaveRequestSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            # save the leave with status PENDING by default
            leave = serializer.save(employee=employee, status='PENDING')

            # send email to manager after employee applies
            # i used try except so that even if email fails, the API still works
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


# employee can cancel their own leave request
# but there are some rules:
# 1. cannot cancel if already rejected or cancelled
# 2. cannot cancel approved leave if start date has passed
# 3. if approved and cancelled before start date, restore the balance
class LeaveCancelView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        employee = get_employee(request)
        if not employee:
            return Response({"error": "Employee profile not found."}, status=404)

        try:
            leave = LeaveRequest.objects.get(pk=pk, employee=employee)
        except LeaveRequest.DoesNotExist:
            return Response({"error": "Leave request not found."}, status=404)

        # rule 1 - cant cancel rejected or already cancelled leave
        if leave.status in ['REJECTED', 'CANCELLED']:
            return Response({"error": f"Cannot cancel a {leave.status} leave."}, status=400)

        # rule 2 - cant cancel approved leave after start date
        if leave.status == 'APPROVED' and leave.start_date <= timezone.now().date():
            return Response({"error": "Cannot cancel approved leave after start date has passed."}, status=400)

        # rule 3 - if approved and cancelled before start date, give back the balance
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


# employee can view their leave balances for current year
class LeaveBalanceView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        employee = get_employee(request)
        if not employee:
            return Response({"error": "Employee profile not found."}, status=404)

        current_year = timezone.now().year
        balances = LeaveBalance.objects.filter(employee=employee, year=current_year)
        serializer = LeaveBalanceSerializer(balances, many=True)
        return Response(serializer.data)


# manager can see all pending leave requests from their department
class ManagerPendingView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # first check if the logged in user is actually a manager
        if not is_manager(request):
            return Response({"error": "Only managers can access this."}, status=403)

        manager = get_employee(request)
        # only show pending requests from same department
        pending = LeaveRequest.objects.filter(
            status='PENDING',
            employee__department=manager.department
        ).order_by('applied_at')

        serializer = LeaveRequestSerializer(pending, many=True)
        return Response(serializer.data)


# manager approves a leave request
# when approved, we deduct the days from employee's leave balance
class ManagerApproveView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if not is_manager(request):
            return Response({"error": "Only managers can access this."}, status=403)

        manager = get_employee(request)

        # make sure the leave exists and belongs to manager's department
        try:
            leave = LeaveRequest.objects.get(pk=pk, status='PENDING', employee__department=manager.department)
        except LeaveRequest.DoesNotExist:
            return Response({"error": "Leave request not found."}, status=404)

        serializer = ApproveLeaveSerializer(data=request.data)
        if serializer.is_valid():
            # deduct leave days from balance
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

            # update the leave request status
            leave.status = 'APPROVED'
            leave.reviewed_by = manager
            leave.reviewed_at = timezone.now()
            leave.save()
            return Response({"message": "Leave request approved successfully."})
        return Response(serializer.errors, status=400)


# manager rejects a leave request
# no balance change when rejecting, just update status and save reason
class ManagerRejectView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
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


# simple calendar view to show all team leaves
# only logged in users can see this
@login_required
def calendar_view(request):
    current_year = datetime.now().year
    current_month = datetime.now().strftime('%B')

    # get all leave requests for this year
    leave_requests = LeaveRequest.objects.filter(
        start_date__year=current_year
    ).order_by('start_date')

    # count leaves by status for the stats cards
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