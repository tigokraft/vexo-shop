#!/usr/bin/env python3
"""
store_tui.py — lightweight terminal UI wrapper for store_cli.ApiClient

Usage:
  python store_tui.py
"""

import json
import os
import sys
from typing import Any, Dict, Optional, List

# Try to import the ApiClient from your CLI file.
# Works whether you named it store_cli.py (from my last message) or admin_automation.py (older name).
try:
    from store_cli import ApiClient, ApiError, DEFAULT_BASE_URL, DEFAULT_ADMIN_EMAIL, DEFAULT_ADMIN_PASSWORD  # type: ignore
except ImportError:
    try:
        from admin_automation import ApiClient, ApiError, DEFAULT_BASE_URL, DEFAULT_ADMIN_EMAIL, DEFAULT_ADMIN_PASSWORD  # type: ignore
    except ImportError as e:
        print("Unable to import ApiClient. Make sure store_cli.py (or admin_automation.py) is beside this file.")
        raise

# ---------- Helpers ----------

def pretty(obj: Any):
    print(json.dumps(obj, indent=2, ensure_ascii=False))

def ask(prompt: str, default: Optional[str] = None) -> str:
    sfx = f" [{default}]" if default not in (None, "") else ""
    val = input(f"{prompt}{sfx}: ").strip()
    return default if (val == "" and default is not None) else val

def ask_int(prompt: str, default: Optional[int] = None) -> int:
    while True:
        s = ask(prompt, str(default) if default is not None else None)
        try:
            return int(s)
        except ValueError:
            print("Enter a valid integer.")

def press_enter():
    input("\n(enter to continue) ")

def divider(title: str = ""):
    print("\n" + "=" * 60)
    if title:
        print(title)
        print("-" * 60)

def confirm(q: str, default_yes=True) -> bool:
    d = "Y/n" if default_yes else "y/N"
    a = input(f"{q} [{d}]: ").strip().lower()
    if a == "" and default_yes: return True
    if a == "" and not default_yes: return False
    return a in ("y", "yes")

# ---------- TUI ----------

class Context:
    def __init__(self):
        self.base_url = os.environ.get("STORE_BASE_URL", DEFAULT_BASE_URL)
        self.cookie_file_admin = "admin.cookies"
        self.cookie_file_cart = "cart.cookies"
        self.cookie_file_user = "user.cookies"
        self.active = "cart"  # "admin" | "cart" | "user"
        self.client = self._mk_client()

    def _mk_client(self) -> ApiClient:
        cookie = {
            "admin": self.cookie_file_admin,
            "cart": self.cookie_file_cart,
            "user": self.cookie_file_user,
        }[self.active]
        return ApiClient(self.base_url, cookie, verbose=True)

    def switch(self, which: str):
        self.active = which
        self.client = self._mk_client()

ctx = Context()

# ---------- Auth ----------

def menu_auth():
    while True:
        divider("Auth")
        print(f"Active session: {ctx.active}  |  base: {ctx.base_url}")
        print("1) Login")
        print("2) Register")
        print("3) Me")
        print("4) Logout")
        print("5) Switch session (admin/cart/user)")
        print("0) Back")
        ch = input("> ").strip()
        try:
            if ch == "1":
                email = ask("Email", DEFAULT_ADMIN_EMAIL if ctx.active == "admin" else None)
                pwd = ask("Password", DEFAULT_ADMIN_PASSWORD if ctx.active == "admin" else None)
                pretty(ctx.client.login(email, pwd))
                press_enter()
            elif ch == "2":
                email = ask("Email")
                pwd = ask("Password")
                name = ask("Name", "User")
                pretty(ctx.client.register(email, pwd, name))
                press_enter()
            elif ch == "3":
                pretty(ctx.client.me())
                press_enter()
            elif ch == "4":
                pretty(ctx.client.logout())
                press_enter()
            elif ch == "5":
                which = ask("Which session? (admin/cart/user)", ctx.active).lower()
                if which in ("admin", "cart", "user"):
                    ctx.switch(which)
                    print(f"Switched to {which}")
                else:
                    print("Invalid.")
                press_enter()
            elif ch == "0":
                return
        except ApiError as e:
            print(e)
            press_enter()

# ---------- Admin: Brands/Categories/Products ----------

