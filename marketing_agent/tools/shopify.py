"""Outils de connexion à l'API Shopify."""
from datetime import datetime, timedelta
import requests
from config import SHOPIFY_SHOP_URL, SHOPIFY_ACCESS_TOKEN

PERIOD_LABELS = {
    "today":      "Aujourd'hui",
    "yesterday":  "Hier",
    "this_week":  "Cette semaine",
    "this_month": "Ce mois-ci",
    "this_year":  "Cette année",
    "week":       "7 derniers jours",
    "month":      "30 derniers jours",
    "3months":    "3 derniers mois",
    "6months":    "6 derniers mois",
    "year":       "12 derniers mois",
    "all":        "Depuis le début",
    "custom":     "Période personnalisée",
}


def _period_dates(period: str, start_date: str = None, end_date: str = None):
    """Retourne (created_at_min, created_at_max) ou (None, None) pour 'all'."""
    now = datetime.now()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    if period == "custom":
        fmt = "%Y-%m-%d"
        start = datetime.strptime(start_date, fmt) if start_date else today
        end   = datetime.strptime(end_date, fmt) + timedelta(days=1) if end_date else now
        return start.isoformat(), end.isoformat()

    if period == "today":
        return today.isoformat(), now.isoformat()
    if period == "yesterday":
        y = today - timedelta(days=1)
        return y.isoformat(), today.isoformat()
    if period == "this_week":
        monday = today - timedelta(days=today.weekday())
        return monday.isoformat(), now.isoformat()
    if period == "this_month":
        first = today.replace(day=1)
        return first.isoformat(), now.isoformat()
    if period == "this_year":
        first = today.replace(month=1, day=1)
        return first.isoformat(), now.isoformat()

    days = {"week": 7, "month": 30, "3months": 90, "6months": 180, "year": 365}.get(period)
    if days:
        return (today - timedelta(days=days)).isoformat(), now.isoformat()

    return None, None  # "all"


def _shopify_configured() -> bool:
    return bool(SHOPIFY_SHOP_URL and SHOPIFY_ACCESS_TOKEN)


def _get(endpoint: str, params: dict = None) -> dict:
    if not _shopify_configured():
        return {}
    url = f"https://{SHOPIFY_SHOP_URL}/admin/api/2024-01/{endpoint}"
    headers = {"X-Shopify-Access-Token": SHOPIFY_ACCESS_TOKEN, "Content-Type": "application/json"}
    resp = requests.get(url, headers=headers, params=params or {}, timeout=15)
    resp.raise_for_status()
    return resp.json()


def _put(endpoint: str, data: dict) -> dict:
    if not _shopify_configured():
        return {"status": "simulated", "reason": "Shopify non configuré"}
    url = f"https://{SHOPIFY_SHOP_URL}/admin/api/2024-01/{endpoint}"
    headers = {"X-Shopify-Access-Token": SHOPIFY_ACCESS_TOKEN, "Content-Type": "application/json"}
    resp = requests.put(url, headers=headers, json=data, timeout=15)
    resp.raise_for_status()
    return resp.json()


def get_products(limit: int = 20, status: str = "active") -> list[dict]:
    data = _get("products.json", {"limit": limit, "status": status})
    products = []
    for p in data.get("products", []):
        products.append({
            "id": p["id"],
            "title": p["title"],
            "description": p.get("body_html", ""),
            "vendor": p.get("vendor", ""),
            "product_type": p.get("product_type", ""),
            "tags": p.get("tags", ""),
            "price": p["variants"][0]["price"] if p.get("variants") else "N/A",
            "inventory": sum(v.get("inventory_quantity", 0) for v in p.get("variants", [])),
            "image_url": p["images"][0]["src"] if p.get("images") else None,
            "handle": p.get("handle", ""),
        })
    return products


def get_orders(period: str = "month", start_date: str = None, end_date: str = None) -> dict:
    date_min, date_max = _period_dates(period, start_date, end_date)
    params: dict = {"limit": 250, "status": "any", "financial_status": "paid"}
    if date_min:
        params["created_at_min"] = date_min
    if date_max:
        params["created_at_max"] = date_max

    params["status"] = "any"
    data = _get("orders.json", params)
    orders = [o for o in data.get("orders", []) if o.get("cancel_reason") is None]
    total_revenue = sum(float(o.get("current_total_price", o.get("total_price", 0))) for o in orders)
    product_sales: dict[str, int] = {}
    for order in orders:
        for item in order.get("line_items", []):
            name = item.get("name", "Inconnu")
            product_sales[name] = product_sales.get(name, 0) + item.get("quantity", 0)
    top_products = sorted(product_sales.items(), key=lambda x: x[1], reverse=True)[:5]
    return {
        "total_orders": len(orders),
        "total_revenue": round(total_revenue, 2),
        "top_selling": top_products,
        "period_label": PERIOD_LABELS.get(period, period),
    }


def get_low_stock_products(threshold: int = 5) -> list[dict]:
    products = get_products(limit=100)
    return [p for p in products if 0 < p["inventory"] <= threshold]


def update_product_description(product_id: int, new_description: str) -> dict:
    data = {"product": {"id": product_id, "body_html": new_description}}
    return _put(f"products/{product_id}.json", data)


def get_store_analytics(period: str = "month", start_date: str = None, end_date: str = None) -> dict:
    orders_data = get_orders(period=period, start_date=start_date, end_date=end_date)
    products = get_products(limit=50)
    low_stock = get_low_stock_products()
    return {
        "orders": orders_data,
        "total_products": len(products),
        "low_stock_count": len(low_stock),
        "low_stock_products": [p["title"] for p in low_stock],
        "period": period,
        "period_label": PERIOD_LABELS.get(period, period),
    }
