from django.urls import path

from attachments import views
from subprojects.files import views as views_files

app_name = 'attachments'
urlpatterns = [
    # path('upload-to-issue', views.UploadIssueAttachmentAPIView.as_view(), name='upload-issue-attachment'),
    path('upload-to-subproject-step', views.UploadSubprojectStepAttachmentAPIView.as_view(), name='upload-subproject-step-attachment'),
    path('upload-to-subproject-step-url', views.UploadSubprojectStepUrlAttachmentAPIView.as_view(), name='upload-subproject-step-url-attachment'),
    path('delete-subproject-file-by-url', views.DeleteSubprojectFileAPIView.as_view(), name='delete-subproject-file-by-url'),


    # path('files/<int:subproject_id>', views_files.AttachmentListView.as_view(), name='attachments'), 
    path('detail/<int:adm_id>/attachments/<path:url>/download/', views.attachment_download,
         name='attachment_download'),
    path('detail/<int:adm_id>/attachments/download-zip/', views.attachment_download_zip,
         name='attachment_download_zip'),
    path('attachments/download-zip/', views.gloval_attachment_download_zip,
         name='gloval_attachment_download_zip'),
    path('attachments/<int:pk>/download/', views.attachment_download_by_id,
         name='attachment_download_by_id'),
]
