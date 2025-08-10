#!/usr/bin/env python3
"""
Products/Variants admin tester for your Next.js + Prisma API.

Requirements:
  pip install requests

Quick demo (runs end-to-end on localhost with default admin creds):
  python product_variant_tester.py demo

Custom base URL / cookie persistence:
  python product_variant_tester.py --base-url http://192.168.68.150:3000 --cookie-file session.cookies demo

Manual ops:
  # login
  python product_variant_tester.py --cookie-file session.cookies login --email admin@local.test --password admin123!

  # create product
  python product_variant_tester.py --cookie-file session.cookies products create --title "Athletic Tee" --slug athletic-tee

  # add options
  python product_variant_tester.py --cookie-file session.cookies options add --product-id PRODUCT_ID --name Size --values S M L
  python product_variant_tester.py --cookie-file session.cookies options add --product-id PRODUCT_ID --name Color --values Black White

  # generate variants
  python product_variant_tester.py --cookie-file session.cookies variants generate --product-id PRODUCT_ID --price-cents 2499 --stock 25

  # list variants
  python product_variant_tester.py --cookie-file session.cookies variants list --product-id PRODUCT_ID

  # update variant + adjust stock
  python product_variant_tester.py --cookie-file session.cookies variant update --variant-id VARIANT_ID --price-cents 2199 --default
  python product_variant_tester.py --cookie-file session.cookies stock set --variant-id VARIANT_ID --on-hand 40 --reason counted
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
    def login(self, email: str, password: str) -> Any:
        return self.request("POST", "/api/auth/login", json_body={"email": email, "password": password})

    def me(self) -> Any:
        return self.request("GET", "/api/auth/me")

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

    # helpers
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


def pretty(obj):
    print(json.dumps(obj, indent=2, ensure_ascii=False))


# ---------------- CLI actions ----------------

def act_login(args):
    c = ApiClient(args.base_url, args.cookie_file, verbose=not args.quiet)
    res = c.login(args.email, args.password)
    pretty(res)


def act_products(args):
    c = ApiClient(args.base_url, args.cookie_file, verbose=not args.quiet)
    if args.action == "list":
        res = c.list_products(page=args.page, page_size=args.page_size, q=args.q or "")
        pretty(res)
    elif args.action == "create":
        payload = {"title": args.title}
        if args.slug:
            payload["slug"] = args.slug
        if args.description:
            payload["description"] = args.description
        if args.brand_id is not None:
            payload["brandId"] = args.brand_id
        if args.status:
            payload["status"] = args.status
        if args.sku_prefix:
            payload["skuPrefix"] = args.sku_prefix
        if args.image:
            payload["images"] = [{"url": args.image}]
        if args.category_ids:
            payload["categoryIds"] = args.category_ids
        pretty(c.create_product(**payload))
    elif args.action == "update":
        payload = {}
        if args.title:
            payload["title"] = args.title
        if args.slug:
            payload["slug"] = args.slug
        if args.description is not None:
            payload["description"] = args.description
        if args.brand_id is not None:
            payload["brandId"] = args.brand_id
        if args.status:
            payload["status"] = args.status
        if args.sku_prefix is not None:
            payload["skuPrefix"] = args.sku_prefix
        if args.image is not None:
            payload["images"] = [{"url": args.image}]
        if args.category_ids is not None:
            payload["categoryIds"] = args.category_ids
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
        # expects {"values":{"Size":"M","Color":"Black"}, "priceCents":2499, "initialStock":10}
        combos = [json.loads(s) for s in args.combo]
        pretty(c.create_combinations(args.product_id, combos, currency=args.currency))


def act_variant(args):
    c = ApiClient(args.base_url, args.cookie_file, verbose=not args.quiet)
    if args.action == "update":
        payload = {}
        if args.sku:
            payload["sku"] = args.sku
        if args.title:
            payload["title"] = args.title
        if args.price_cents is not None:
            payload["priceCents"] = args.price_cents
        if args.compare_at_cents is not None:
            payload["compareAtCents"] = args.compare_at_cents
        if args.cost_cents is not None:
            payload["costCents"] = args.cost_cents
        if args.currency:
            payload["currency"] = args.currency
        if args.track_inventory is not None:
            payload["trackInventory"] = args.track_inventory
        if args.default:
            payload["isDefault"] = True
        pretty(c.update_variant(args.variant_id, **payload))
    elif args.action == "delete":
        pretty(c.delete_variant(args.variant_id))


def act_stock(args):
    c = ApiClient(args.base_url, args.cookie_file, verbose=not args.quiet)
    if args.action == "set":
        pretty(c.set_stock(args.variant_id, on_hand=args.on_hand, reason=args.reason, warehouse_id=args.warehouse_id))
    elif args.action == "delta":
        pretty(c.delta_stock(args.variant_id, delta=args.delta, reason=args.reason, warehouse_id=args.warehouse_id))


def act_demo(args):
    c = ApiClient(args.base_url, args.cookie_file, verbose=not args.quiet)
    print(f"[demo] Logging in as {args.email}")
    c.login(args.email, args.password)
    me = c.me()
    print("[demo] Authenticated user:")
    pretty(me)

    # Ensure product
    print("\n[demo] Ensure product 'Athletic Tee'")
    prod = c.ensure_product(
        title="Athletic Tee",
        slug="athletic-tee",
        description="Breathable tee",
        status="DRAFT",
        skuPrefix="TEE",
        images=[{"url": "https://picsum.photos/seed/athtee/800/800"}],
    )
    pretty(prod)
    pid = prod["id"]

    # Ensure options Size/Color
    print("\n[demo] Ensure options Size / Color")
    existing_opts = {o["name"] for o in c.list_options(pid)}
    if "Size" not in existing_opts:
        pretty(c.add_option(pid, "Size", ["S", "M", "L"]))
    else:
        print("[demo] Size already exists")
    if "Color" not in existing_opts:
        pretty(c.add_option(pid, "Color", ["Black", "White"]))
    else:
        print("[demo] Color already exists")

    # Generate variants if none exist
    print("\n[demo] Generate variants (if needed)")
    variants = c.list_variants(pid)
    if isinstance(variants, list) and len(variants) > 0:
        print(f"[demo] Variants already exist: {len(variants)}")
    else:
        try:
            pretty(c.generate_variants(pid, price_cents=2499, currency="EUR", initial_stock=25))
        except ApiError as e:
            # likely duplicate SKU; proceed to list
            print(f"[demo] generateAll failed (likely duplicates): {e}")
    variants = c.list_variants(pid)
    pretty(variants if isinstance(variants, list) else [])

    # Update first variant + set stock
    if isinstance(variants, list) and variants:
        vid = variants[0]["id"]
        print("\n[demo] Update first variant price -> 2199 & default=true")
        pretty(c.update_variant(vid, priceCents=2199, isDefault=True))
        print("\n[demo] Set stock of first variant to 40")
        pretty(c.set_stock(vid, on_hand=40, reason="counted"))

    # Optionally cleanup
    if args.cleanup:
        print("\n[demo] Cleanup: delete product")
        pretty(c.delete_product(pid))


# ---------------- Argparse ----------------

def build_parser():
    p = argparse.ArgumentParser(description="Products & Variants Admin Tester")
    p.add_argument("--base-url", default=DEFAULT_BASE_URL, help=f"API base URL (default: {DEFAULT_BASE_URL})")
    p.add_argument("--cookie-file", default=None, help="Path to persist cookies between runs")
    p.add_argument("--quiet", action="store_true", help="Less verbose output")

    sub = p.add_subparsers(dest="cmd", required=True)

    # login
    pl = sub.add_parser("login", help="Login and store session cookie")
    pl.add_argument("--email", default=DEFAULT_ADMIN_EMAIL)
    pl.add_argument("--password", default=DEFAULT_ADMIN_PASSWORD)
    pl.set_defaults(func=act_login)

    # products
    pp = sub.add_parser("products", help="Product operations")
    pps = pp.add_subparsers(dest="action", required=True)

    ppl = pps.add_parser("list", help="List products")
    ppl.add_argument("--q", default="")
    ppl.add_argument("--page", type=int, default=1)
    ppl.add_argument("--page-size", type=int, default=20)
    ppl.set_defaults(func=act_products)

    ppc = pps.add_parser("create", help="Create a product")
    ppc.add_argument("--title", required=True)
    ppc.add_argument("--slug")
    ppc.add_argument("--description")
    ppc.add_argument("--brand-id")
    ppc.add_argument("--status", choices=["DRAFT", "PUBLISHED", "ARCHIVED"])
    ppc.add_argument("--sku-prefix")
    ppc.add_argument("--image")
    ppc.add_argument("--category-ids", nargs="*")
    ppc.set_defaults(func=act_products)

    ppu = pps.add_parser("update", help="Update a product")
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

    ppd = pps.add_parser("delete", help="Delete a product")
    ppd.add_argument("--id", required=True)
    ppd.set_defaults(func=act_products)

    ppg = pps.add_parser("get", help="Get a product (full)")
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

    # variants collection
    pv = sub.add_parser("variants", help="Variants for a product")
    pvs = pv.add_subparsers(dest="action", required=True)

    pvl = pvs.add_parser("list", help="List variants for product")
    pvl.add_argument("--product-id", required=True)
    pvl.set_defaults(func=act_variants)

    pvg = pvs.add_parser("generate", help="Generate cartesian variants from options")
    pvg.add_argument("--product-id", required=True)
    pvg.add_argument("--price-cents", type=int, required=True)
    pvg.add_argument("--currency", default="EUR")
    pvg.add_argument("--stock", type=int, default=0)
    pvg.set_defaults(func=act_variants)

    pvc = pvs.add_parser("create", help="Create explicit combinations (JSON strings)")
    pvc.add_argument("--product-id", required=True)
    pvc.add_argument("--currency", default="EUR")
    pvc.add_argument("--combo", nargs="+", required=True,
                     help='One or more JSON blobs, e.g. \'{"values":{"Size":"M","Color":"Black"},"priceCents":2499,"initialStock":10}\'')
    pvc.set_defaults(func=act_variants)

    # single variant
    sv = sub.add_parser("variant", help="Single variant operations")
    svs = sv.add_subparsers(dest="action", required=True)

    svu = svs.add_parser("update", help="Update a variant")
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

    svd = svs.add_parser("delete", help="Delete a variant")
    svd.add_argument("--variant-id", required=True)
    svd.set_defaults(func=act_variant)

    # stock
    st = sub.add_parser("stock", help="Variant stock adjustments")
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

    # demo
    pd = sub.add_parser("demo", help="End-to-end demo for products/options/variants")
    pd.add_argument("--email", default=DEFAULT_ADMIN_EMAIL)
    pd.add_argument("--password", default=DEFAULT_ADMIN_PASSWORD)
    pd.add_argument("--cleanup", action="store_true", help="Delete the product at the end")
    pd.set_defaults(func=act_demo)

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
