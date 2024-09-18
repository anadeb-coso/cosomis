from django.urls import path

from . import views

app_name = 'administrativelevels'

urlpatterns = [
    path('get-administrative-levels-by-user/<str:type_adl>/<str:project_name>/', views.RestGetAdministrativeLevelByUser.as_view(), name="get_administrative_levels_by_user"),
    path('get-cvds-by-user/<str:project_name>/', views.RestGetACVDByUser.as_view(), name="get_cvds_by_user"),
    path('save-administrative-level-geolocation/<int:pk>/', views.SaveAdministrativeLevelGeoLocation.as_view(), name="save_administrative_level_geolocation"),
]


