from django.urls import path

from results_framework import views

app_name = 'results_framework'

urlpatterns = [
    path('', views.indicator_list, name='indicator_list'),
    path('indicateurs/ajouter/', views.IndicatorCreateView.as_view(), name='indicator_create'),
    path('indicateurs/<int:pk>/', views.indicator_detail, name='indicator_detail'),
    path('indicateurs/<int:pk>/modifier/', views.IndicatorUpdateView.as_view(), name='indicator_update'),
    path('indicateurs/<int:pk>/supprimer/', views.indicator_delete, name='indicator_delete'),
    path('mesures/<int:pk>/modifier/', views.MeasurementUpdateView.as_view(), name='measurement_update'),
    path('mesures/<int:pk>/supprimer/', views.measurement_delete, name='measurement_delete'),
]