def admin_brands():
    while True:
        divider("Admin / Brands")
        print("1) List")
        print("2) Create")
        print("3) Update")
        print("4) Delete")
        print("0) Back")
        ch = input("> ").strip()
        try:
            if ch == "1":
                q = ask("q", "")
                page = ask_int("page", 1)
                size = ask_int("page-size", 20)
                pretty(ctx.client.list_brands(page=page, page_size=size, q=q))
                press_enter()
            elif ch == "2":
                name = ask("name")
                slug = ask("slug (optional)", "")
                desc = ask("description (optional)", "")
                website = ask("website (optional)", "")
                logo = ask("logoUrl (optional)", "")
                payload = {"name": name}
                if slug: payload["slug"] = slug
                if desc: payload["description"] = desc
                if website: payload["website"] = website
                if logo: payload["logoUrl"] = logo
                pretty(ctx.client.create_brand(**payload))
                press_enter()
            elif ch == "3":
                bid = ask("brand id")
                payload: Dict[str, Any] = {}
                if confirm("Change name?", False): payload["name"] = ask("name")
                if confirm("Change slug?", False): payload["slug"] = ask("slug")
                if confirm("Change description?", False): payload["description"] = ask("description", "")
                if confirm("Change website?", False): payload["website"] = ask("website", "")
                if confirm("Change logoUrl?", False): payload["logoUrl"] = ask("logoUrl", "")
                pretty(ctx.client.update_brand(bid, **payload))
                press_enter()
            elif ch == "4":
                bid = ask("brand id")
                if confirm("Really delete?"):
                    pretty(ctx.client.delete_brand(bid))
                press_enter()
            elif ch == "0":
                return
        except ApiError as e:
            print(e); press_enter()

def admin_categories():
    while True:
        divider("Admin / Categories")
        print("1) List")
        print("2) Create")
        print("3) Update")
        print("4) Delete")
        print("0) Back")
        ch = input("> ").strip()
        try:
            if ch == "1":
                q = ask("q", "")
                page = ask_int("page", 1)
                size = ask_int("page-size", 20)
                parent = ask("parentId (optional)", "")
                pretty(ctx.client.list_categories(page=page, page_size=size, q=q, parent_id=(parent or None)))
                press_enter()
            elif ch == "2":
                name = ask("name")
                slug = ask("slug (optional)", "")
                desc = ask("description (optional)", "")
                parent = ask("parentId (optional)", "")
                payload = {"name": name}
                if slug: payload["slug"] = slug
                if desc: payload["description"] = desc
                if parent: payload["parentId"] = parent
                pretty(ctx.client.create_category(**payload))
                press_enter()
            elif ch == "3":
                cid = ask("category id")
                payload: Dict[str, Any] = {}
                if confirm("Change name?", False): payload["name"] = ask("name")
                if confirm("Change slug?", False): payload["slug"] = ask("slug")
                if confirm("Change description?", False): payload["description"] = ask("description", "")
                if confirm("Change parentId?", False): payload["parentId"] = ask("parentId", "")
                pretty(ctx.client.update_category(cid, **payload))
                press_enter()
            elif ch == "4":
                cid = ask("category id")
                if confirm("Really delete?"):
                    pretty(ctx.client.delete_category(cid))
                press_enter()
            elif ch == "0":
                return
        except ApiError as e:
            print(e); press_enter()

