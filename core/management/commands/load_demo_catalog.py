from django.core.management.base import BaseCommand

from core.models import Category, Product


class Command(BaseCommand):
    help = "Load the starter catalog values shown in the SupplyHub homepage template."

    def handle(self, *args, **options):
        categories = [
            ("Jute Bags", "👜"),
            ("Jute Packaging", "📦"),
            ("Home Decor", "🧺"),
            ("Gift Items", "🎁"),
            ("Industrial", "🏭"),
            ("Customized", "🏷️"),
            ("Eco Friendly", "♻️"),
            ("Handicrafts", "🪢"),
        ]
        category_objects = {}
        for order, (name, icon) in enumerate(categories):
            category, _ = Category.objects.update_or_create(
                name=name,
                defaults={"icon": icon, "sort_order": order},
            )
            category_objects[name] = category

        demo_products = [
            ("Jute Shopping Bag", "Jute Bags", "25.00", "piece", 100, "Best Seller", "👜"),
            ("Jute Packaging Bag", "Jute Packaging", "35.00", "piece", 100, "Bulk Discount", "📦"),
            ("Jute Storage Basket", "Home Decor", "180.00", "piece", 20, "Eco Friendly", "🧺"),
            ("Jute Promotional Bag", "Jute Bags", "40.00", "piece", 500, "Custom Logo", "🎒"),
            ("Jute Table Runner", "Home Decor", "120.00", "piece", 50, "New Arrival", "🧶"),
            ("Jute Fabric Roll", "Industrial", "75.00", "meter", 100, "Industrial", "🪢"),
            ("Jute Gift Box", "Gift Items", "90.00", "piece", 50, "Popular", "🎁"),
            ("Premium Jute Tote Bag", "Jute Bags", "65.00", "piece", 100, "Premium", "🛍️"),
        ]
        for name, category_name, price, unit, moq, badge, icon in demo_products:
            Product.objects.update_or_create(
                name=name,
                defaults={
                    "category": category_objects[category_name],
                    "price": price,
                    "unit": unit,
                    "minimum_order_quantity": moq,
                    "badge": badge,
                    "icon": icon,
                    "is_featured": True,
                    "is_active": True,
                },
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Catalog ready: {Category.objects.count()} categories, "
                f"{Product.objects.count()} products. Demo prices/MOQs need review."
            )
        )
