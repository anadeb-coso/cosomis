"""
Django settings for cosomis project.

Generated by 'django-admin startproject' using Django 1.8.9.

For more information on this file, see
https://docs.djangoproject.com/en/1.8/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/1.8/ref/settings/
"""

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
from pathlib import Path
import os
import django.conf.locale
import environ
from django.conf import global_settings
from django.utils.translation import gettext_lazy as _

# https://django-environ.readthedocs.io/en/latest/
env = environ.Env()
env.read_env()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/1.8/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'pl&dkqrq0rj+#n747=@#a-0b(bgb2j#%@f7v4_vp1q84cr7r#$'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env.bool('DEBUG', False)

ALLOWED_HOSTS = env('ALLOWED_HOSTS', list, ['localhost'])


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
]

CREATED_APPS = [
    'usermanager',
    'subprojects',
    'administrativelevels',
    'unicorn',
    'kobotoolbox',
    'authentication',
    'assignments',
    'dashboard',
    'financial',
    'process_manager',
    'custom_file',
]

THIRD_PARTY_APPS = [
    'bootstrap4',
    'django_unicorn',
    'django_celery_results',
    'drf_spectacular',
    'rest_framework',
]

INSTALLED_APPS += CREATED_APPS + THIRD_PARTY_APPS

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware', #tries to determine user's language using URL language prefix
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'cosomis.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': ['cosomis/templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',

                'cosomis.services.overall_variables' #Called the function which presents the globals variables
            ],
        },
    },
]

WSGI_APPLICATION = 'cosomis.wsgi.application'


# Database
# https://docs.djangoproject.com/en/1.8/ref/settings/#databases

EXTERNAL_DATABASE_NAME = 'cdd'

DATABASES = {
    'default': env.db(),
    EXTERNAL_DATABASE_NAME: env.db('LEGACY_DATABASE_URL')
}


# Internationalization
# https://docs.djangoproject.com/en/1.8/topics/i18n/

LANGUAGE_CODE = 'fr'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True

LOCALE_PATHS = [os.path.join(BASE_DIR, 'locale')]

LANGUAGES = [
    ('en', _('English')), 
    ('fr', _('French')), 
]

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.8/howto/static-files/

STATIC_URL = '/static/'

STATICFILES_DIRS = [
    BASE_DIR / "static",
]

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

LOGIN_URL = '/'
LOGIN_REDIRECT_URL = 'dashboard:dashboard'
LOGOUT_REDIRECT_URL = '/'


# Mapbox
MAPBOX_ACCESS_TOKEN = env('MAPBOX_ACCESS_TOKEN')

DIAGNOSTIC_MAP_LATITUDE = env('DIAGNOSTIC_MAP_LATITUDE')

DIAGNOSTIC_MAP_LONGITUDE = env('DIAGNOSTIC_MAP_LONGITUDE')

DIAGNOSTIC_MAP_ZOOM = env('DIAGNOSTIC_MAP_ZOOM')

DIAGNOSTIC_MAP_WS_BOUND = env('DIAGNOSTIC_MAP_WS_BOUND')

DIAGNOSTIC_MAP_EN_BOUND = env('DIAGNOSTIC_MAP_EN_BOUND')

DIAGNOSTIC_MAP_ISO_CODE = env('DIAGNOSTIC_MAP_ISO_CODE')


# CouchDB

NO_SQL_USER = env('NO_SQL_USER')

NO_SQL_PASS = env('NO_SQL_PASS')

NO_SQL_URL = env('NO_SQL_URL')

COUCHDB_DATABASE = env('COUCHDB_DATABASE')

COUCHDB_DATABASE_ADMINISTRATIVE_LEVEL = env('COUCHDB_DATABASE_ADMINISTRATIVE_LEVEL')

COUCHDB_ATTACHMENT_DATABASE = env('COUCHDB_ATTACHMENT_DATABASE')

COUCHDB_GRM_DATABASE = env('COUCHDB_GRM_DATABASE')

COUCHDB_GRM_ATTACHMENT_DATABASE = env('COUCHDB_GRM_ATTACHMENT_DATABASE')


# S3
DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'

AWS_STORAGE_BUCKET_NAME = env('S3_BUCKET')

AWS_ACCESS_KEY_ID = env('S3_ACCESS')

AWS_SECRET_ACCESS_KEY = env('S3_SECRET')

#REST API
REST_FRAMEWORK = {
    # https://github.com/tfranzel/drf-spectacular
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}


# Default primary key field type
# https://docs.djangoproject.com/en/4.0/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'