from django.urls import path
from .views import (
    LeaveListCreateView,
    LeaveCancelView,
    LeaveBalanceView,
    ManagerPendingView,
    ManagerApproveView,
    ManagerRejectView,
    calendar_view
)

urlpatterns = [
    # employee apis
    # GET to see own leaves, POST to apply for leave
    path('api/leaves/', LeaveListCreateView.as_view(), name='leave-list-create'),

    # employee can cancel their own leave using the leave id
    path('api/leaves/<int:pk>/cancel/', LeaveCancelView.as_view(), name='leave-cancel'),

    # employee can check how many leaves they have left
    path('api/balance/', LeaveBalanceView.as_view(), name='leave-balance'),

    # manager apis
    # manager can see all pending requests from their department
    path('api/manager/pending/', ManagerPendingView.as_view(), name='manager-pending'),

    # manager can approve a specific leave request using its id
    path('api/manager/<int:pk>/approve/', ManagerApproveView.as_view(), name='manager-approve'),

    # manager can reject a specific leave request using its id
    path('api/manager/<int:pk>/reject/', ManagerRejectView.as_view(), name='manager-reject'),

    # calendar page to see all team leaves in one place
    path('calendar/', calendar_view, name='calendar'),
]