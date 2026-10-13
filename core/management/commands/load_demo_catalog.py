from django.core.management.base import BaseCommand

from core.models import Category, Product


class Command(BaseCommand):
    help = "Add inactive, clearly labelled demo categories and products for review."

    def handle(self, *args, **options):
        categories = [
            "Apparel & Textiles",
            "Automotive",
            "Electronics",
            "Food & Beverage",
            "Health & Beauty",
            "Home & Kitchen",
            "Industrial Supplies",
            "Office Supplies",
            "Packaging",
            "Sports & Outdoors",
            "Toys & Games",
            "Agriculture",
        ]
        category_objects = {}
        for order, name in enumerate(categories):
            category, _ = Category.objects.update_or_create(
                name=f"DEMO - {name}",
                defaults={"is_active": False, "sort_order": order},
            )
            category_objects[name] = category

        demo_products = [
            ("Cotton Tote Bag", "Apparel & Textiles", "180.00", "piece", 100),
            ("Reusable Cotton Apron", "Apparel & Textiles", "220.00", "piece", 50),
            ("Automotive Oil Filter", "Automotive", "250.00", "piece", 100),
            ("Car Care Microfiber Cloth", "Automotive", "45.00", "piece", 500),
            ("USB-C Charging Cable", "Electronics", "90.00", "piece", 200),
            ("LED Desk Lamp", "Electronics", "450.00", "piece", 30),
            ("Stainless Steel Water Bottle", "Food & Beverage", "160.00", "piece", 100),
            ("Paper Food Container", "Food & Beverage", "4.00", "piece", 1000),
            ("Herbal Soap Bar", "Health & Beauty", "35.00", "piece", 200),
            ("Reusable Cosmetic Pouch", "Health & Beauty", "75.00", "piece", 100),
            ("Stackable Storage Basket", "Home & Kitchen", "140.00", "piece", 40),
            ("Cotton Kitchen Towel Set", "Home & Kitchen", "110.00", "set", 50),
            ("Protective Work Gloves", "Industrial Supplies", "55.00", "pair", 100),
            ("Reusable Safety Helmet", "Industrial Supplies", "320.00", "piece", 25),
            ("Recycled Paper Notebook", "Office Supplies", "48.00", "piece", 100),
            ("Thermal Shipping Label Roll", "Office Supplies", "130.00", "roll", 50),
            ("Corrugated Shipping Box", "Packaging", "18.00", "piece", 500),
            ("Kraft Paper Carry Bag", "Packaging", "7.00", "piece", 1000),
            ("Resistance Band Set", "Sports & Outdoors", "190.00", "set", 40),
            ("Insulated Picnic Mat", "Sports & Outdoors", "350.00", "piece", 20),
            ("Wooden Building Block Set", "Toys & Games", "260.00", "set", 30),
            ("Coloring Activity Book", "Toys & Games", "32.00", "piece", 200),
            ("Drip Irrigation Connector", "Agriculture", "12.00", "piece", 500),
            ("Seedling Nursery Tray", "Agriculture", "65.00", "piece", 100),
        ]
        demo_notice = (
            "DEMO DATA: Replace this description, price and minimum order quantity "
            "with verified business information before activating this listing."
        )
        for name, category_name, price, unit, moq in demo_products:
            Product.objects.update_or_create(
                name=f"DEMO - {name}",
                defaults={
                    "category": category_objects[category_name],
                    "price": price,
                    "unit": unit,
                    "minimum_order_quantity": moq,
                    "description": demo_notice,
                    "is_featured": False,
                    "is_active": False,
                },
            )

        self.stdout.write(
            self.style.SUCCESS(
                "Added or updated 12 inactive demo categories and 24 inactive demo "
                "products. Review prices, MOQs, descriptions, and images before "
                "activating them."
            )
        )
