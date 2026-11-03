from django.urls import path

from reports import views

app_name = 'rapports'

urlpatterns = [
    path('', views.reports_home, name='home'),
    path('modeles/ajouter/', views.ReportTemplateCreateView.as_view(), name='template_create'),
    path('modeles/<int:pk>/modifier/', views.ReportTemplateUpdateView.as_view(), name='template_update'),
    path('modeles/<int:pk>/supprimer/', views.delete_template, name='template_delete'),
    path('modeles/<int:pk>/apercu/', views.preview_template, name='template_preview'),
    path('modeles/<int:pk>/envoyer/', views.send_template, name='template_send'),
]
