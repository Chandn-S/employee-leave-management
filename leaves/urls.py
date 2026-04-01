from django.urls import path
from .views import (
    LeaveListCreateView,
    LeaveCancelView,
    LeaveBalanceView,
    ManagerPendingView,
    ManagerApproveView,
    ManagerRejectView
)

urlpatterns = [
    # ── Employee APIs ──────────────────────────────────────────
    # GET  → list own leave requests
    # POST → apply for leave
    path('api/leaves/', LeaveListCreateView.as_view(), name='leave-list-create'),

    # POST → cancel a leave request
    path('api/leaves/<int:pk>/cancel/', LeaveCancelView.as_view(), name='leave-cancel'),

    # GET → view own leave balances
    path('api/balance/', LeaveBalanceView.as_view(), name='leave-balance'),

    # ── Manager APIs ───────────────────────────────────────────
    # GET → list all pending requests from own department
    path('api/manager/pending/', ManagerPendingView.as_view(), name='manager-pending'),

    # POST → approve a leave request
    path('api/manager/<int:pk>/approve/', ManagerApproveView.as_view(), name='manager-approve'),

    # POST → reject a leave request
    path('api/manager/<int:pk>/reject/', ManagerRejectView.as_view(), name='manager-reject'),
]