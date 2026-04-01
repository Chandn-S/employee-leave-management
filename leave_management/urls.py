from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect

# Redirect homepage to login
def home_redirect(request):
    return redirect('/accounts/login/')

urlpatterns = [
    path('', home_redirect),  # ← Homepage redirects to login
    path('admin/', admin.site.urls),
    path('', include('leaves.urls')),
    path('accounts/', include('django.contrib.auth.urls')),
]