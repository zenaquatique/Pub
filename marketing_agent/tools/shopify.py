"""Outils de connexion à l'API Shopify."""
import requests
from config import SHOPIFY_SHOP_URL, SHOPIFY_ACCESS_TOKEN


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


def get_orders(limit: int = 50, status: str = "any") -> dict:
    data = _get("orders.json", {"limit": limit, "status": status, "financial_status": "paid"})
    orders = data.get("orders", [])
    total_revenue = sum(float(o.get("total_price", 0)) for o in orders)
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
        "recent_orders": len([o for o in orders if o.get("financial_status") == "paid"]),
    }


def get_low_stock_products(threshold: int = 5) -> list[dict]:
    products = get_products(limit=100)
    return [p for p in products if 0 < p["inventory"] <= threshold]


def update_product_description(product_id: int, new_description: str) -> dict:
    data = {"product": {"id": product_id, "body_html": new_description}}
    return _put(f"products/{product_id}.json", data)


def get_store_analytics() -> dict:
    orders_data = get_orders(limit=250)
    products = get_products(limit=50)
    low_stock = get_low_stock_products()
    return {
        "orders": orders_data,
        "total_products": len(products),
        "low_stock_count": len(low_stock),
        "low_stock_products": [p["title"] for p in low_stock],
    }
