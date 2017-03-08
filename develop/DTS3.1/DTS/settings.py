# -*- coding: utf-8 -*-
from __future__ import absolute_import
import os
from datetime import timedelta

from celery.schedules import crontab
from kombu import Exchange, Queue


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SECRET_KEY = '@bh0d#+apvb3a5=!fd0wvs(_9-o9i*i!567ku^l5b1w@*z4o=b'

DEBUG = True

ALLOWED_HOSTS = ['dts.100credit.com', '127.0.0.1', 'localhost']

LOGIN_URL = '/accounts/login/'

INSTALLED_APPS = (
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'bootstrap3',
    'customer',
    'analyst',
    'account',
    'checker',
)

MIDDLEWARE_CLASSES = (
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.auth.middleware.SessionAuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django.middleware.security.SecurityMiddleware',
)

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            os.path.join(BASE_DIR, 'templates'),
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

FILE_UPLOAD_HANDLERS = (
    "django.core.files.uploadhandler.TemporaryFileUploadHandler",
)

DATABASES = {
    'default': {
         'ENGINE': 'django.db.backends.mysql',
         'NAME': 'dts',
         'USER': 'dts',
         'PASSWORD': '123456',
         'HOST': 'localhost',
         'PORT': '3306',
    }
}

WSGI_APPLICATION = 'DTS.wsgi.application'

ROOT_URLCONF = 'DTS.urls'

# 验证码字体
FONT_TYPE_PATH = os.path.join(BASE_DIR, 'static/fonts/ae_AlArabiya.ttf')

# TMP_PATH = '/opt/django_project/all_file/DTS/tmp/'
TMP_PATH = '/tmp/'

# STATIC_ROOT = os.path.join(BASE_DIR, 'static_root')
STATIC_URL = '/static/'

STATICFILES_DIRS = (
    os.path.join(BASE_DIR, 'static'),
)

# MEDIA_ROOT = '/opt/django_project/all_file/DTS/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

MEDIA_URL = '/media/'

LANGUAGE_CODE = 'zh-hans'

# SITE_ID = 1

TIME_ZONE = 'Asia/Shanghai'

USE_I18N = True

USE_L10N = False

USE_TZ = False

DATETIME_FORMAT = 'Y-m-d H:i:s'


EMAIL_HOST = '117.121.48.85'
EMAIL_HOST_USER = 'dts@100credit.com'
EMAIL_HOST_PASSWORD = '018660'
EMAIL_PORT = 25
EMAIL_USE_TLS = True


LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '%(asctime)s [DTS%(name)s] [%(threadName)s] %(levelname)s [%(pathname)s--line:%(lineno)d] %(message)s'
        },
        'simple': {
            'format': '[%(asctime)s] %(levelname)s %(name)s : %(message)s'
        },
    },
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse',
        },
        'require_debug_true': {
            '()': 'django.utils.log.RequireDebugTrue',
        },
    },
    'handlers': {
        'null': {
            'class': 'logging.NullHandler',
        },
        'console': {
            'level': 'DEBUG',
            'filters': ['require_debug_true'],
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        'error': {
            'level': 'ERROR',
            # 'filters': ['require_debug_false'],
            'class': 'logging.FileHandler',
            'filename': os.path.join(BASE_DIR, 'error.log'),
            'formatter': 'verbose',
        },
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(BASE_DIR, 'info.log'),
            'maxBytes': 1024*1024*10,
            'backupCount': 8,
            'formatter': 'simple',
        }
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'propagate': True,
        },
        'django.request': {
            'handlers': ['error'],
            'level': 'ERROR',
            'propagate': True,
        },
        'django.security': {
            'handlers': ['error'],
            'level': 'ERROR',
            'propagate': True,
        },
        'py.warnings': {
            'handlers': ['console'],
        },
        'DTS': {
            'handlers': ['file'],
            'level': 'INFO',
        }
    }
}


BOOTSTRAP3 = {
    'jquery_url': '//static/jquery/jquery.min.js',
    'base_url': '//static/bootstrap/',
    'css_url': None,
    'theme_url': None,
    'javascript_url': None,
    'javascript_in_head': False,
    'include_jquery': False,
    'horizontal_label_class': 'col-md-3',
    'horizontal_field_class': 'col-md-9',
    'set_required': True,
    'set_disabled': False,
    'set_placeholder': True,
    'required_css_class': '',
    'error_css_class': 'has-error',
    'success_css_class': 'has-success',
    'formset_renderers':{
        'default': 'bootstrap3.renderers.FormsetRenderer',
    },
    'form_renderers': {
        'default': 'bootstrap3.renderers.FormRenderer',
    },
    'field_renderers': {
        'default': 'bootstrap3.renderers.FieldRenderer',
        'inline': 'bootstrap3.renderers.InlineFieldRenderer',
    },
}


# BROKER_URL = 'amqp://test:123@127.0.0.1:5672/testvhost'
# CELERYD_FORCE_EXECV = True
# CELERY_IGNORE_RESULT = True
# CELERY_DISABLE_RATE_LIMITS = True
# CELERY_CREATE_MISSING_QUEUES = True
# CELERY_ENABLE_UTC = True
# CELERY_ACCEPT_CONTENT = ['json']
# CELERY_TASK_SERIALIZER = 'json'
# CELERY_TIMEZONE = 'Asia/Shanghai'
#
# CELERYBEAT_SCHEDULE = {
#     # 'every-50-seconds': {
#     #     'task': 'taskfor_scan',
#     #     'schedule': timedelta(seconds=50),
#     #     'args': ()
#     # },
#     'every-3-minute': {
#         'task': 'taskfor_scan',
#         'schedule': crontab(minute='*/3'),
#         'args': ()
#     },
# }
#
#
# CELERY_QUEUES = (
#     Queue('ice', Exchange('taskfor_ice'), routing_key='taskfor_ice'),
#     Queue('hx', Exchange('taskfor_hx'), routing_key='taskfor_hx'),
#     Queue('scan', Exchange('taskfor_scan'), routing_key='taskfor_scan'),
#     # Queue('mail', Exchange('taskfor_mail'), routing_key='taskfor_mail'),
# )
#
# CELERY_ROUTES = {
#     'taskfor_ice': {'queue': 'taskfor_ice', 'routing_key': 'taskfor_ice'},
#     'taskfor_hx': {'queue': 'taskfor_hx', 'routing_key': 'taskfor_hx'},
#     'taskfor_scan': {'queue': 'taskfor_scan', 'routing_key': 'taskfor_scan'},
#     # 'taskfor_mail': {'queue': 'taskfor_mail', 'routing_key': 'taskfor_mail'},
# }
