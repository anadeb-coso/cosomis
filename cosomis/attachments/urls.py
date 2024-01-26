from django.urls import path

from attachments import views

app_name = 'attachments'
urlpatterns = [
    # path('upload-to-issue', views.UploadIssueAttachmentAPIView.as_view(), name='upload-issue-attachment'),
    path('upload-to-subproject-step', views.UploadSubprojectStepAttachmentAPIView.as_view(), name='upload-subproject-step-attachment'),
    path('delete-subproject-file-by-url', views.DeleteSubprojectFileAPIView.as_view(), name='delete-subproject-file-by-url'),
]
