# SupplyHub B2B Wholesale Marketplace

A responsive Django wholesale marketplace. Staff manage sellers, products, orders, offers, homepage campaigns, and store settings from the staff dashboard. Django admin is also available for advanced maintenance.

For a step-by-step Hindi/Hinglish guide to customer, seller, and staff workflows and common fixes, see [WEBSITE_GUIDE.md](./WEBSITE_GUIDE.md).

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

The main staff/admin dashboard is available at `http://127.0.0.1:8000/staff-dashboard/` after signing in with a staff or superuser account. It summarizes the catalog, orders, pending quote requests, suppliers, product offers, seller approvals, and store settings. Regular customer accounts cannot access it.

Customers can create an account at `/register/` and log in at `/login/`. Registration creates a regular customer account; it does not grant admin access. Logout uses the account menu on the homepage.

The demo command is safe to run repeatedly and adds starter products. **Its sample prices and minimum order quantities are placeholders; review them before showing the catalog to customers.** Add or edit catalog entries in Django admin. Run checks and tests with `python manage.py check` and `python manage.py test`.

The storefront is a responsive B2B wholesale marketplace with category browsing, search and sorting, MOQ/sample details, carts, wishlists and bulk quote requests. The homepage automatically features products marked **Featured**, shows the most recently added products, and builds a deals shelf from products with an offer price or sample price. Sellers have a separate seller centre and public store page.

## Customer ordering

