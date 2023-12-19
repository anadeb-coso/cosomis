from django.urls import path

from administrativelevels.grm import views

app_name = 'grm'

urlpatterns = [
    path('review-issues/<int:administrative_id>/', views.ReviewIssuesFormView.as_view(), name='review_issues'),
    path('issue-list', views.IssueListView.as_view(), name='issue_list'),
    path('issues-statistics', views.IssuesStatisticsView.as_view(), name='issues_statistics'),
]


