from django.urls import path
from django.conf.urls import include

from administrativelevels import views, views_json

app_name = 'administrativelevels'

urlpatterns = [
    path('', views.AdministrativeLevelsListView.as_view(), name='list'), # Administrative levels list path
    path('create/', views.AdministrativeLevelCreateView.as_view(), name='create'), # Administrative level path to create
    path('update/<int:pk>/', views.AdministrativeLevelUpdateView.as_view(), name='update'), # Administrative level path to update
    path('village-detail/<int:pk>/', views.VillageDetailView.as_view(), name='village_detail'), #The path of the detail of village
    path('detail/<int:pk>/', views.AdministrativeLevelDetailView.as_view(), name='detail'), #The path of the detail
    path('upload/', views.UploadCSVView.as_view(), name='upload'), #The path to download CSV/Excel file from db
    path('download/', views.DownloadCSVView.as_view(), name='download'), #The path to upload CSV file and save in db
    path('download-cvd/', views.DownloadCVDCSVView.as_view(), name='download_cvd'), #The path to upload CVD on CSV file and save in db
    path('village/<int:administrative_level_id>/obstacles', views.ObstaclesListView.as_view(), name='priorities_obstacles'),
    path('village/obstacles/<int:obstacle_id>/delete', views.obstacle_delete, name='obstacle_delete'), #The path to delete obstacle
    path('village/<int:administrative_level_id>/goals', views.GoalsListView.as_view(), name='priorities_goals'),
    path('village/goals/<int:goal_id>/delete', views.goal_delete, name='goal_delete'), #The path to delete goal
    path('village/<int:administrative_level_id>/priorities', views.PrioritiesListView.as_view(), name='priorities_priorities'),
    path('village/priorities/<int:priority_id>/delete', views.priority_delete, name='priority_delete'), #The path to delete priority

    path('geographical-units', views.GeographicalUnitListView.as_view(), name='geographical_units_list'), # Geographical units list path    
    path('geographical-unit/create', views.GeographicalUnitCreateView.as_view(), name='geographical_unit_create'), #The path to create Geographical unit
    path('geographical-unit-detail/<int:pk>/', views.GeographicalUnitDetailView.as_view(), name='geographical_unit_detail'), #The path of the detail of Geographical unit
    path('geographical-unit-update/<int:pk>/', views.GeographicalUnitUpdateView.as_view(), name='geographical_unit_update'), #The path of to update Geographical unit

    path('cvds', views.CVDListView.as_view(), name='cvds_list'), # CVD list path    
    path('cvd/create', views.CVDCreateView.as_view(), name='cvd_create'), #The path to create cvd
    path('cvd-detail/<int:pk>/', views.CVDDetailView.as_view(), name='cvd_detail'), #The path of the detail of cvd
    path('cvd-update/<int:pk>/', views.CVDUpdateView.as_view(), name='cvd_update'), #The path to update cvd

    path('utils/', include('administrativelevels.utils.urls')),
    path('components/', include('administrativelevels.urls_component')),
    path('grm/', include('administrativelevels.grm.urls')),


    path('get-administrative-level-by-type-view/', views_json.GetAdministrativeLevelByTypeView.as_view(), name='get_administrative_level_by_type'), #Get AdministrativeLevel by type

]


