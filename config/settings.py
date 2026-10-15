"""
Django settings for the AI-Based Sudoku Solver project.

Django project package: config
Application package:     sudoku

Phase 1 note
------------
This project intentionally uses a minimal Django configuration. There is no
database-backed feature in the initial implementation, so the default contrib
apps (admin, auth, sessions, messages, contenttypes) are deliberately not
enabled. A lightweight SQLite entry is kept only so that Django's test runner
can create and destroy a throwaway test database. The application itself does
not persist any data.

For more information on this file, see:
    https://docs.djangoproject.com/en/5.2/topics/settings/
For the full list of settings and their values, see:
    https://docs.djangoproject.com/en/5.2/ref/settings/
"""

from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# SECURITY WARNING: keep the secret key used in production secret!
# This key is a generated development key and is acceptable for a local,
# academic project. Read it from an environment variable before deployment.
SECRET_KEY = "django-insecure-%qq39pde(hl_7_)2t=!@mppf)ol4_x)(u)1#^=)wp8!b@2&87c"

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

# Allow the local development server on every common host form.
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]"]


# Application definition

INSTALLED_APPS = [
    "django.contrib.staticfiles",
    "sudoku",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases
#
# Phase 1 does not store any data. This SQLite definition exists only because
# Django's test runner expects a database to be configured; the test database
# is created and destroyed automatically and is never used by the app itself.

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = "static/"


# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
