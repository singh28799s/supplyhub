import json
from dataclasses import dataclass
from decimal import Decimal

import requests
from django.conf import settings
from django.utils.dateparse import parse_datetime


class DelhiveryError(Exception):
    pass


@dataclass(frozen=True)
class TrackingSnapshot:
    status: str
    status_time: object
    scans: list


def delhivery_is_configured() -> bool:
    return bool(settings.DELHIVERY_API_TOKEN and settings.DELHIVERY_PICKUP_LOCATION)


def _request(method, path, *, params=None, payload=None):
    if not delhivery_is_configured():
        raise DelhiveryError(
            "Set DELHIVERY_API_TOKEN and DELHIVERY_PICKUP_LOCATION before using shipping."
        )
    try:
        response = requests.request(
            method,
            f"{settings.DELHIVERY_API_BASE_URL}{path}",
            headers={
                "Authorization": f"Token {settings.DELHIVERY_API_TOKEN}",
                "Accept": "application/json",
            },
            params=params,
            data=payload,
            timeout=20,
        )
    except requests.RequestException as exc:
        raise DelhiveryError("Delhivery could not be reached. Check tracking and retry.") from exc
    if not response.ok:
        raise DelhiveryError(
            f"Delhivery returned HTTP {response.status_code}; shipment status was not changed."
        )
    try:
        return response.json()
    except requests.JSONDecodeError as exc:
        raise DelhiveryError("Delhivery returned an invalid response.") from exc


def create_shipment(seller_order, package):
    order = seller_order.order
    item_names = ", ".join(
        dict.fromkeys(seller_order.items.values_list("product_name", flat=True))
    )
    seller_reference = f"SH-{seller_order.pk}-{str(order.reference)[:8]}"
    shipping_amount = Decimal("0.00")
    seller_subtotal = seller_order.subtotal
    if order.total_amount > 0 and seller_subtotal > 0:
        shipping_amount = order.shipping_charge * seller_subtotal / (
            order.total_amount - order.shipping_charge
        )
    cod_amount = seller_subtotal + shipping_amount
    shipment = {
        "name": order.customer_name,
        "order": seller_reference,
        "phone": "".join(character for character in order.phone if character.isdigit())[-15:],
        "add": order.delivery_address,
        "city": order.city,
        "pin": order.postal_code,
        "payment_mode": "Prepaid" if order.payment_received else "COD",
        "weight": str(package["package_weight_grams"]),
        "shipment_length": str(package["package_length_cm"]),
        "shipment_width": str(package["package_width_cm"]),
        "shipment_height": str(package["package_height_cm"]),
        "products_desc": item_names[:250],
        "total_amount": str(cod_amount.quantize(Decimal("0.01"))),
    }
    if not order.payment_received:
        shipment["cod_amount"] = shipment["total_amount"]
    response = _request(
        "POST",
        "/api/cmu/create.json",
        payload={
            "format": "json",
            "data": json.dumps(
                {
                    "shipments": [shipment],
                    "pickup_location": {"name": settings.DELHIVERY_PICKUP_LOCATION},
                }
            ),
        },
    )
    packages = response.get("packages") or []
    package_response = packages[0] if packages else {}
    waybill = package_response.get("waybill") or package_response.get("waybill_number")
    shipment_id = package_response.get("refnum") or package_response.get("shipment_id") or seller_reference
    if not waybill:
        raise DelhiveryError("Delhivery did not return a waybill; shipment was not marked shipped.")
    return {
        "waybill": str(waybill),
        "shipment_id": str(shipment_id),
        "status": str(package_response.get("status") or "Manifested"),
    }


def fetch_tracking(waybill):
    response = _request(
        "GET",
        "/api/v1/packages/json/",
        params={"waybill": waybill, "verbose": "1"},
    )
    shipments = response.get("ShipmentData") or []
    if not shipments or not isinstance(shipments[0], dict):
        raise DelhiveryError("Delhivery returned no tracking details for this waybill.")
    shipment = shipments[0].get("Shipment") or {}
    current = shipment.get("Status") or {}
    if isinstance(current, str):
        status = current
        status_time_text = ""
    else:
        status = current.get("Status") or current.get("StatusType") or ""
        status_time_text = current.get("StatusDateTime") or ""
    scans = []
    for scan in shipment.get("Scans") or []:
        detail = scan.get("ScanDetail") or {}
        description = detail.get("Scan") or detail.get("Instructions") or ""
        timestamp = detail.get("ScanDateTime") or ""
        scans.append(
            {
                "status": str(description)[:100],
                "description": str(detail.get("Instructions") or ""),
                "occurred_at": parse_datetime(timestamp) if timestamp else None,
            }
        )
    if not status:
        raise DelhiveryError("Delhivery tracking response did not include a current status.")
    return TrackingSnapshot(
        status=str(status)[:100],
        status_time=parse_datetime(status_time_text) if status_time_text else None,
        scans=scans,
    )
