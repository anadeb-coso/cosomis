from django.urls import path

from . import views

app_name = 'users'

urlpatterns = [
    path('', views.RestGetAUsers.as_view(), name="get_users"),
]