def admin_products():
    while True:
        divider("Admin / Products")
        print("1) List")
        print("2) Create")
        print("3) Update")
        print("4) Delete")
        print("5) Options: List/Add")
        print("6) Variants: List/Generate")
        print("7) Stock: Set/Delta")
        print("0) Back")
        ch = input("> ").strip()
        try:
            if ch == "1":
                q = ask("q", "")
                page = ask_int("page", 1)
                size = ask_int("page-size", 20)
                pretty(ctx.client.list_products(page=page, page_size=size, q=q))
                press_enter()
            elif ch == "2":
                title = ask("title")
                slug = ask("slug (optional)", "")
                desc = ask("description (optional)", "")
                brand = ask("brandId (optional)", "")
                status = ask("status [DRAFT|PUBLISHED|ARCHIVED]", "DRAFT")
                sku = ask("skuPrefix (optional)", "")
                image = ask("image url (optional)", "")
                cat_ids = ask("categoryIds (space-separated, optional)", "")
                payload = {"title": title}
                if slug: payload["slug"] = slug
                if desc: payload["description"] = desc
                if brand: payload["brandId"] = brand
                if status: payload["status"] = status
                if sku: payload["skuPrefix"] = sku
                if image: payload["images"] = [{"url": image}]
                if cat_ids: payload["categoryIds"] = cat_ids.split()
                pretty(ctx.client.create_product(**payload))
                press_enter()
            elif ch == "3":
                pid = ask("product id")
                payload: Dict[str, Any] = {}
                if confirm("Change title?", False): payload["title"] = ask("title")
                if confirm("Change slug?", False): payload["slug"] = ask("slug")
                if confirm("Change description?", False): payload["description"] = ask("description", "")
                if confirm("Change brandId?", False): payload["brandId"] = ask("brandId", "")
                if confirm("Change status?", False): payload["status"] = ask("status", "DRAFT")
                if confirm("Change skuPrefix?", False): payload["skuPrefix"] = ask("skuPrefix", "")
                if confirm("Replace image?", False):
                    img = ask("image url (blank to clear)", "")
                    payload["images"] = ([{"url": img}] if img else [])
                if confirm("Replace categoryIds?", False):
                    ids = ask("categoryIds (space-separated)", "")
                    payload["categoryIds"] = ids.split() if ids else []
                pretty(ctx.client.update_product(pid, **payload))
                press_enter()
            elif ch == "4":
                pid = ask("product id")
                if confirm("Really delete?"):
                    pretty(ctx.client.delete_product(pid))
                press_enter()
            elif ch == "5":
                pid = ask("product id")
                print("a) List options")
                print("b) Add option")
                sub = input("> ").strip().lower()
                if sub == "a":
                    pretty(ctx.client.list_options(pid)); press_enter()
                elif sub == "b":
                    name = ask("option name (e.g., Size)")
                    values = ask("values (space-separated)", "S M L").split()
                    pretty(ctx.client.add_option(pid, name, values))
                    press_enter()
            elif ch == "6":
                pid = ask("product id")
                print("a) List variants")
                print("b) Generate cartesian variants")
                sub = input("> ").strip().lower()
                if sub == "a":
                    pretty(ctx.client.list_variants(pid)); press_enter()
                elif sub == "b":
                    price = ask_int("priceCents", 2499)
                    stock = ask_int("initial stock", 0)
                    pretty(ctx.client.generate_variants(pid, price_cents=price, currency="EUR", initial_stock=stock))
                    press_enter()
            elif ch == "7":
                print("a) Set on-hand")
                print("b) Delta on-hand")
                sub = input("> ").strip().lower()
                vid = ask("variant id")
                if sub == "a":
                    onh = ask_int("onHand", 10)
                    pretty(ctx.client.set_stock(vid, on_hand=onh))
                elif sub == "b":
                    d = ask_int("delta (+/-)", 1)
                    pretty(ctx.client.delta_stock(vid, delta=d))
                press_enter()
            elif ch == "0":
                return
        except ApiError as e:
            print(e); press_enter()

# ---------- Admin: Coupons / Orders / Stats ----------

def admin_coupons():
    while True:
        divider("Admin / Coupons")
        print("1) List")
        print("2) Create (raw JSON)")
        print("3) Update (raw JSON)")
        print("4) Delete")
        print("0) Back")
        ch = input("> ").strip()
        try:
            if ch == "1":
                q = ask("q", "")
                page = ask_int("page", 1)
                size = ask_int("page-size", 50)
                pretty(ctx.client.admin_list_coupons(page=page, page_size=size, q=q)); press_enter()
            elif ch == "2":
                raw = ask("JSON payload", '{"code":"SAVE10","type":"PERCENT","value":10,"maxUses":100}')
                pretty(ctx.client.admin_create_coupon(json.loads(raw))); press_enter()
            elif ch == "3":
                cid = ask("coupon id")
                raw = ask("JSON payload", '{"active":true}')
                pretty(ctx.client.admin_update_coupon(cid, json.loads(raw))); press_enter()
            elif ch == "4":
                cid = ask("coupon id")
                if confirm("Really delete?"):
                    pretty(ctx.client.admin_delete_coupon(cid))
                press_enter()
            elif ch == "0":
                return
        except ApiError as e:
            print(e); press_enter()

