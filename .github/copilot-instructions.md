# SupplyHub project guidance

- This is a Django project. Keep project settings and root URL configuration in `supplyhub/`; keep application views, models, tests, and templates in `core/` or `dashboard/`.
- SupplyHub is a responsive B2B wholesale marketplace. Homepage campaigns are managed through Django admin and the staff dashboard links to campaign controls. Featured products, recent arrivals, and product offers are derived from the catalog.
- Sellers apply through the seller centre and need admin approval before their shop or products are public. Seller profiles, product details/media/price tiers, quote assignments, and per-seller order statuses are separate models in the configured project database. Keep seller data access scoped to the authenticated seller.
- Sellers control buyer-visible product detail fields. If a seller hides direct pricing, keep the listing quote-only in both the interface and the server-side cart/checkout endpoints.
- Preserve existing customer workflows for authentication, wholesale MOQ/sample orders, carts, wishlists, and bulk quote requests when changing the storefront.
- Install Python dependencies from `requirements.txt`. Use SQLite for local development and apply schema changes with `python manage.py migrate`.
- Verify changes with `python manage.py check` and relevant focused tests; the full suite is run with `python manage.py test`.
- Do not commit `.env` files, credentials, local databases, static build output, or virtual environments.
