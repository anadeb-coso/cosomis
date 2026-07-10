from django.urls import path
from . import views

app_name = 'files'

urlpatterns = [
    
    path('files/<int:subproject_id>', views.FilesListView.as_view(), name='files'), 
#     path('files/<int:subproject_id>', views.AttachmentListView.as_view(), name='attachments'), 
    path('toggle-validation-file-view/', views.ToggleValidationFileView.as_view(), name='toggle_validation_file_view'), 
    path('toggle-principal-file-view/', views.TogglePrincipalFileView.as_view(), name='toggle_principal_file_view'), 
    path('toggle-special-file-view/', views.ToggleSpecialFileView.as_view(), name='toggle_special_file_view'), 
    path('file-comments-view/', views.FileCommentsListView.as_view(), name='file_comments_view'), 


    path('detail/files/<path:url>/download/', views.file_download,
         name='file_download'),
    path('detail/files/download-zip/', views.files_download_zip,
         name='files_download_zip'),
]