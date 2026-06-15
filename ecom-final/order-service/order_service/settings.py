import os, dj_database_url
from decouple import config
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SECRET_KEY = config('SECRET_KEY', default='order-secret'); DEBUG = config('DEBUG', default=False, cast=bool)
ALLOWED_HOSTS = ['*']
INSTALLED_APPS = ['django.contrib.admin','django.contrib.auth','django.contrib.contenttypes','django.contrib.sessions','django.contrib.messages','django.contrib.staticfiles','rest_framework','app']
MIDDLEWARE = ['django.middleware.security.SecurityMiddleware','django.contrib.sessions.middleware.SessionMiddleware','django.middleware.common.CommonMiddleware','django.contrib.auth.middleware.AuthenticationMiddleware','django.contrib.messages.middleware.MessageMiddleware']
ROOT_URLCONF = 'order_service.urls'; WSGI_APPLICATION = 'order_service.wsgi.application'
TEMPLATES = [{'BACKEND':'django.template.backends.django.DjangoTemplates','DIRS':[],'APP_DIRS':True,'OPTIONS':{'context_processors':['django.template.context_processors.request','django.contrib.auth.context_processors.auth','django.contrib.messages.context_processors.messages']}}]
DATABASES = {'default': dj_database_url.parse(config('DATABASE_URL', default='sqlite:///db.sqlite3'), conn_max_age=600)}
REST_FRAMEWORK = {'DEFAULT_PERMISSION_CLASSES':['rest_framework.permissions.AllowAny'],'DEFAULT_RENDERER_CLASSES':['rest_framework.renderers.JSONRenderer']}
CART_SERVICE_URL = config('CART_SERVICE_URL', default='http://cart-service:8002')
PAYMENT_SERVICE_URL = config('PAYMENT_SERVICE_URL', default='http://payment-service:8004')
REDIS_URL = config('REDIS_URL', default='redis://redis:6379/0')
ORDER_EVENTS_CHANNEL = config('ORDER_EVENTS_CHANNEL', default='order.events')
STATIC_URL = '/static/'; STATIC_ROOT = os.path.join(BASE_DIR,'staticfiles')
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'; LANGUAGE_CODE='vi'; TIME_ZONE='Asia/Ho_Chi_Minh'; USE_TZ=True
