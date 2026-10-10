# SupplyHub website chalane aur manage karne ki guide

Yeh guide customer, seller aur staff/admin ke liye hai. Website ke pages aur buttons user ke role ke hisaab se dikhte hain. Staff dashboard kholne ke liye staff account se login hona zaroori hai.

## Website shuru karna

Website ka address local computer par `http://127.0.0.1:8000/` hota hai.

PowerShell mein project folder kholkar:

```powershell
.\.venv\Scripts\Activate.ps1
python manage.py runserver
```

Band karne ke liye runserver wale terminal mein `Ctrl+C` dabayein. Agar `.venv` abhi bana nahi hai, to project ke README mein diye setup steps follow karein.

## Customer ke liye

1. Home page par categories ya search box se product dhoondhein. Search product ke naam ke saath category aur description se milte-julte results bhi dikhata hai.
2. Product kholkar photo, price, minimum order quantity (MOQ), stock aur seller ki details dekhein.
3. **Add to Cart** ya **Buy Now** se cart mein product add karein. Sample ka option tabhi dikhega jab seller ne sample price set kiya ho.
4. Cart mein quantity check karke **Checkout** karein. Delivery aur payment details bharein. Guest checkout available hai; account mein login karne par order history account se judi rahegi.
5. **Orders / My orders** page par order number, items, payment aur status dekhein. Order number `#123` jaise numeric format mein dikhega.
6. Pending ya Confirmed order par cancellation ka button available ho sakta hai. Paid, Processing, Shipped ya carrier ko handover hue order ko website se cancel nahi kiya ja sakta; support se sampark karein.
7. Bulk/custom price chahiye to **Request a quote** bhejein. Login ke baad **My quotes** mein quote ka jawab dekh sakte hain.

## Seller ke liye

1. **Sell on website** ya `/sellers/register/` se seller application bharein.
2. Staff approval ka intezar karein. Approval se pehle products save ho sakte hain, lekin customers ko nahi dikhte.
3. Approval ke baad seller account se login karke `/seller/dashboard/` kholein.
4. **Products** mein **Add product** dabayein. Naam, category, description, price, MOQ, photo aur stock ki sahi jaankari bharein; phir save karein.
5. Product list mein **Published** ya **Draft** status check karein. **View** se customer wala product page dekh sakte hain.
6. Seller centre mein apne orders aur quote requests dekhein. Order status sirf sahi fulfilment step par update karein. Shipment booking tabhi kaam karegi jab Delhivery settings configured hon.

## Staff/Admin ke liye

Staff account se login karke `/staff-dashboard/` kholein. Yeh SupplyHub ka mukhya staff dashboard hai.

### Website ka naam, logo, headline aur colors badalna

1. Dashboard ke **Website Settings** section par jaayein.
2. Store name, browser title, tagline, homepage eyebrow/headline aur brand icon badlein.
3. **Logo** aur **Favicon** ke liye image file select karein. Logo storefront par dikhai deta hai; favicon browser tab ka chhota icon hai.
4. Color pickers se primary, dark primary, accent, page background aur text colors set karein.
5. Support phone/email, address aur delivery note bhi isi form mein update kiye ja sakte hain.
6. **Save Website Settings** dabayein. Save ke baad storefront ko refresh karke customer view check karein. Galat color format par field ke neeche error aayega; valid color picker se dobara select karein.

### Shipping aur payment settings

**Payment & Shipping** section mein delivery charge, free-shipping limit aur Cash on Delivery/bank transfer options configure karein. Offline payment ki receipt staff ko manually confirm karni hoti hai. Razorpay ke liye alag provider credentials chahiye.

### Products, sellers, orders aur quotes

- **Products:** Listing aur active status dekhein.
- **Seller approvals:** Seller application approve/reject karein. Approval par seller ke products publish hote hain; rejection par hidden rehte hain.
- **Orders:** Customer order aur current status check karein.
- **Quotations / RFQ:** Customer quote request ka jawab aur status manage karein.
- **Promotions & Ads:** Homepage campaign create, edit, pause ya schedule karein.
- **Suppliers / offers:** Supplier aur product offer ki settings manage karein.

## Aam problems aur unke hal

| Problem | Kya check karein |
|---|---|
| Product website par nahi dikh raha | Seller approved hai ya nahi, product **Published/active** hai ya nahi, category active hai ya nahi; phir page refresh karke naam/category se search karein. |
| Product photo nahi aa rahi | Product edit karke valid image upload karein. Branding logo/favicon ke liye bhi image file upload karke Website Settings save karein. Image badalne ke baad browser refresh karein. |
| Seller form save nahi hota | Har required field, category, price, MOQ aur image/type ke errors dekhein. Form ke neeche dikhaye error ko theek karke dobara save karein. |
| Customer order nahi dekh pa raha | Order banate waqt customer login tha ya guest, yeh check karein. Account ke orders sirf usi signed-in account ko dikhte hain; guest order ke confirmation page/notification par diya order number sambhal kar rakhein. |
| Cancel button nahi dikh raha | Self-cancellation sirf Pending/Confirmed order ke liye hoti hai. Payment ho chuka ho, order Processing/Shipped ho, ya carrier booking ho gayi ho to support se baat karein. |
| Website Settings save nahi hui | Har field ka error padhein. Hex color ko color picker se chun kar `#` ke saath 6 digits wala format use karein, jaise `#0F766E`. Upload ke baad save dabana na bhoolein. |
| Email customer/admin ko nahi mil rahi | Local development mein email runserver terminal par print hoti hai. Real email ke liye SMTP environment settings aur valid recipient details configure karni hoti hain. |
| Page error de raha hai ya website start nahi hoti | PowerShell mein project folder se `python manage.py check` chalayein. Database schema update ke baad `python manage.py migrate` chalayein. Runserver terminal ka pehla error dekhein; poora error message developer ko bhejein. |

## Developer ke liye quick checks

Project folder ke PowerShell terminal mein:

```powershell
python manage.py check
python manage.py migrate
python manage.py test
```

Error report karte waqt page/URL, kis role se login the, kya action kiya, exact error text aur terminal traceback bhejein. Password, API key, `.env` file ya customer ki private details share na karein.