def admin_orders_stats():
    while True:
        divider("Admin / Orders & Stats")
        print("1) List orders")
        print("2) Get order")
        print("3) Update order (raw JSON)")
        print("4) Stats")
        print("0) Back")
        ch = input("> ").strip()
        try:
            if ch == "1":
                page = ask_int("page", 1)
                size = ask_int("page-size", 50)
                status = ask("status filter (optional)", "")
                q = ask("q (optional)", "")
                pretty(ctx.client.admin_orders(page=page, page_size=size, status=(status or None), q=q))
                press_enter()
            elif ch == "2":
                oid = ask("order id")
                pretty(ctx.client.admin_order_get(oid)); press_enter()
            elif ch == "3":
                oid = ask("order id")
                raw = ask("JSON payload", '{"status":"FULFILLED"}')
                pretty(ctx.client.admin_order_update(oid, json.loads(raw))); press_enter()
            elif ch == "4":
                pretty(ctx.client.admin_stats()); press_enter()
            elif ch == "0":
                return
        except ApiError as e:
            print(e); press_enter()

# ---------- Catalog / Cart / Checkout ----------

def catalog_cart():
    while True:
        divider("Catalog / Cart / Checkout")
        print("1) Catalog products")
        print("2) Product by slug")
        print("3) Cart: get")
        print("4) Cart: clear")
        print("5) Cart: add item")
        print("6) Cart: set qty")
        print("7) Cart: remove item")
        print("8) Cart: apply coupon")
        print("9) Cart: remove coupon")
        print("a) Checkout (manual)")
        print("0) Back")
        ch = input("> ").strip().lower()
        try:
            if ch == "1":
                page = ask_int("page", 1)
                size = ask_int("page-size", 12)
                sort = ask("sort [newest|title_asc|title_desc]", "newest")
                pretty(ctx.client.catalog_products(page=page, page_size=size, sort=sort))
                press_enter()
            elif ch == "2":
                slug = ask("slug", "athletic-tee")
                pretty(ctx.client.catalog_product(slug)); press_enter()
            elif ch == "3":
                pretty(ctx.client.cart_get()); press_enter()
            elif ch == "4":
                pretty(ctx.client.cart_clear()); press_enter()
            elif ch == "5":
                vid = ask("variantId")
                qty = ask_int("qty", 1)
                pretty(ctx.client.cart_add_item(vid, qty)); press_enter()
            elif ch == "6":
                iid = ask("itemId")
                qty = ask_int("qty", 1)
                pretty(ctx.client.cart_update_item(iid, qty)); press_enter()
            elif ch == "7":
                iid = ask("itemId")
                pretty(ctx.client.cart_delete_item(iid)); press_enter()
            elif ch == "8":
                code = ask("coupon code", "SAVE10")
                pretty(ctx.client.cart_apply_coupon(code)); press_enter()
            elif ch == "9":
                pretty(ctx.client.cart_remove_coupon()); press_enter()
            elif ch == "a":
                email = ask("email (blank uses logged-in user)", "")
                pretty(ctx.client.checkout(email=(email or None))); press_enter()
            elif ch == "0":
                return
        except ApiError as e:
            print(e); press_enter()

# ---------- Account (customer) ----------

def account_menu():
    while True:
        divider("Account")
        print("1) My orders")
        print("2) Get my order")
        print("0) Back")
        ch = input("> ").strip()
        try:
            if ch == "1":
                pretty(ctx.client.account_orders()); press_enter()
            elif ch == "2":
                oid = ask("order id")
                pretty(ctx.client.account_order_get(oid)); press_enter()
            elif ch == "0":
                return
        except ApiError as e:
            print(e); press_enter()

# ---------- Demos ----------

