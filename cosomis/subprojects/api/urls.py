from django.urls import path

from . import views, views_steps

app_name = 'subprojects'

urlpatterns = [
    path('get-subprojects-by-user/', views.RestGetSubprojectsByUser.as_view(), name="get_subprojects_by_user"),
    path('get-subproject-by-user/<int:pk>/', views.RestGetSubprojectByUser.as_view(), name="get_subproject_by_user"),
    path('save-subproject-geolocation/<int:pk>/', views.SaveSubprojectsGeoLocation.as_view(), name="save_subproject_geolocation"),

    path('get-steps/', views_steps.RestGetSteps.as_view(), name="get_steps"),
    path('get-subproject-steps/<int:subproject_id>/', views_steps.RestGetSubprojectSteps.as_view(), name="get_subproject_steps"),
    path('save-subproject-step/', views_steps.RestSaveSubprojectStep.as_view(), name="save_subproject_steps"),

    path('get-subproject-levels/<int:subproject_id>/', views_steps.RestGetSubprojectLevels.as_view(), name="get_subproject_levels"),
    path('save-subproject-level/', views_steps.RestSaveSubprojectLevel.as_view(), name="save_subproject_level"),

]


