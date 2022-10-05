from django.urls import path

from . import views

app_name = 'subprojects'
urlpatterns = [
    path('', views.SubprojectsListView.as_view(), name='list'),
    path('<int:pk>', views.SubprojectDetailView.as_view(), name='detail'),
]