Customers can add products to the session cart, adjust quantities (subject to each product's MOQ), and submit delivery details at checkout. They may order as guests; signed-in customers can see their orders from the **Orders** link. New orders are saved with a pending-confirmation status and can be reviewed/updated in Django admin. Razorpay online payments are optional and require provider configuration; COD and bank-transfer payment receipt remains a manual staff step. Confirm sample prices and shipping with the customer before fulfilling an order.

To offer samples, set a product's **Sample price** and **Sample quantity** in Django admin. Buyers may order that exact sample quantity at the sample price, or order the wholesale MOQ or more at the wholesale price. Quantities between the sample quantity and MOQ are rejected. Sample prices are left unset until you enter your actual price.

## Quotes, suppliers, and store settings

Buyers can submit a bulk/custom quote request from the storefront. Staff can review it under **Quotations / RFQ** in the dashboard or in Django admin, enter a quoted unit price and response, and update its status. Signed-in customers can see their quote history. Suppliers are managed from the dashboard/Admin and can be assigned to products.

Store branding, contact details, shipping fee, free-shipping threshold, and offline checkout methods (cash on delivery/bank transfer) are configurable in the dashboard. Orders save the selected payment method and shipping amount. Razorpay online checkout is available when its API keys are configured; COD and bank-transfer orders still require manual payment confirmation. Email notifications are automated but require SMTP configuration for real delivery.

Order and quote notifications are queued after the database transaction commits. Locally, Django prints email contents in the runserver terminal; configure `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL`, and `SUPPLYHUB_ADMIN_EMAIL` as environment variables to send real SMTP email. Set `EMAIL_USE_TLS` or `EMAIL_USE_SSL` to match the mail provider. Store support email is also used for staff notifications when no `SUPPLYHUB_ADMIN_EMAIL` is set. Delivery depends on valid SMTP configuration.

Product promotional prices can be set through the product admin's **Offer price** field. The offer must be below the wholesale price.

### Homepage campaigns and ads

Staff can open **Promotions & Ads** in the staff dashboard or **Promotion campaigns** in Django admin. Create a campaign with its internal name, eyebrow, headline, description and optional banner image. Choose a button destination (catalog, categories, bulk quote, or a specific product), set optional start/end times, and enable the campaign. Currently active campaigns rotate in the homepage hero in display order; paused, future, and expired campaigns stay hidden. Campaign dates use the server's configured timezone. Update the storefront name and tagline under **Website Settings**.

After pulling changes that add a migration, apply it with `python manage.py migrate`.

### Seller accounts and listings

Sellers apply at `/sellers/register/` or from **Sell on SupplyHub**. A seller account starts as **Awaiting review**; staff must approve the profile under **Seller approvals** in the staff dashboard before the seller's products or public shop appear. Sign in with that seller account and open `/seller/dashboard/` to manage the shop profile, product listings, buyer quote inquiries, and seller-specific order updates.

Seller profiles, product specifications, extra product photos, quantity-price tiers, customizations, seller orders, and seller quote replies each have their own Django models/tables in the project's configured database. Local development uses SQLite; deployment can continue using the existing `DATABASE_URL` configuration. No separate database server is required.

Product listings support multiple gallery images and product specifications entered one per line as `Name: Value`. Optional wholesale tiers use `1-99: 120.00` and `100+: 99.00` format; the applicable tier price is used for cart and checkout totals. Optional customization choices can be recorded as `Option | extra price per unit | minimum quantity` (use `-` when no extra price is known). These customization prices are indicative; customers must confirm options and final charges with the seller through a quote before ordering. Sellers choose which standard detail sections and individual specifications appear to buyers. Product name/category remain visible; saved price/MOQ remain enforced by checkout even if their display is hidden.

Orders that contain products from multiple sellers are split into seller-specific order records in the seller centre. Sellers can advance their own order status from confirmation to processing, create a Delhivery shipment, and refresh tracking without overwriting another seller's status or the overall marketplace order. Sellers can reply with their own price and message to product-specific or shop-specific quote inquiries.

### Inventory, online payments, shipping, and seller payouts

- **Inventory:** Sellers can enable stock tracking and set available units on each product. Checkout locks tracked products, rejects quantities above stock, and reserves ordered units. Staff cancellation of an order releases its reserved units. Untracked products preserve the existing unlimited-stock behavior.
- **Razorpay checkout:** Configure `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, and `RAZORPAY_WEBHOOK_SECRET` as environment variables. Add the webhook endpoint `/payments/razorpay/webhook/` in Razorpay and subscribe it to `payment.captured`, `transfer.processed`, and `transfer.failed`. Checkout signatures are verified server-side and the payment is fetched from Razorpay before the order is marked paid. Do not put API secrets in source control.
- **Delhivery:** Configure `DELHIVERY_API_TOKEN` and `DELHIVERY_PICKUP_LOCATION`; the pickup name must exactly match the warehouse registered with Delhivery. `DELHIVERY_API_BASE_URL` defaults to `https://track.delhivery.com`; set it to the Delhivery staging host to test. Product weight/dimensions are optional estimates. Before booking each seller parcel, the seller confirms its final packed weight and dimensions; the seller centre then creates a waybill and lets the seller refresh carrier tracking.
- **Seller payout:** Razorpay Route must be enabled for the SupplyHub account, and each seller must complete Razorpay's linked-account/KYC setup. Store the provider-issued linked-account ID in that seller's **Seller profile** admin record; SupplyHub does not store bank-account credentials. The default SupplyHub commission is 5% of the seller's product subtotal (shipping is excluded); override with `SUPPLYHUB_SELLER_COMMISSION_PERCENT`. Only Razorpay-captured orders can be transferred automatically. A verified Delhivery delivery starts a seven-day hold (`SUPPLYHUB_PAYOUT_HOLD_DAYS`, default `7`); staff then selects eligible rows under **Seller payouts** in Django admin and runs **Release eligible payouts through Razorpay Route**. Razorpay transfer webhooks update transfer completion/failure status. COD and bank-transfer orders are not eligible for automatic Razorpay Route transfers.
- **Cancellations/refunds:** Cancelling an order releases its reserved stock and blocks any unreleased seller payout. Refunds are not automated; staff must refund a captured Razorpay payment in the Razorpay dashboard before/while cancelling it and reconcile it manually.

Use Razorpay and Delhivery test credentials and test environments before enabling live credentials. External requests are not made by the automated tests; provider responses are mocked.

Images use local media-file storage during development when no Cloudinary credentials are configured. Set `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, and `CLOUDINARY_API_SECRET` (or `CLOUDINARY_URL`) for Cloudinary-backed media; production mode requires Cloudinary configuration.

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
