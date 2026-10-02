"""WSGI config for SupplyHub."""
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "supplyhub.settings")
application = get_wsgi_application()
