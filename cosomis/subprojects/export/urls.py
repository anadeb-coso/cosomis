from django.urls import path
from . import views

app_name = 'export'

urlpatterns = [
    path('excel-insufficient/', views.insufficient_subprojects_status_to_excel, name='export_subprojects_images_status_excel'),
]