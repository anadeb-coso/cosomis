from django.urls import path

from process_manager import views

app_name = 'process_manager'
urlpatterns = [
    path('select-project/', views.ProjectListView.as_view(), name='list'),
]
