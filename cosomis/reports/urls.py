
from django.urls import path
from django.conf.urls import include

app_name = 'reports'

urlpatterns = [
    path('subprojects/', include('reports.subprojects.urls')),
]
