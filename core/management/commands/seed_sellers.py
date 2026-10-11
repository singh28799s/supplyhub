from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils.text import slugify

from core.models import SellerProfile


class Command(BaseCommand):
    help = "Create 50 fictional seller profiles without duplicating them."

    def handle(self, *args, **options):
        User = get_user_model()

        sellers = [
            ("Jaipur Handicrafts", "Aarav Sharma", "Jaipur", "Handicrafts"),
            ("Royal Textile House", "Priya Verma", "Jaipur", "Textiles"),
            ("Desert Ceramic Works", "Rohan Mehta", "Jodhpur", "Ceramics"),
            ("Marwar Leather Goods", "Neha Singh", "Jodhpur", "Leather Goods"),
            ("Pink City Packaging", "Karan Gupta", "Jaipur", "Packaging"),
            ("Aravali Metal Crafts", "Simran Kaur", "Alwar", "Metal Products"),
            ("Thar Organic Foods", "Vikram Joshi", "Bikaner", "Food Products"),
            ("Blue Pottery Studio", "Ananya Jain", "Jaipur", "Pottery"),
            ("Royal Furniture Makers", "Mohit Yadav", "Kota", "Furniture"),
            ("Desert Home Decor", "Kavya Agarwal", "Udaipur", "Home Decor"),
        ]

        # Generate 50 distinct fictional businesses from 10 base names.
        records = []
        for i in range(50):
            company, contact, city, business_type = sellers[i % len(sellers)]
            number = i + 1
            records.append({
                "company_name": f"{company} {number:02d}",
                "contact_name": contact,
                "city": city,
                "business_type": business_type,
                "slug": slugify(f"{company}-{number:02d}"),
                "email": f"sample.seller{number:02d}@example.com",
            })

        created = 0
        skipped = 0

        with transaction.atomic():
            for data in records:
                username = data["email"]

                user, user_created = User.objects.get_or_create(
                    username=username,
                    defaults={
                        "email": data["email"],
                        "first_name": data["contact_name"].split()[0],
                    },
                )

                if user_created:
                    user.set_unusable_password()
                    user.save(update_fields=["password"])

                profile, profile_created = SellerProfile.objects.get_or_create(
                    slug=data["slug"],
                    defaults={
                        "user": user,
                        "company_name": data["company_name"],
                        "contact_name": data["contact_name"],
                        "email": data["email"],
                        "phone": "",
                        "country": "India",
                        "city": data["city"],
                        "business_type": data["business_type"],
                        "years_in_business": 3,
                        "description": (
                            f"Fictional sample seller based in {data['city']}. "
                            "Created for SupplyHub development testing."
                        ),
                        "customization_capabilities": (
                            "Custom packaging and bulk order support"
                        ),
                        "certifications": "Sample data - not verified",
                    },
                )

                if profile_created:
                    created += 1
                else:
                    skipped += 1

        self.stdout.write(self.style.SUCCESS(
            f"Finished. Created: {created}, skipped existing slugs: {skipped}"
        ))
        self.stdout.write(
            f"Total seller profiles in database: {SellerProfile.objects.count()}"
        )
