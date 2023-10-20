from django.urls import path
from django.conf.urls import include


app_name = 'users'

urlpatterns = [
    path('', include('usermanager.api.users.urls')),
]
