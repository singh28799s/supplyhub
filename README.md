# SupplyHub

A Django B2B catalog starter. Catalog categories and wholesale products are stored in the local SQLite database and managed through Django admin.

## Run on Windows (PowerShell)

From the project folder:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py load_demo_catalog
python manage.py runserver
```

Open `http://127.0.0.1:8000/` in your browser. Create an admin account with `python manage.py createsuperuser`, then manage categories and products at `http://127.0.0.1:8000/admin/`.

The separate staff dashboard is available at `http://127.0.0.1:8000/staff-dashboard/` after signing in with a staff or superuser account. It summarizes the catalog, orders, pending quote requests, suppliers, product offers, and store settings. Regular customer accounts cannot access it.

Customers can create an account at `/register/` and log in at `/login/`. Registration creates a regular customer account; it does not grant admin access. Logout uses the account menu on the homepage.

The demo command is safe to run repeatedly and adds the starter products from the original homepage template. **Its sample prices and minimum order quantities are placeholders; review them before showing the catalog to customers.** Add or edit catalog entries in Django admin. Run checks and tests with `python manage.py check` and `python manage.py test`.

## Customer ordering

Customers can add products to the session cart, adjust quantities (subject to each product's MOQ), and submit delivery details at checkout. They may order as guests; signed-in customers can see their orders from the **Orders** link. New orders are saved with a pending-confirmation status and can be reviewed/updated in Django admin. This starter workflow does not collect payment or send email; confirm sample prices and shipping with the customer before fulfilling an order.

To offer samples, set a product's **Sample price** and **Sample quantity** in Django admin. Buyers may order that exact sample quantity at the sample price, or order the wholesale MOQ or more at the wholesale price. Quantities between the sample quantity and MOQ are rejected. Sample prices are left unset until you enter your actual price.

## Quotes, suppliers, and store settings

Buyers can submit a bulk/custom quote request from the storefront. Staff can review it under **Quotations / RFQ** in the dashboard or in Django admin, enter a quoted unit price and response, and update its status. Signed-in customers can see their quote history. Suppliers are managed from the dashboard/Admin and can be assigned to products.

Store branding, contact details, shipping fee, free-shipping threshold, and offline checkout methods (cash on delivery/bank transfer) are configurable in the dashboard. Orders save the selected offline payment method and shipping amount. **No card/UPI payment gateway, bank verification, inventory deduction, or shipping carrier integration is configured**; bank-transfer orders require manual confirmation. Email notifications are automated but require SMTP configuration for real delivery.

Order and quote notifications are queued after the database transaction commits. Locally, Django prints email contents in the runserver terminal; configure `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL`, and `SUPPLYHUB_ADMIN_EMAIL` as environment variables to send real SMTP email. Set `EMAIL_USE_TLS` or `EMAIL_USE_SSL` to match the mail provider. Store support email is also used for staff notifications when no `SUPPLYHUB_ADMIN_EMAIL` is set. Delivery depends on valid SMTP configuration.

Product promotional prices can be set through the product admin's **Offer price** field. The offer must be below the wholesale price.

## GitHub upload

Git is initialized in this folder. Create an empty repository on GitHub, then connect it and push:

```powershell
git add .
git commit -m "Initial Django project"
git branch -M main
git remote add origin YOUR_GITHUB_REPOSITORY_URL
git push -u origin main
```

Replace `YOUR_GITHUB_REPOSITORY_URL` with the repository URL. Do not commit secrets or production credentials.