def demo_admin():
    divider("Demo: Admin seed")
    email = ask("Admin email", DEFAULT_ADMIN_EMAIL)
    pwd = ask("Admin password", DEFAULT_ADMIN_PASSWORD)
    try:
        pretty(ctx.client.login(email, pwd))
        print("Logged in as:"); pretty(ctx.client.me())
        # Brand
        print("\nEnsure brand Orbit…")
        try:
            brand = ctx.client.create_brand(name="Orbit", slug="orbit", description="Performance basics")
        except ApiError:
            # list & find
            brand = ctx.client.find_brand(slug="orbit", name="Orbit") or {}
        pretty(brand)
        # Categories
        print("\nEnsure categories Women > Tops…")
        try:
            women = ctx.client.create_category(name="Women", slug="women")
        except ApiError:
            women = ctx.client.find_category(slug="women", name="Women") or {}
        try:
            tops = ctx.client.create_category(name="Tops", slug="tops", parentId=women.get("id"))
        except ApiError:
            tops = ctx.client.find_category(slug="tops", name="Tops", parent_id=women.get("id")) or {}
        pretty({"women": women.get("id"), "tops": tops.get("id")})
        # Product
        print("\nEnsure product Athletic Tee…")
        try:
            prod = ctx.client.create_product(
                title="Athletic Tee",
                slug="athletic-tee",
                description="Breathable tee",
                status="PUBLISHED",
                skuPrefix="TEE",
                images=[{"url": "https://picsum.photos/seed/athtee/800/800"}],
                brandId=brand.get("id"),
                categoryIds=[tops.get("id")] if tops.get("id") else [],
            )
        except ApiError:
            prod = ctx.client.find_product(slug="athletic-tee", title="Athletic Tee") or {}
        pretty(prod)
        pid = prod.get("id")
        if pid:
            # Options
            exist_names = {o["name"] for o in (ctx.client.list_options(pid) or [])}
            if "Size" not in exist_names:
                ctx.client.add_option(pid, "Size", ["S", "M", "L"])
            if "Color" not in exist_names:
                ctx.client.add_option(pid, "Color", ["Black", "White"])
            # Variants
            vlist = ctx.client.list_variants(pid)
            if not vlist:
                ctx.client.generate_variants(pid, price_cents=2499, currency="EUR", initial_stock=25)
            print("\nDone.")
        press_enter()
    except ApiError as e:
        print(e); press_enter()

def demo_storefront():
    divider("Demo: Storefront flow")
    try:
        print("Catalog products…")
        cat = ctx.client.catalog_products(page=1, page_size=12)
        pretty(cat)
        items = (cat or {}).get("items", [])
        if not items:
            print("No published products yet. Run Demo Admin first.")
            press_enter(); return
        slug = items[0]["slug"]
        print(f"\nPDP {slug}…")
        pdp = ctx.client.catalog_product(slug)
        pretty(pdp)
        vars = pdp.get("variants", [])
        if not vars:
            print("No variants."); press_enter(); return
        vid = vars[0]["id"]
        print(f"\nAdd to cart {vid} x2…")
        pretty(ctx.client.cart_add_item(vid, 2))
        print("\nCart:"); pretty(ctx.client.cart_get())
        print("\nCheckout as guest…")
        pretty(ctx.client.checkout(email="buyer@local.test"))
        press_enter()
    except ApiError as e:
        print(e); press_enter()

# ---------- Settings ----------

def settings_menu():
    while True:
        divider("Settings")
        print(f"Current base URL: {ctx.base_url}")
        print(f"Admin cookies: {ctx.cookie_file_admin}")
        print(f"Cart  cookies: {ctx.cookie_file_cart}")
        print(f"User  cookies: {ctx.cookie_file_user}")
        print("1) Change base URL")
        print("2) Change cookie files")
        print("0) Back")
        ch = input("> ").strip()
        if ch == "1":
            ctx.base_url = ask("New base URL", ctx.base_url)
            ctx.switch(ctx.active)
        elif ch == "2":
            ctx.cookie_file_admin = ask("Admin cookie file", ctx.cookie_file_admin)
            ctx.cookie_file_cart  = ask("Cart cookie file",  ctx.cookie_file_cart)
            ctx.cookie_file_user  = ask("User cookie file",  ctx.cookie_file_user)
            ctx.switch(ctx.active)
        elif ch == "0":
            return

# ---------- Main ----------

def main():
    while True:
        divider("Vexo Store – Terminal Tester")
        print(f"Active: {ctx.active}  |  Base: {ctx.base_url}")
        print("1) Auth")
        print("2) Admin: Brands")
        print("3) Admin: Categories")
        print("4) Admin: Products / Options / Variants / Stock")
        print("5) Admin: Coupons")
        print("6) Admin: Orders & Stats")
        print("7) Catalog / Cart / Checkout")
        print("8) Account (customer)")
        print("9) Demo: Admin seed")
        print("a) Demo: Storefront flow")
        print("s) Settings")
        print("0) Exit")
        ch = input("> ").strip().lower()
        if ch == "1": menu_auth()
        elif ch == "2": admin_brands()
        elif ch == "3": admin_categories()
        elif ch == "4": admin_products()
        elif ch == "5": admin_coupons()
        elif ch == "6": admin_orders_stats()
        elif ch == "7": catalog_cart()
        elif ch == "8": account_menu()
        elif ch == "9": demo_admin()
        elif ch == "a": demo_storefront()
        elif ch == "s": settings_menu()
        elif ch == "0":
            print("bye!")
            return

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n^C")
