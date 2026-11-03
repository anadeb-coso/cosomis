from django.urls import path

from assignments import views_facilitators as views

app_name = 'animateurs'

urlpatterns = [
    path('', views.facilitator_list, name='list'),
    path('<int:pk>/', views.facilitator_profile, name='profile'),
]
