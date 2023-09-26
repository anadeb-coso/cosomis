from django.urls import path
from django.conf.urls import include

from . import views_step

app_name = 'step'
urlpatterns = [
    path('subproject-step-add-template/<int:subproject_id>/', views_step.SubprojectStepAddTemplateView.as_view(), name='subproject_step_add_template'),
    path('subproject-step-graph-template/<int:subproject_id>/', views_step.SubprojectStepGraphTemplateView.as_view(), name='subproject_step_graph_template'),
    path('add-subproject-step/<int:subproject_id>/', views_step.SubprojectStepAddFormView.as_view(), name='subproject_step_add_form'),
    path('update-subproject-step/<int:subproject_id>/<int:subproject_step_update_id>/', views_step.SubprojectStepAddFormView.as_view(), name='subproject_step_update_form'),
    path('add-subproject-level/<int:subproject_id>/<int:subproject_step_id>/', views_step.SubprojectLevelAddFormView.as_view(), name='subproject_level_add_form'),
    path('add-subproject-level/<int:subproject_id>/<int:subproject_step_id>/<int:subproject_level_update_id>/', views_step.SubprojectLevelAddFormView.as_view(), name='subproject_level_update_form'),
    # path('delete-subproject-step/<int:subproject_step_deletion_id>/<str:type>/', views_step.SubprojectStepDeleteFormView.as_view(), name='subproject_step_delete_form'),
    path('display-subproject-step-files/<int:subproject_step_id>/', views_step.FilesView.as_view(), name='display_subproject_step_files'),
    path('display-subproject-level-files/<int:subproject_level_id>/', views_step.FilesView.as_view(), name='display_subproject_level_files'),
]
