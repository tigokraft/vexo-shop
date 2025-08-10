#!/usr/bin/env python3
"""
Full API CLI for your Next.js + Prisma store.

Requirements:
  pip install requests

Quick samples:
  # login (stores cookie if --cookie-file is set)
  python store_cli.py --cookie-file session.cookies login --email admin@local.test --password admin123!

  # brands
  python store_cli.py --cookie-file session.cookies brands list
  python store_cli.py --cookie-file session.cookies brands create --name Orbit --slug orbit

  # products + options + variants
  python store_cli.py --cookie-file session.cookies products create --title "Athletic Tee" --slug athletic-tee --sku-prefix TEE
  python store_cli.py --cookie-file session.cookies options add --product-id PRODUCT_ID --name Size --values S M L
  python store_cli.py --cookie-file session.cookies options add --product-id PRODUCT_ID --name Color --values Black White
  python store_cli.py --cookie-file session.cookies variants generate --product-id PRODUCT_ID --price-cents 2499 --stock 25

  # catalog (public)
  python store_cli.py catalog products --page 1 --page-size 24
  python store_cli.py catalog product --slug athletic-tee

  # cart -> add item -> checkout (guest)
  python store_cli.py --cookie-file cart.cookies cart add --variant-id VARIANT_ID --qty 2
  python store_cli.py --cookie-file cart.cookies checkout --email buyer@local.test

  # end-to-end demos
  python store_cli.py --cookie-file admin.cookies demo-admin
  python store_cli.py --cookie-file cart.cookies demo-storefront
"""

import argparse
import json
import os
import sys
import pickle
from typing import Any, Dict, Optional, List

import requests

DEFAULT_BASE_URL = os.environ.get("STORE_BASE_URL", "http://localhost:3000")
DEFAULT_ADMIN_EMAIL = os.environ.get("STORE_ADMIN_EMAIL", "admin@local.test")
DEFAULT_ADMIN_PASSWORD = os.environ.get("STORE_ADMIN_PASSWORD", "admin123!")


class ApiError(Exception):
    pass


