"""cosomis URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.8/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
"""
from django.urls import path
from django.conf.urls import include
from django.contrib import admin
from django.conf.urls.i18n import i18n_patterns
from django.conf import settings
from django.conf.urls.static import static

from . import views

# urlpatterns = [
#     path('admin/', admin.site.urls),
#     path('', include('usermanager.urls')),
#     path('subprojects/', include('subprojects.urls')),
#     path('administrative-levels/', include('administrativelevels.urls')),
#     path('unicorn/', include('django_unicorn.urls')),
# ]
urlpatterns = [
    path('set-language/', 
         views.set_language, 
         name='set_language'),
    path('api/', include('cosomis.urls_api')),
]

urlpatterns += i18n_patterns(
    path('admin/', admin.site.urls),
    path('', include('usermanager.urls')),
    path('subprojects/', include('subprojects.urls')),
    path('administrative-levels/', include('administrativelevels.urls')),
    path('unicorn/', include('django_unicorn.urls')),
    path('kobotoolbox/', include('kobotoolbox.urls')),
    path('dashboard/', include('dashboard.urls')),
    path('financial/', include('financial.urls')),
    path('custom-file/', include('custom_file.urls')),

    path('services/', include('administrativelevels.libraries.services.urls')),

    path('delete-object/<int:object_id>/<str:type>/', views.DeleteObjectFormView.as_view(), name='object_deletion_form'),
)


if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root = settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root = settings.MEDIA_ROOT)