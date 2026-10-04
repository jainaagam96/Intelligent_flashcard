import os
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse
from dotenv import load_dotenv
from django.core.exceptions import ImproperlyConfigured
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')

DEBUG = os.getenv('DEBUG', '0') == '1'
ALLOW_PUBLIC_REGISTRATION = os.getenv(
    'ALLOW_PUBLIC_REGISTRATION', '1' if DEBUG else '0'
) == '1'
SECRET_KEY = os.getenv('SECRET_KEY', 'upscEasy-local-dev-key')
if not DEBUG and SECRET_KEY in {'', 'upscEasy-local-dev-key', 'change-me-for-local-use'}:
    raise RuntimeError('Set a unique SECRET_KEY in the production environment.')

ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv('ALLOWED_HOSTS', '127.0.0.1,localhost').split(',')
    if host.strip()
]
RENDER_EXTERNAL_HOSTNAME = os.getenv('RENDER_EXTERNAL_HOSTNAME', '').strip()
if RENDER_EXTERNAL_HOSTNAME and RENDER_EXTERNAL_HOSTNAME not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.getenv('CSRF_TRUSTED_ORIGINS', '').split(',')
    if origin.strip()
]
if RENDER_EXTERNAL_HOSTNAME:
    render_origin = f'https://{RENDER_EXTERNAL_HOSTNAME}'
    if render_origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(render_origin)
INSTALLED_APPS=['django.contrib.admin','django.contrib.auth','django.contrib.contenttypes','django.contrib.sessions','django.contrib.messages','django.contrib.staticfiles','rest_framework','core']
MIDDLEWARE=['django.middleware.security.SecurityMiddleware','whitenoise.middleware.WhiteNoiseMiddleware','django.contrib.sessions.middleware.SessionMiddleware','django.middleware.common.CommonMiddleware','django.middleware.csrf.CsrfViewMiddleware','django.contrib.auth.middleware.AuthenticationMiddleware','django.contrib.messages.middleware.MessageMiddleware']
ROOT_URLCONF='upsc_easy.urls'
TEMPLATES=[{'BACKEND':'django.template.backends.django.DjangoTemplates','DIRS':[BASE_DIR/'core/templates'],'APP_DIRS':True,'OPTIONS':{'context_processors':['django.template.context_processors.request','django.contrib.auth.context_processors.auth','django.contrib.messages.context_processors.messages']}}]
WSGI_APPLICATION='upsc_easy.wsgi.application'
DB_URL = os.getenv('DB_URL') or os.getenv('DATABASE_URL', '')
if DB_URL:
    parsed_db_url = urlparse(DB_URL)
    if parsed_db_url.scheme not in {'postgres', 'postgresql'}:
        raise ImproperlyConfigured('DB_URL must be a PostgreSQL connection URL.')
    if not parsed_db_url.hostname or not parsed_db_url.path.strip('/'):
        raise ImproperlyConfigured('DB_URL must include a database host and database name.')
    db_query = parse_qs(parsed_db_url.query)
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': unquote(parsed_db_url.path.lstrip('/')),
            'USER': unquote(parsed_db_url.username or ''),
            'PASSWORD': unquote(parsed_db_url.password or ''),
            'HOST': parsed_db_url.hostname,
            'PORT': parsed_db_url.port or 5432,
            'OPTIONS': {
                'sslmode': db_query.get('sslmode', ['require'])[0],
            },
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': os.getenv('SQLITE_PATH') or str(BASE_DIR / 'db.sqlite3'),
        }
    }
LANGUAGE_CODE='en-us'; TIME_ZONE='Asia/Kolkata'; USE_I18N=True; USE_TZ=True
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'core/static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedStaticFilesStorage'},
}
SECURE_SSL_REDIRECT = os.getenv('SECURE_SSL_REDIRECT', '0') == '1'
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
DEFAULT_AUTO_FIELD='django.db.models.BigAutoField'
OPENAI_API_KEY=os.getenv('OPENAI_API_KEY',''); OPENAI_MODEL=os.getenv('OPENAI_MODEL','gpt-5.5')
REST_FRAMEWORK={'DEFAULT_PERMISSION_CLASSES':['rest_framework.permissions.IsAuthenticated'],'DEFAULT_AUTHENTICATION_CLASSES':['rest_framework.authentication.SessionAuthentication']}
