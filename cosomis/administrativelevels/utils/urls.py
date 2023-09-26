from django.urls import path

from . import views

app_name = 'utils'
urlpatterns = [
    path('get-administrative-level-for-cvd-by-adl', views.GetAdministrativeLevelForCVDByADLView.as_view(),
         name='get_administrative_level_for_cvd_by_adl'),
    path('get-choices-for-next-administrative-level-no-condition', views.GetChoicesForNextAdministrativeLevelNoConditionView.as_view(),
         name='get_choices_for_next_administrative_level_no_condition'),
    path('get-choices-for-next-administrative-level', views.GetChoicesForNextAdministrativeLevelView.as_view(),
         name='get_choices_for_next_administrative_level'),
     path('get-choices-for-next-administrative-level-by-geographical-unit', 
          views.GetChoicesAdministrativeLevelByGeographicalUnitView.as_view(),
          name='get_choices_for_next_administrative_level_by_geographical_unit'),
    path('get-ancestor-administrative-levels', views.GetAncestorAdministrativeLevelsView.as_view(),
         name='get_ancestor_administrative_levels'),
     
     path('get-choices-for-next-administrative-level-all', views.GetChoicesForNextAdministrativeLevelAllView.as_view(),
         name='get_choices_for_next_administrative_level_all'),
]
