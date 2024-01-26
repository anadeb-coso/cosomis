from django.urls import path
from django.conf.urls import include


app_name = 'api'

urlpatterns = [
    path('subprojects/', include('subprojects.api.urls')),
    path('administrativelevels/', include('administrativelevels.api.urls')),
    path('users/', include('usermanager.api.urls')),
    path('attachments/', include('attachments.urls')),
]