class ApiClient:
    def __init__(self, base_url: str, cookie_file: Optional[str] = None, verbose: bool = True):
        self.base_url = base_url.rstrip("/")
        self.sess = requests.Session()
        self.cookie_file = cookie_file
        self.verbose = verbose
        if cookie_file and os.path.exists(cookie_file):
            try:
                with open(cookie_file, "rb") as f:
                    self.sess.cookies.update(pickle.load(f))
                if self.verbose:
                    print(f"[cookies] Loaded cookie jar from {cookie_file}")
            except Exception as e:
                if self.verbose:
                    print(f"[cookies] Failed to load cookie jar: {e}")

    def _save_cookies(self):
        if not self.cookie_file:
            return
        try:
            with open(self.cookie_file, "wb") as f:
                pickle.dump(self.sess.cookies, f)
            if self.verbose:
                print(f"[cookies] Saved cookie jar to {self.cookie_file}")
        except Exception as e:
            if self.verbose:
                print(f"[cookies] Failed to save cookie jar: {e}")

    def request(self, method: str, path: str, *, params: Dict[str, Any] = None, json_body: Dict[str, Any] = None) -> Any:
        url = f"{self.base_url}{path}"
        headers = {"content-type": "application/json"} if json_body is not None else {}
        resp = self.sess.request(method, url, params=params, json=json_body, headers=headers, timeout=30)
        try:
            data = resp.json()
        except ValueError:
            data = resp.text
        if self.verbose:
            print(f"[{method} {path}] {resp.status_code}")
        if not (200 <= resp.status_code < 300):
            raise ApiError(f"HTTP {resp.status_code} for {method} {path}: {json.dumps(data, indent=2) if isinstance(data, dict) else data}")
        self._save_cookies()
        return data

    # ---------- Auth ----------
    def register(self, email: str, password: str, name: str) -> Any:
        return self.request("POST", "/api/auth/register", json_body={"email": email, "password": password, "name": name})

    def login(self, email: str, password: str) -> Any:
        return self.request("POST", "/api/auth/login", json_body={"email": email, "password": password})

    def me(self) -> Any:
        return self.request("GET", "/api/auth/me")

    def logout(self) -> Any:
        return self.request("POST", "/api/auth/logout")

    # ---------- Brands ----------
    def list_brands(self, page: int = 1, page_size: int = 20, q: str = "") -> Any:
        params = {"page": page, "pageSize": page_size}
        if q:
            params["q"] = q
        return self.request("GET", "/api/admin/brands", params=params)

    def create_brand(self, **kwargs) -> Any:
        return self.request("POST", "/api/admin/brands", json_body=kwargs)

    def update_brand(self, brand_id: str, **kwargs) -> Any:
        return self.request("PUT", f"/api/admin/brands/{brand_id}", json_body=kwargs)

    def delete_brand(self, brand_id: str) -> Any:
        return self.request("DELETE", f"/api/admin/brands/{brand_id}")

    def find_brand(self, *, slug: Optional[str] = None, name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        q = slug or name or ""
        if not q:
            return None
        res = self.list_brands(page=1, page_size=50, q=q)
        items = res.get("items", []) if isinstance(res, dict) else []
        for it in items:
            if slug and it.get("slug") == slug:
                return it
            if name and it.get("name") == name:
                return it
        return None

    def ensure_brand(self, *, name: str, slug: Optional[str] = None, **kwargs) -> Any:
        payload = {"name": name}
        if slug:
            payload["slug"] = slug
        payload.update(kwargs or {})
        try:
            return self.create_brand(**payload)
        except ApiError as e:
            if "409" in str(e) or "Conflict" in str(e):
                existing = self.find_brand(slug=slug, name=name)
                if existing:
                    if self.verbose:
                        print(f"[ensure_brand] Using existing brand {existing['id']} ({existing.get('slug')})")
                    return existing
            raise

    # ---------- Categories ----------
    def list_categories(self, page: int = 1, page_size: int = 20, q: str = "", parent_id: Optional[str] = None) -> Any:
        params = {"page": page, "pageSize": page_size}
        if q:
            params["q"] = q
        if parent_id is not None:
            params["parentId"] = parent_id
        return self.request("GET", "/api/admin/categories", params=params)

    def create_category(self, **kwargs) -> Any:
        return self.request("POST", "/api/admin/categories", json_body=kwargs)

    def update_category(self, cat_id: str, **kwargs) -> Any:
        return self.request("PUT", f"/api/admin/categories/{cat_id}", json_body=kwargs)

    def delete_category(self, cat_id: str) -> Any:
        return self.request("DELETE", f"/api/admin/categories/{cat_id}")

    def find_category(self, *, slug: Optional[str] = None, name: Optional[str] = None, parent_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        q = slug or name or ""
        res = self.list_categories(page=1, page_size=100, q=q, parent_id=parent_id if parent_id is not None else None)
        items = res.get("items", []) if isinstance(res, dict) else []
        for it in items:
            if slug and it.get("slug") == slug:
                return it
            if name and it.get("name") == name and (parent_id is None or it.get("parentId") == parent_id):
                return it
        return None

    def ensure_category(self, *, name: str, slug: Optional[str] = None, parentId: Optional[str] = None, **kwargs) -> Any:
        payload = {"name": name}
        if slug:
            payload["slug"] = slug
        if parentId:
            payload["parentId"] = parentId
        payload.update(kwargs or {})
        try:
            return self.create_category(**payload)
        except ApiError as e:
            if "409" in str(e) or "Conflict" in str(e):
                existing = self.find_category(slug=slug, name=name, parent_id=parentId)
                if existing:
                    if self.verbose:
                        print(f"[ensure_category] Using existing category {existing['id']} ({existing.get('slug')})")
                    return existing
            raise

    # ---------- Products ----------
    def list_products(self, page: int = 1, page_size: int = 20, q: str = "") -> Any:
        params = {"page": page, "pageSize": page_size}
        if q:
            params["q"] = q
        return self.request("GET", "/api/admin/products", params=params)

    def create_product(self, **kwargs) -> Any:
        return self.request("POST", "/api/admin/products", json_body=kwargs)

    def update_product(self, product_id: str, **kwargs) -> Any:
        return self.request("PUT", f"/api/admin/products/{product_id}", json_body=kwargs)

    def delete_product(self, product_id: str) -> Any:
        return self.request("DELETE", f"/api/admin/products/{product_id}")

    def get_product(self, product_id: str) -> Any:
        return self.request("GET", f"/api/admin/products/{product_id}")

    def find_product(self, *, slug: Optional[str] = None, title: Optional[str] = None) -> Optional[Dict[str, Any]]:
        q = slug or title or ""
        if not q:
            return None
        res = self.list_products(page=1, page_size=50, q=q)
        items = res.get("items", []) if isinstance(res, dict) else []
        for it in items:
            if slug and it.get("slug") == slug:
                return it
            if title and it.get("title") == title:
                return it
        return None

    def ensure_product(self, *, title: str, slug: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        payload = {"title": title}
        if slug:
            payload["slug"] = slug
        payload.update(kwargs or {})
        try:
            return self.create_product(**payload)
        except ApiError as e:
            if "409" in str(e) or "Slug already exists" in str(e) or "Conflict" in str(e):
                existing = self.find_product(slug=slug, title=title)
                if existing:
                    if self.verbose:
                        print(f"[ensure_product] Using existing product {existing['id']} ({existing.get('slug')})")
                    return existing
            raise

    # ---------- Options ----------
    def list_options(self, product_id: str) -> List[Dict[str, Any]]:
        data = self.request("GET", f"/api/admin/products/{product_id}/options")
        return data if isinstance(data, list) else []

    def add_option(self, product_id: str, name: str, values: List[str], position: Optional[int] = None) -> Any:
        body = {"name": name, "values": values}
        if position is not None:
            body["position"] = position
        return self.request("POST", f"/api/admin/products/{product_id}/options", json_body=body)

    # ---------- Variants ----------
    def list_variants(self, product_id: str) -> Any:
        return self.request("GET", f"/api/admin/products/{product_id}/variants")

    def generate_variants(self, product_id: str, *, price_cents: int, currency: str = "EUR", initial_stock: int = 0) -> Any:
        body = {"generateAll": True, "priceCents": price_cents, "currency": currency, "initialStock": initial_stock}
        return self.request("POST", f"/api/admin/products/{product_id}/variants", json_body=body)

    def create_combinations(self, product_id: str, combinations: List[Dict[str, Any]], currency: str = "EUR") -> Any:
        body = {"currency": currency, "combinations": combinations}
        return self.request("POST", f"/api/admin/products/{product_id}/variants", json_body=body)

    def update_variant(self, variant_id: str, **kwargs) -> Any:
        return self.request("PUT", f"/api/admin/variants/{variant_id}", json_body=kwargs)

    def delete_variant(self, variant_id: str) -> Any:
        return self.request("DELETE", f"/api/admin/variants/{variant_id}")

    # ---------- Stock ----------
    def set_stock(self, variant_id: str, on_hand: int, reason: str = "setOnHand", warehouse_id: Optional[str] = None) -> Any:
        body = {"setOnHand": on_hand, "reason": reason}
        if warehouse_id:
            body["warehouseId"] = warehouse_id
        return self.request("POST", f"/api/admin/variants/{variant_id}/stock", json_body=body)

    def delta_stock(self, variant_id: str, delta: int, reason: str = "deltaOnHand", warehouse_id: Optional[str] = None) -> Any:
        body = {"deltaOnHand": delta, "reason": reason}
        if warehouse_id:
            body["warehouseId"] = warehouse_id
        return self.request("POST", f"/api/admin/variants/{variant_id}/stock", json_body=body)

    # ---------- Catalog (public) ----------
    def catalog_products(self, page=1, page_size=24, q="", brand="", category="", sort="newest", min_price=None, max_price=None) -> Any:
        params = {"page": page, "pageSize": page_size, "sort": sort}
        if q:
            params["q"] = q
        if brand:
            params["brand"] = brand
        if category:
            params["category"] = category
        if min_price is not None:
            params["minPrice"] = min_price
        if max_price is not None:
            params["maxPrice"] = max_price
        return self.request("GET", "/api/catalog/products", params=params)

    def catalog_product(self, slug: str) -> Any:
        return self.request("GET", f"/api/catalog/products/{slug}")

    def catalog_categories(self, parent="root", page=1, page_size=50) -> Any:
        return self.request("GET", "/api/catalog/categories", params={"parent": parent, "page": page, "pageSize": page_size})

    def catalog_brands(self, q="") -> Any:
        p = {}
        if q:
            p["q"] = q
        return self.request("GET", "/api/catalog/brands", params=p)

    # ---------- Cart ----------
    def cart_get(self) -> Any:
        return self.request("GET", "/api/cart")

    def cart_clear(self) -> Any:
        return self.request("DELETE", "/api/cart")

    def cart_add_item(self, variant_id: str, qty: int = 1) -> Any:
        return self.request("POST", "/api/cart/items", json_body={"variantId": variant_id, "quantity": qty})

    def cart_update_item(self, item_id: str, qty: int) -> Any:
        return self.request("PATCH", f"/api/cart/items/{item_id}", json_body={"quantity": qty})

    def cart_delete_item(self, item_id: str) -> Any:
        return self.request("DELETE", f"/api/cart/items/{item_id}")

    def cart_apply_coupon(self, code: str) -> Any:
        return self.request("POST", "/api/cart/coupon", json_body={"code": code})

    def cart_remove_coupon(self) -> Any:
        return self.request("DELETE", "/api/cart/coupon")

    # ---------- Checkout (manual) ----------
    def checkout(self, email: Optional[str] = None, provider: str = "manual", capture: bool = True,
                 shipping_address_id: Optional[str] = None, billing_address_id: Optional[str] = None) -> Any:
        body = {
            "payment": {"provider": provider, "capture": bool(capture)},
        }
        if email:
            body["email"] = email
        if shipping_address_id:
            body["shippingAddressId"] = shipping_address_id
        if billing_address_id:
            body["billingAddressId"] = billing_address_id
        return self.request("POST", "/api/checkout", json_body=body)


def pretty(obj):
    print(json.dumps(obj, indent=2, ensure_ascii=False))


# ---------------- CLI actions ----------------

def act_register(args):
    c = ApiClient(args.base_url, args.cookie_file, verbose=not args.quiet)
    pretty(c.register(args.email, args.password, args.name))

def act_login(args):
    c = ApiClient(args.base_url, args.cookie_file, verbose=not args.quiet)
    pretty(c.login(args.email, args.password))

def act_me(args):
    c = ApiClient(args.base_url, args.cookie_file, verbose=not args.quiet)
    pretty(c.me())

def act_logout(args):
    c = ApiClient(args.base_url, args.cookie_file, verbose=not args.quiet)
    pretty(c.logout())


def act_brands(args):
    c = ApiClient(args.base_url, args.cookie_file, verbose=not args.quiet)
    if args.action == "list":
        pretty(c.list_brands(page=args.page, page_size=args.page_size, q=args.q or ""))
    elif args.action == "create":
        payload = {"name": args.name}
        if args.slug: payload["slug"] = args.slug
        if args.description: payload["description"] = args.description
        if args.website: payload["website"] = args.website
        if args.logo_url: payload["logoUrl"] = args.logo_url
        pretty(c.create_brand(**payload))
    elif args.action == "update":
        payload = {}
        if args.name: payload["name"] = args.name
        if args.slug: payload["slug"] = args.slug
        if args.description is not None: payload["description"] = args.description
        if args.website is not None: payload["website"] = args.website
        if args.logo_url is not None: payload["logoUrl"] = args.logo_url
        pretty(c.update_brand(args.id, **payload))
    elif args.action == "delete":
        pretty(c.delete_brand(args.id))


def act_categories(args):
    c = ApiClient(args.base_url, args.cookie_file, verbose=not args.quiet)
    if args.action == "list":
        parent = args.parent_id
        pretty(c.list_categories(page=args.page, page_size=args.page_size, q=args.q or "", parent_id=parent))
    elif args.action == "create":
        payload = {"name": args.name}
        if args.slug: payload["slug"] = args.slug
        if args.description: payload["description"] = args.description
        if args.parent_id: payload["parentId"] = args.parent_id
        pretty(c.create_category(**payload))
    elif args.action == "update":
        payload = {}
        if args.name: payload["name"] = args.name
        if args.slug: payload["slug"] = args.slug
        if args.description is not None: payload["description"] = args.description
        if args.parent_id is not None: payload["parentId"] = args.parent_id
        pretty(c.update_category(args.id, **payload))
    elif args.action == "delete":
        pretty(c.delete_category(args.id))


def act_products(args):
    c = ApiClient(args.base_url, args.cookie_file, verbose=not args.quiet)
    if args.action == "list":
        pretty(c.list_products(page=args.page, page_size=args.page_size, q=args.q or ""))
    elif args.action == "create":
        payload = {"title": args.title}
        if args.slug: payload["slug"] = args.slug
        if args.description: payload["description"] = args.description
        if args.brand_id is not None: payload["brandId"] = args.brand_id
        if args.status: payload["status"] = args.status
        if args.sku_prefix: payload["skuPrefix"] = args.sku_prefix
        if args.image: payload["images"] = [{"url": args.image}]
        if args.category_ids: payload["categoryIds"] = args.category_ids
        pretty(c.create_product(**payload))
    elif args.action == "update":
        payload = {}
        if args.title: payload["title"] = args.title
        if args.slug: payload["slug"] = args.slug
        if args.description is not None: payload["description"] = args.description
        if args.brand_id is not None: payload["brandId"] = args.brand_id
        if args.status: payload["status"] = args.status
        if args.sku_prefix is not None: payload["skuPrefix"] = args.sku_prefix
        if args.image is not None: payload["images"] = [{"url": args.image}]
        if args.category_ids is not None: payload["categoryIds"] = args.category_ids
        pretty(c.update_product(args.id, **payload))
    elif args.action == "delete":
        pretty(c.delete_product(args.id))
    elif args.action == "get":
        pretty(c.get_product(args.id))


def act_options(args):
    c = ApiClient(args.base_url, args.cookie_file, verbose=not args.quiet)
    if args.action == "list":
        pretty(c.list_options(args.product_id))
    elif args.action == "add":
        pretty(c.add_option(args.product_id, args.name, args.values, position=args.position))


def act_variants(args):
    c = ApiClient(args.base_url, args.cookie_file, verbose=not args.quiet)
    if args.action == "list":
        pretty(c.list_variants(args.product_id))
    elif args.action == "generate":
        pretty(c.generate_variants(args.product_id, price_cents=args.price_cents, currency=args.currency, initial_stock=args.stock))
    elif args.action == "create":
        combos = [json.loads(s) for s in args.combo]
        pretty(c.create_combinations(args.product_id, combos, currency=args.currency))


def act_variant(args):
    c = ApiClient(args.base_url, args.cookie_file, verbose=not args.quiet)
    if args.action == "update":
        payload = {}
        if args.sku: payload["sku"] = args.sku
        if args.title: payload["title"] = args.title
        if args.price_cents is not None: payload["priceCents"] = args.price_cents
        if args.compare_at_cents is not None: payload["compareAtCents"] = args.compare_at_cents
        if args.cost_cents is not None: payload["costCents"] = args.cost_cents
        if args.currency: payload["currency"] = args.currency
        if args.track_inventory is not None: payload["trackInventory"] = args.track_inventory
        if args.default: payload["isDefault"] = True
        pretty(c.update_variant(args.variant_id, **payload))
    elif args.action == "delete":
        pretty(c.delete_variant(args.variant_id))


def act_stock(args):
    c = ApiClient(args.base_url, args.cookie_file, verbose=not args.quiet)
    if args.action == "set":
        pretty(c.set_stock(args.variant_id, on_hand=args.on_hand, reason=args.reason, warehouse_id=args.warehouse_id))
    elif args.action == "delta":
        pretty(c.delta_stock(args.variant_id, delta=args.delta, reason=args.reason, warehouse_id=args.warehouse_id))


def act_catalog(args):
    c = ApiClient(args.base_url, args.cookie_file, verbose=not args.quiet)
    if args.section == "products":
        pretty(c.catalog_products(page=args.page, page_size=args.page_size, q=args.q or "", brand=args.brand or "", category=args.category or "", sort=args.sort, min_price=args.min_price, max_price=args.max_price))
    elif args.section == "product":
        pretty(c.catalog_product(args.slug))
    elif args.section == "brands":
        pretty(c.catalog_brands(q=args.q or ""))
    elif args.section == "categories":
        pretty(c.catalog_categories(parent=args.parent, page=args.page, page_size=args.page_size))


def act_cart(args):
    c = ApiClient(args.base_url, args.cookie_file, verbose=not args.quiet)
    if args.action == "get":
        pretty(c.cart_get())
    elif args.action == "clear":
        pretty(c.cart_clear())
    elif args.action == "add":
        pretty(c.cart_add_item(args.variant_id, qty=args.qty))
    elif args.action == "set":
        pretty(c.cart_update_item(args.item_id, qty=args.qty))
    elif args.action == "remove":
        pretty(c.cart_delete_item(args.item_id))
    elif args.action == "apply-coupon":
        pretty(c.cart_apply_coupon(args.code))
    elif args.action == "remove-coupon":
        pretty(c.cart_remove_coupon())


def act_checkout(args):
    c = ApiClient(args.base_url, args.cookie_file, verbose=not args.quiet)
    pretty(c.checkout(email=args.email, provider=args.provider, capture=not args.auth_only, shipping_address_id=args.shipping_address_id, billing_address_id=args.billing_address_id))


def act_demo_admin(args):
    c = ApiClient(args.base_url, args.cookie_file, verbose=not args.quiet)
    print(f"[demo-admin] Login as {args.email}")
    c.login(args.email, args.password)
    pretty(c.me())

    print("\n[demo-admin] Ensure brand Orbit")
    brand = c.ensure_brand(name="Orbit", slug="orbit", description="Performance basics")
    pretty(brand)
    brand_id = brand.get("id")

    print("\n[demo-admin] Ensure categories Women > Tops")
    women = c.ensure_category(name="Women", slug="women")
    tops = c.ensure_category(name="Tops", slug="tops", parentId=women["id"])
    pretty({"women": women["id"], "tops": tops["id"]})

    print("\n[demo-admin] Ensure product Athletic Tee")
    prod = c.ensure_product(title="Athletic Tee", slug="athletic-tee", description="Breathable tee", status="PUBLISHED", skuPrefix="TEE", images=[{"url": "https://picsum.photos/seed/athtee/800/800"}], brandId=brand_id, categoryIds=[tops["id"]])
    pretty(prod)

    pid = prod["id"]
    print("\n[demo-admin] Ensure options")
    existing_opts = {o["name"] for o in c.list_options(pid)}
    if "Size" not in existing_opts:
        pretty(c.add_option(pid, "Size", ["S", "M", "L"]))
    else:
        print("[demo-admin] Size already exists")
    if "Color" not in existing_opts:
        pretty(c.add_option(pid, "Color", ["Black", "White"]))
    else:
        print("[demo-admin] Color already exists")

    print("\n[demo-admin] Ensure variants")
    variants = c.list_variants(pid)
    if not (isinstance(variants, list) and variants):
        pretty(c.generate_variants(pid, price_cents=2499, currency="EUR", initial_stock=25))
        variants = c.list_variants(pid)
    print(f"[demo-admin] Variants: {len(variants) if isinstance(variants, list) else 0}")


def act_demo_storefront(args):
    # Guest/cart flow using separate cookie jar typically
    c = ApiClient(args.base_url, args.cookie_file, verbose=not args.quiet)
    print("[demo-storefront] Catalog products (PUBLISHED)")
    cat = c.catalog_products(page=1, page_size=12)
    pretty(cat)

    if isinstance(cat, dict) and cat.get("items"):
        product = cat["items"][0]
        slug = product["slug"]
        print(f"\n[demo-storefront] PDP for {slug}")
        pdp = c.catalog_product(slug)
        pretty(pdp)
        # pick first variant
        variants = pdp.get("variants", [])
        if variants:
            vid = variants[0]["id"]
            print(f"\n[demo-storefront] Add to cart variant {vid}")
            pretty(c.cart_add_item(vid, qty=2))
        else:
            print("[demo-storefront] No variants found, abort.")
            return
    else:
        print("[demo-storefront] No published products; run demo-admin first.")
        return

    print("\n[demo-storefront] Show cart")
    pretty(c.cart_get())

    print("\n[demo-storefront] Checkout (manual provider) as guest")
    pretty(c.checkout(email=args.email))


# ---------------- Argparse ----------------

def build_parser():
    p = argparse.ArgumentParser(description="Store Admin + Storefront CLI")
    p.add_argument("--base-url", default=DEFAULT_BASE_URL, help=f"API base URL (default: {DEFAULT_BASE_URL})")
    p.add_argument("--cookie-file", default=None, help="Path to persist cookies between runs")
    p.add_argument("--quiet", action="store_true", help="Less verbose output")

    sub = p.add_subparsers(dest="cmd", required=True)

    # auth
    preg = sub.add_parser("register", help="Register user")
    preg.add_argument("--email", required=True)
    preg.add_argument("--password", required=True)
    preg.add_argument("--name", required=True)
    preg.set_defaults(func=act_register)

    plog = sub.add_parser("login", help="Login and store session cookie")
    plog.add_argument("--email", default=DEFAULT_ADMIN_EMAIL)
    plog.add_argument("--password", default=DEFAULT_ADMIN_PASSWORD)
    plog.set_defaults(func=act_login)

    pme = sub.add_parser("me", help="Show current user")
    pme.set_defaults(func=act_me)

    plo = sub.add_parser("logout", help="Logout")
    plo.set_defaults(func=act_logout)

    # brands
    pb = sub.add_parser("brands", help="Brand operations")
    pbsub = pb.add_subparsers(dest="action", required=True)

    pbl = pbsub.add_parser("list", help="List brands")
    pbl.add_argument("--q", default="")
    pbl.add_argument("--page", type=int, default=1)
    pbl.add_argument("--page-size", type=int, default=20)
    pbl.set_defaults(func=act_brands)

    pbc = pbsub.add_parser("create", help="Create a brand")
    pbc.add_argument("--name", required=True)
    pbc.add_argument("--slug")
    pbc.add_argument("--description")
    pbc.add_argument("--website")
    pbc.add_argument("--logo-url")
    pbc.set_defaults(func=act_brands)

    pbu = pbsub.add_parser("update", help="Update a brand")
    pbu.add_argument("--id", required=True)
    pbu.add_argument("--name")
    pbu.add_argument("--slug")
    pbu.add_argument("--description", nargs="?", const=None)
    pbu.add_argument("--website", nargs="?", const=None)
    pbu.add_argument("--logo-url", nargs="?", const=None)
    pbu.set_defaults(func=act_brands)

    pbd = pbsub.add_parser("delete", help="Delete a brand")
    pbd.add_argument("--id", required=True)
    pbd.set_defaults(func=act_brands)

    # categories
    pc = sub.add_parser("categories", help="Category operations")
    pcsub = pc.add_subparsers(dest="action", required=True)

    pcl = pcsub.add_parser("list", help="List categories")
    pcl.add_argument("--q", default="")
    pcl.add_argument("--page", type=int, default=1)
    pcl.add_argument("--page-size", type=int, default=20)
    pcl.add_argument("--parent-id", default=None)
    pcl.set_defaults(func=act_categories)

    pcc = pcsub.add_parser("create", help="Create category")
    pcc.add_argument("--name", required=True)
    pcc.add_argument("--slug")
    pcc.add_argument("--description")
    pcc.add_argument("--parent-id")
    pcc.set_defaults(func=act_categories)

    pcu = pcsub.add_parser("update", help="Update category")
    pcu.add_argument("--id", required=True)
    pcu.add_argument("--name")
    pcu.add_argument("--slug")
    pcu.add_argument("--description", nargs="?", const=None)
    pcu.add_argument("--parent-id", nargs="?", const=None)
    pcu.set_defaults(func=act_categories)

    pcd = pcsub.add_parser("delete", help="Delete category")
    pcd.add_argument("--id", required=True)
    pcd.set_defaults(func=act_categories)

    # products
    pp = sub.add_parser("products", help="Product operations")
    pps = pp.add_subparsers(dest="action", required=True)

    ppl = pps.add_parser("list", help="List products")
    ppl.add_argument("--q", default="")
    ppl.add_argument("--page", type=int, default=1)
    ppl.add_argument("--page-size", type=int, default=20)
    ppl.set_defaults(func=act_products)

    ppc = pps.add_parser("create", help="Create product")
    ppc.add_argument("--title", required=True)
    ppc.add_argument("--slug")
    ppc.add_argument("--description")
    ppc.add_argument("--brand-id")
    ppc.add_argument("--status", choices=["DRAFT", "PUBLISHED", "ARCHIVED"])
    ppc.add_argument("--sku-prefix")
    ppc.add_argument("--image")
    ppc.add_argument("--category-ids", nargs="*")
    ppc.set_defaults(func=act_products)

    ppu = pps.add_parser("update", help="Update product")
    ppu.add_argument("--id", required=True)
    ppu.add_argument("--title")
    ppu.add_argument("--slug")
    ppu.add_argument("--description", nargs="?", const=None)
    ppu.add_argument("--brand-id", nargs="?", const=None)
    ppu.add_argument("--status", choices=["DRAFT", "PUBLISHED", "ARCHIVED"])
    ppu.add_argument("--sku-prefix", nargs="?", const=None)
    ppu.add_argument("--image", nargs="?", const=None)
    ppu.add_argument("--category-ids", nargs="*")
    ppu.set_defaults(func=act_products)

    ppd = pps.add_parser("delete", help="Delete product")
    ppd.add_argument("--id", required=True)
    ppd.set_defaults(func=act_products)

    ppg = pps.add_parser("get", help="Get product (full)")
    ppg.add_argument("--id", required=True)
    ppg.set_defaults(func=act_products)

    # options
    po = sub.add_parser("options", help="Product options")
    pos = po.add_subparsers(dest="action", required=True)

    pol = pos.add_parser("list", help="List options")
    pol.add_argument("--product-id", required=True)
    pol.set_defaults(func=act_options)

    poa = pos.add_parser("add", help="Add option + values")
    poa.add_argument("--product-id", required=True)
    poa.add_argument("--name", required=True)
    poa.add_argument("--values", nargs="+", required=True)
    poa.add_argument("--position", type=int)
    poa.set_defaults(func=act_options)

    # variants (collection)
    pv = sub.add_parser("variants", help="Variants for a product")
    pvs = pv.add_subparsers(dest="action", required=True)

    pvl = pvs.add_parser("list", help="List variants")
    pvl.add_argument("--product-id", required=True)
    pvl.set_defaults(func=act_variants)

    pvg = pvs.add_parser("generate", help="Generate cartesian variants")
    pvg.add_argument("--product-id", required=True)
    pvg.add_argument("--price-cents", type=int, required=True)
    pvg.add_argument("--currency", default="EUR")
    pvg.add_argument("--stock", type=int, default=0)
    pvg.set_defaults(func=act_variants)

    pvc = pvs.add_parser("create", help="Create explicit combinations (JSON)")
    pvc.add_argument("--product-id", required=True)
    pvc.add_argument("--currency", default="EUR")
    pvc.add_argument("--combo", nargs="+", required=True,
                     help='Blobs like \'{"values":{"Size":"M","Color":"Black"},"priceCents":2499,"initialStock":10}\'')
    pvc.set_defaults(func=act_variants)

    # single variant
    sv = sub.add_parser("variant", help="Single variant")
    svs = sv.add_subparsers(dest="action", required=True)

    svu = svs.add_parser("update", help="Update variant")
    svu.add_argument("--variant-id", required=True)
    svu.add_argument("--sku")
    svu.add_argument("--title")
    svu.add_argument("--price-cents", type=int)
    svu.add_argument("--compare-at-cents", type=int)
    svu.add_argument("--cost-cents", type=int)
    svu.add_argument("--currency")
    svu.add_argument("--track-inventory", dest="track_inventory", action="store_true")
    svu.add_argument("--no-track-inventory", dest="track_inventory", action="store_false")
    svu.add_argument("--default", action="store_true")
    svu.set_defaults(func=act_variant, track_inventory=None)

    svd = svs.add_parser("delete", help="Delete variant")
    svd.add_argument("--variant-id", required=True)
    svd.set_defaults(func=act_variant)

    # stock
    st = sub.add_parser("stock", help="Stock adjustments")
    sts = st.add_subparsers(dest="action", required=True)

    sts_set = sts.add_parser("set", help="Set on-hand")
    sts_set.add_argument("--variant-id", required=True)
    sts_set.add_argument("--on-hand", type=int, required=True)
    sts_set.add_argument("--warehouse-id")
    sts_set.add_argument("--reason", default="setOnHand")
    sts_set.set_defaults(func=act_stock)

    sts_delta = sts.add_parser("delta", help="Delta on-hand")
    sts_delta.add_argument("--variant-id", required=True)
    sts_delta.add_argument("--delta", type=int, required=True)
    sts_delta.add_argument("--warehouse-id")
    sts_delta.add_argument("--reason", default="deltaOnHand")
    sts_delta.set_defaults(func=act_stock)

    # catalog
    pcg = sub.add_parser("catalog", help="Public catalog")
    pcgs = pcg.add_subparsers(dest="section", required=True)

    pcg_products = pcgs.add_parser("products", help="List products")
    pcg_products.add_argument("--page", type=int, default=1)
    pcg_products.add_argument("--page-size", type=int, default=24)
    pcg_products.add_argument("--q", default="")
    pcg_products.add_argument("--brand", default="")
    pcg_products.add_argument("--category", default="")
    pcg_products.add_argument("--sort", choices=["newest", "title_asc", "title_desc"], default="newest")
    pcg_products.add_argument("--min-price", type=int)
    pcg_products.add_argument("--max-price", type=int)
    pcg_products.set_defaults(func=act_catalog)

    pcg_product = pcgs.add_parser("product", help="Product detail by slug")
    pcg_product.add_argument("--slug", required=True)
    pcg_product.set_defaults(func=act_catalog)

    pcg_brands = pcgs.add_parser("brands", help="List brands")
    pcg_brands.add_argument("--q", default="")
    pcg_brands.set_defaults(func=act_catalog)

    pcg_cats = pcgs.add_parser("categories", help="List categories")
    pcg_cats.add_argument("--parent", default="root")
    pcg_cats.add_argument("--page", type=int, default=1)
    pcg_cats.add_argument("--page-size", type=int, default=50)
    pcg_cats.set_defaults(func=act_catalog)

    # cart
    crt = sub.add_parser("cart", help="Cart")
    crts = crt.add_subparsers(dest="action", required=True)

    crt_get = crts.add_parser("get", help="Get cart")
    crt_get.set_defaults(func=act_cart)

    crt_clear = crts.add_parser("clear", help="Clear cart")
    crt_clear.set_defaults(func=act_cart)

    crt_add = crts.add_parser("add", help="Add item")
    crt_add.add_argument("--variant-id", required=True)
    crt_add.add_argument("--qty", type=int, default=1)
    crt_add.set_defaults(func=act_cart)

    crt_set = crts.add_parser("set", help="Set item quantity")
    crt_set.add_argument("--item-id", required=True)
    crt_set.add_argument("--qty", type=int, required=True)
    crt_set.set_defaults(func=act_cart)

    crt_rm = crts.add_parser("remove", help="Remove item")
    crt_rm.add_argument("--item-id", required=True)
    crt_rm.set_defaults(func=act_cart)

    crt_apply = crts.add_parser("apply-coupon", help="Apply coupon code")
    crt_apply.add_argument("--code", required=True)
    crt_apply.set_defaults(func=act_cart)

    crt_unapply = crts.add_parser("remove-coupon", help="Remove coupon")
    crt_unapply.set_defaults(func=act_cart)

    # checkout
    chk = sub.add_parser("checkout", help="Checkout (manual)")
    chk.add_argument("--email", help="Required if not logged in")
    chk.add_argument("--provider", default="manual", choices=["manual"])
    chk.add_argument("--auth-only", action="store_true", help="If set, do auth only (no capture) when provider supports it")
    chk.add_argument("--shipping-address-id")
    chk.add_argument("--billing-address-id")
    chk.set_defaults(func=act_checkout)

    # demos
    dma = sub.add_parser("demo-admin", help="Seed brand/cats/product/options/variants")
    dma.add_argument("--email", default=DEFAULT_ADMIN_EMAIL)
    dma.add_argument("--password", default=DEFAULT_ADMIN_PASSWORD)
    dma.set_defaults(func=act_demo_admin)

    dms = sub.add_parser("demo-storefront", help="Browse catalog -> add to cart -> checkout as guest")
    dms.add_argument("--email", default="buyer@local.test")
    dms.set_defaults(func=act_demo_storefront)

    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except ApiError as e:
        print(str(e), file=sys.stderr)
        sys.exit(2)
    except requests.RequestException as e:
        print(f"Network error: {e}", file=sys.stderr)
        sys.exit(3)


if __name__ == "__main__":
    main()
