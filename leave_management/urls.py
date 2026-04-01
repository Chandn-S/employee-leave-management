from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    # Include all leaves app URLs
    path('', include('leaves.urls')),
]