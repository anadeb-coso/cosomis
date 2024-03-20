from django.urls import path
from django.conf.urls import include

from . import views_subprojects, views_excel, views_administrativelevels, views_summary

app_name = 'dashboard'

urlpatterns = [
    path('', views_summary.DashboardTemplateView.as_view(), name='dashboard'),
    path('subprojects/', views_subprojects.DashboardTemplateView.as_view(), name='dashboard_subprojects'),
    path('administrativelevels/', views_administrativelevels.DashboardTemplateView.as_view(), name='dashboard_administrativelevels'),
    
    path('subprojects-sectors/', views_subprojects.DashboardSubprojectsListView.as_view(), name='dashboard_subprojects_sectors'),
    path('subprojects-sectors-amount/', views_subprojects.DashboardSubprojectsBySectorAmountListView.as_view(), name='dashboard_subprojects_sectors_amount'),
    path('subprojects-sectors-and-steps/', views_subprojects.DashboardSubprojectsSectorsAndStepsListView.as_view(), name='dashboard_subprojects_sectors_and_steps'),
    path('subprojects-steps-already-track/', views_subprojects.DashboardSubprojectsStepsAlreadyTrackListView.as_view(), name='dashboard_subprojects_steps_already_track'),
    path('subprojects-current-steps/', views_subprojects.DashboardSubprojectsCurrentStepsListView.as_view(), name='dashboard_subprojects_current_steps'),
    
    path('waves/', views_administrativelevels.DashboardWaveListView.as_view(), name='dashboard_waves'),
    path('waves-times/', views_administrativelevels.DashboardWaveTimesListView.as_view(), name='dashboard_waves_times'),
    path('summary-administrativel-levels-number/', views_administrativelevels.DashboardSummaryAdministrativeLevelNumberListView.as_view(), name='dashboard_summary_administrativel_levels_number'),
    path('summary-allocation/', views_administrativelevels.DashboardSummaryAdministrativeLevelAllocationListView.as_view(), name='dashboard_summary_allocation'),
    path('summary-allocation-cvd/', views_administrativelevels.DashboardSummaryCVDAllocationListView.as_view(), name='dashboard_summary_allocation_cvd'),

    path('download-excel-file/', views_excel.DownloadExcelFile.as_view(), name='dashboard_download_excel_file'),
    
    
    path('summary/', views_summary.DashboardTemplateView.as_view(), name='dashboard_summary'),
    path('summary-subprojects/', views_summary.DashboardSubprojectsListView.as_view(), name='dashboard_summary_subprojects'),
    path('summary-subprojects-details/', views_summary.SubprojectsDetailsModalView.as_view(), name='dashboard_summary_subprojects_details'),
]
