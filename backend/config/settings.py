"""type-10022026-Maurice: Secure PostgreSQL-backed Django configuration."""
import os
import tempfile
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "unsafe-local-key-for-tests")
DEBUG = os.environ.get("DJANGO_DEBUG", "0") == "1"
ALLOWED_HOSTS = [h for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h]
ROOT_URLCONF = "backend.config.urls"
WSGI_APPLICATION = "backend.config.wsgi.application"
INSTALLED_APPS = ["django.contrib.auth", "django.contrib.contenttypes", "django.contrib.sessions", "oauth2_provider", "rest_framework", "backend.users"]
MIDDLEWARE = ["django.middleware.security.SecurityMiddleware", "django.contrib.sessions.middleware.SessionMiddleware", "django.middleware.common.CommonMiddleware", "backend.users.correlation.CorrelationMiddleware", "django.middleware.csrf.CsrfViewMiddleware", "django.middleware.clickjacking.XFrameOptionsMiddleware", "django.contrib.auth.middleware.AuthenticationMiddleware", "backend.users.middleware.InactivityMiddleware"]
DATABASES = {"default": {"ENGINE": "django.db.backends.postgresql", "NAME": os.environ.get("POSTGRES_DB", "ehr"), "USER": os.environ.get("POSTGRES_USER", "ehr"), "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""), "HOST": os.environ.get("POSTGRES_HOST", "127.0.0.1"), "PORT": os.environ.get("POSTGRES_PORT", "5432")}}
AUTH_USER_MODEL = "users.User"
SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_HTTPONLY = False
CSRF_TRUSTED_ORIGINS = [origin for origin in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "https://localhost,https://127.0.0.1").split(",") if origin]
SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", "31536000")) if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
SECURE_SSL_REDIRECT = os.environ.get("DJANGO_SECURE_SSL_REDIRECT", "0") == "1"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
DATA_UPLOAD_MAX_MEMORY_SIZE = int(os.environ.get("DATA_UPLOAD_MAX_MEMORY_SIZE", str(1024 * 1024)))
DATA_UPLOAD_MAX_NUMBER_FIELDS = 200
SESSION_INACTIVITY_SECONDS = int(os.environ.get("SESSION_INACTIVITY_SECONDS", "900"))
WEBAUTHN_RP_ID = os.environ.get("WEBAUTHN_RP_ID", "localhost")
WEBAUTHN_ORIGIN = os.environ.get("WEBAUTHN_ORIGIN", "https://localhost")
WEBAUTHN_CHALLENGE_TTL_SECONDS = int(os.environ.get("WEBAUTHN_CHALLENGE_TTL_SECONDS", "60"))
SMS_RECOVERY_TTL_SECONDS = int(os.environ.get("SMS_RECOVERY_TTL_SECONDS", "300"))
SMS_RECOVERY_MAX_ATTEMPTS = int(os.environ.get("SMS_RECOVERY_MAX_ATTEMPTS", "5"))
EXPORT_ROOT = os.environ.get("EHR_EXPORT_ROOT", os.path.join(tempfile.gettempdir(), "ehr-exports"))
POPULATION_EXPORT_ROOT = os.environ.get("EHR_POPULATION_EXPORT_ROOT", os.path.join(tempfile.gettempdir(), "ehr-population-exports"))
POPULATION_EXPORT_KEY = os.environ.get("EHR_POPULATION_EXPORT_KEY", "")
POPULATION_EXPORT_CAP = int(os.environ.get("EHR_POPULATION_EXPORT_CAP", "10000"))
POPULATION_EXPORT_MAX_BYTES = 100 * 1024 * 1024
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
REST_FRAMEWORK = {"DEFAULT_AUTHENTICATION_CLASSES": ["backend.users.authentication.OAuthBearerOrSessionAuthentication"]}
OAUTH2_PROVIDER = {
    "SCOPES": {"openid": "OpenID", "fhirUser": "FHIR user identity", "patient/Patient.r": "Read Patient", "patient/Patient.s": "Select one Patient", "patient/MedicationRequest.r": "Read MedicationRequest", "patient/AllergyIntolerance.r": "Read AllergyIntolerance", "patient/Condition.r": "Read Condition", "patient/Observation.r": "Read Observation", "patient/Device.r": "Read Device", "patient/FamilyMemberHistory.r": "Read FamilyMemberHistory", "patient/Questionnaire.r": "Read Questionnaire", "patient/QuestionnaireResponse.r": "Read QuestionnaireResponse"},
    "DEFAULT_SCOPES": "openid fhirUser",
    "ACCESS_TOKEN_EXPIRE_SECONDS": 300,
    "REFRESH_TOKEN_EXPIRE_SECONDS": 86400,
    "ROTATE_REFRESH_TOKEN": True,
    "HASH_CLIENT_SECRETS": True,
    "COMPLIANT_BCP_RFC9700_TOKEN_STORAGE": True,
}
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"json": {"()": "backend.users.logging.JsonConsoleFormatter"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "json"}},
    "loggers": {"ehr": {"handlers": ["console"], "level": "INFO", "propagate": True}},
}
