from django.urls import path

from .views_sheet import *
from . import views_sheet2


from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r'subprojects', SubprojectViewSet)


app_name = 'sheet'
urlpatterns = [

    # path('api/', include(router.urls)),
    path('sheet-editor/', subproject_sheet_view, name='subproject_sheet_editor'),



    path('api-2/subprojects/', views_sheet2.subproject_list, name='subproject_list'),
    path('api-2/subprojects/create-or-update/', views_sheet2.subproject_create_or_update, name='subproject_create_or_update'),
    path('api-2/subprojects/<int:pk>/delete/', views_sheet2.subproject_delete, name='subproject_delete'),
    # Ajoutez cette vue pour servir le template principal
    path('spreadsheet/', views_sheet2.spreadsheet_view, name='spreadsheet-view'),
    path('api/options/<str:model_name>/', OptionsAPIView.as_view(), name='api-options'),
]
