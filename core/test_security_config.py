import os
import subprocess
import sys
from pathlib import Path

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.test import TestCase

from core.forms import SellerRegistrationForm


class SecurityConfigurationTests(TestCase):
    def run_settings_import(self, overrides):
        environment = os.environ.copy()
        environment.update(
            {
                "DJANGO_SETTINGS_MODULE": "supplyhub.settings",
                "DJANGO_ENV": "production",
                "DEBUG": "False",
                "RENDER": "",
                "SECRET_KEY": "test-only-secret-key",
                "ALLOWED_HOSTS": "shop.example.com",
                "CSRF_TRUSTED_ORIGINS": "https://shop.example.com",
                "DATABASE_URL": (
                    "postgresql://test:test@localhost:5432/test"
                ),
                "CLOUDINARY_CLOUD_NAME": "test-cloud",
                "CLOUDINARY_API_KEY": "test-key",
                "CLOUDINARY_API_SECRET": "test-secret",
                "EMAIL_BACKEND": "django.core.mail.backends.smtp.EmailBackend",
                "EMAIL_HOST": "smtp.example.com",
                "EMAIL_HOST_USER": "seller@example.com",
                "EMAIL_HOST_PASSWORD": "test-only-password",
                "EMAIL_USE_TLS": "True",
                "EMAIL_USE_SSL": "False",
            }
        )
        environment.update(overrides)
        return subprocess.run(
            [sys.executable, "-c", "import supplyhub.settings"],
            cwd=Path(__file__).resolve().parents[1],
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_render_cannot_start_with_debug_enabled(self):
        result = self.run_settings_import(
            {
                "DJANGO_ENV": "development",
                "DEBUG": "True",
                "RENDER": "true",
            }
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DEBUG must be False", result.stderr)

    def test_production_rejects_wildcard_allowed_hosts(self):
        result = self.run_settings_import({"ALLOWED_HOSTS": "*"})

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("must list specific hostnames", result.stderr)

    def test_mail_tls_and_ssl_cannot_both_be_enabled(self):
        result = self.run_settings_import(
            {"EMAIL_USE_TLS": "True", "EMAIL_USE_SSL": "True"}
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("cannot both be enabled", result.stderr)

    def test_new_passwords_require_at_least_twelve_characters(self):
        form = SellerRegistrationForm(
            data={
                "username": "shortpasswordseller",
                "email": "seller@example.com",
                "company_name": "Short Password Seller",
                "contact_name": "Seller Contact",
                "phone": "+919876543210",
                "country": "India",
                "city": "Delhi",
                "business_type": "manufacturer",
                "years_in_business": "1",
                "password1": "ShortPass1!",
                "password2": "ShortPass1!",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("password2", form.errors)

        with self.assertRaises(ValidationError):
            validate_password("ShortPass1!")
