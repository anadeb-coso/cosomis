from django.urls import path
from django.conf.urls import include

from . import views

app_name = 'subprojects'
urlpatterns = [
    path('', views.SubprojectsListView.as_view(), name='list'),
    path('map', views.SubprojectsMapViewPage.as_view(), name='map'),
    path('map-view', views.SubprojectsMapView.as_view(), name='map_view'),
    path('<int:pk>', views.SubprojectDetailView.as_view(), name='detail'),
    path('create', views.SubprojectCreateView.as_view(), name='create'),
    path('create-infra-or-link-subproject/<int:subproject_id>/', views.SubSubprojectCreateView.as_view(), name='create_infra_or_link_subproject'),
    path('update/<int:pk>/', views.SubprojectUpdateView.as_view(), name='update'),
    path('vulnerable-group/create', views.VulnerableGroupCreateView.as_view(), name='vulnerable_group_create'),
    path('image/<int:file_id>/delete', views.subprojectfile_delete, name='subproject_file_delete'),

    path('download/', views.DownloadCSVView.as_view(), name='download'), #The path to upload CSV file and save in db

    path('utils/', include('subprojects.utils.urls')),
    path('components/', include('subprojects.urls_component')),
    path('step/', include('subprojects.urls_step')),
]
