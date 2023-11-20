from django.urls import path
from django.conf.urls import include

from . import views_display_grouped as views

app_name = 'display_grouped'
urlpatterns = [
    path('dashboard/', views.DashboardTemplateView.as_view(), name='display_grouped_dashboard'),
    path('display-grouped-by-sector/', views.DashboardSubprojectsDisplayGroupedBySectorsListView.as_view(), name='display_grouped_by_sector'),
    path('display-grouped-by-sector-sub/', views.DashboardSubprojectsDisplayGroupedBySectorsListSubView.as_view(), name='display_grouped_by_sector_sub'),
    path('display-grouped-by-type-sub/', views.DashboardSubprojectsDisplayGroupedByTypeListSubView.as_view(), name='display_grouped_by_type_sub'),
    
]
