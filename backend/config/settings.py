"""type-10022026-Maurice: Secure PostgreSQL-backed Django configuration."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "unsafe-local-key-for-tests")
DEBUG = os.environ.get("DJANGO_DEBUG", "0") == "1"
ALLOWED_HOSTS = [h for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h]
ROOT_URLCONF = "backend.config.urls"
WSGI_APPLICATION = "backend.config.wsgi.application"
INSTALLED_APPS = ["django.contrib.auth", "django.contrib.contenttypes", "django.contrib.sessions", "rest_framework", "backend.users"]
MIDDLEWARE = ["django.middleware.security.SecurityMiddleware", "django.contrib.sessions.middleware.SessionMiddleware", "django.middleware.common.CommonMiddleware", "backend.users.correlation.CorrelationMiddleware", "django.middleware.csrf.CsrfViewMiddleware", "django.contrib.auth.middleware.AuthenticationMiddleware", "backend.users.middleware.InactivityMiddleware"]
DATABASES = {"default": {"ENGINE": "django.db.backends.postgresql", "NAME": os.environ.get("POSTGRES_DB", "ehr"), "USER": os.environ.get("POSTGRES_USER", "ehr"), "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""), "HOST": os.environ.get("POSTGRES_HOST", "127.0.0.1"), "PORT": os.environ.get("POSTGRES_PORT", "5432")}}
AUTH_USER_MODEL = "users.User"
SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = not DEBUG
SESSION_INACTIVITY_SECONDS = int(os.environ.get("SESSION_INACTIVITY_SECONDS", "900"))
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
REST_FRAMEWORK = {"DEFAULT_AUTHENTICATION_CLASSES": ["backend.users.authentication.SessionAuthenticationWithChallenge"]}
LOGGING = {"version": 1, "disable_existing_loggers": False, "handlers": {"console": {"class": "logging.StreamHandler"}}, "loggers": {"ehr": {"handlers": ["console"], "level": "INFO", "propagate": True}}}
