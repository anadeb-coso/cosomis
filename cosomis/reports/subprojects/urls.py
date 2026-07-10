from django.urls import path

from . import views_docx

app_name = 'subprojects'

urlpatterns = [
    path('generate-subproject-report/', views_docx.generate_subproject_report, name='generate_subproject_report'),
]
