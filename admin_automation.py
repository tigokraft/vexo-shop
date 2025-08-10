#!/usr/bin/env python3
"""
Admin API automation for your Next.js + Prisma store.

Requirements:
  pip install requests

Usage examples:
  # Run the full demo flow against localhost using default admin creds
  python admin_automation.py demo

  # Point to a different base URL
  python admin_automation.py --base-url http://192.168.68.150:3000 demo

  # Explicit login, persist cookie, and list brands
  python admin_automation.py --cookie-file session.cookies login --email admin@local.test --password admin123!
  python admin_automation.py --cookie-file session.cookies brands list

Subcommands:
  login, me
  brands  (list | create | update | delete)
  categories  (list | create | update | delete)
  demo   (end-to-end sample: login -> create/update/delete brand & categories)
"""

import argparse
import json
import os
import sys
from typing import Optional, Dict, Any
import requests
import pickle

DEFAULT_BASE_URL = os.environ.get("STORE_BASE_URL", "http://localhost:3000")
DEFAULT_ADMIN_EMAIL = os.environ.get("STORE_ADMIN_EMAIL", "admin@local.test")
DEFAULT_ADMIN_PASSWORD = os.environ.get("STORE_ADMIN_PASSWORD", "admin123!")


class ApiError(Exception):
    pass


class ApiClient:
    def __init__(self, base_url: str, cookie_file: Optional[str] = None, verbose: bool = True):
        self.base_url = base_url.rstrip('/')
        self.sess = requests.Session()
        self.cookie_file = cookie_file
        self.verbose = verbose
        if cookie_file and os.path.exists(cookie_file):
            try:
                with open(cookie_file, 'rb') as f:
                    self.sess.cookies.update(pickle.load(f))
                if self.verbose:
                    print(f"[cookies] Loaded cookie jar from {cookie_file}")
            except Exception as e:
                if self.verbose:
                    print(f"[cookies] Failed to load cookie jar: {e}")

    def save_cookies(self):
        if not self.cookie_file:
            return
        try:
            with open(self.cookie_file, 'wb') as f:
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
        self.save_cookies()
        return data

    # ---- Auth ----
    def login(self, email: str, password: str) -> Any:
        return self.request("POST", "/api/auth/login", json_body={"email": email, "password": password})

    def me(self) -> Any:
        return self.request("GET", "/api/auth/me")

    # ---- Brands ----
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

    # ---- Helpers / finders ----
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

    # ---- Categories ----
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


def pretty(obj):
    print(json.dumps(obj, indent=2, ensure_ascii=False))


def do_login(args):
    client = ApiClient(args.base_url, args.cookie_file, verbose=not args.quiet)
    res = client.login(args.email, args.password)
    pretty(res)


def do_me(args):
    client = ApiClient(args.base_url, args.cookie_file, verbose=not args.quiet)
    res = client.me()
    pretty(res)


def do_brands(args):
    client = ApiClient(args.base_url, args.cookie_file, verbose=not args.quiet)
    if args.action == "list":
        res = client.list_brands(page=args.page, page_size=args.page_size, q=args.q or "")
        pretty(res)
    elif args.action == "create":
        payload = {"name": args.name}
        if args.slug:
            payload["slug"] = args.slug
        if args.description:
            payload["description"] = args.description
        if args.website:
            payload["website"] = args.website
        if args.logo_url:
            payload["logoUrl"] = args.logo_url
        res = client.create_brand(**payload)
        pretty(res)
    elif args.action == "update":
        if not args.id:
            raise SystemExit("--id is required for update")
        payload = {}
        if args.name:
            payload["name"] = args.name
        if args.slug:
            payload["slug"] = args.slug
        if args.description is not None:
            payload["description"] = args.description
        if args.website is not None:
            payload["website"] = args.website
        if args.logo_url is not None:
            payload["logoUrl"] = args.logo_url
        res = client.update_brand(args.id, **payload)
        pretty(res)
    elif args.action == "delete":
        if not args.id:
            raise SystemExit("--id is required for delete")
        res = client.delete_brand(args.id)
        pretty(res)


def do_categories(args):
    client = ApiClient(args.base_url, args.cookie_file, verbose=not args.quiet)
    if args.action == "list":
        parent = args.parent_id
        res = client.list_categories(page=args.page, page_size=args.page_size, q=args.q or "", parent_id=parent)
        pretty(res)
    elif args.action == "create":
        payload = {"name": args.name}
        if args.slug:
            payload["slug"] = args.slug
        if args.description:
            payload["description"] = args.description
        if args.parent_id:
            payload["parentId"] = args.parent_id
        res = client.create_category(**payload)
        pretty(res)
    elif args.action == "update":
        if not args.id:
            raise SystemExit("--id is required for update")
        payload = {}
        if args.name:
            payload["name"] = args.name
        if args.slug:
            payload["slug"] = args.slug
        if args.description is not None:
            payload["description"] = args.description
        if args.parent_id is not None:
            payload["parentId"] = args.parent_id
        res = client.update_category(args.id, **payload)
        pretty(res)
    elif args.action == "delete":
        if not args.id:
            raise SystemExit("--id is required for delete")
        res = client.delete_category(args.id)
        pretty(res)


def do_demo(args):
    client = ApiClient(args.base_url, args.cookie_file, verbose=not args.quiet)
    print(f"[demo] Logging in as {args.email}")
    client.login(args.email, args.password)
    me = client.me()
    print("[demo] Authenticated user:")
    pretty(me)

    # Brand flow
    print("\n[demo] Creating brand 'Orbit'")
    brand = client.ensure_brand(name="Orbit", slug="orbit", description="Performance basics")
    pretty(brand)
    brand_id = brand["id"]

    print("\n[demo] Updating brand slug + website")
    brand = client.update_brand(brand_id, slug="orbit", website="https://orbit.example")
    pretty(brand)

    print("\n[demo] Listing brands page 1")
    pretty(client.list_brands(page=1, page_size=10))

    print("\n[demo] Deleting brand")
    pretty(client.delete_brand(brand_id))

    # Category flow
    print("\n[demo] Creating category 'Women' (root)")
    cat_root = client.ensure_category(name="Women", slug="women")
    pretty(cat_root)
    root_id = cat_root["id"]

    print("\n[demo] Creating subcategory 'Tops' under 'Women'")
    cat_sub = client.ensure_category(name="Tops", slug="tops", parentId=root_id)
    pretty(cat_sub)
    sub_id = cat_sub["id"]

    print("\n[demo] Updating 'Women' description")
    pretty(client.update_category(root_id, description="All women categories"))

    print("\n[demo] Listing root categories")
    pretty(client.list_categories(parent_id="root", page=1, page_size=10))

    print("\n[demo] Delete subcategory then root")
    pretty(client.delete_category(sub_id))
    pretty(client.delete_category(root_id))


def build_parser():
    p = argparse.ArgumentParser(description="Admin API automation")
    p.add_argument("--base-url", default=DEFAULT_BASE_URL, help=f"API base URL (default: {DEFAULT_BASE_URL})")
    p.add_argument("--cookie-file", default=None, help="Path to persist cookies between runs")
    p.add_argument("--quiet", action="store_true", help="Less verbose output")

    sub = p.add_subparsers(dest="cmd", required=True)

    # login
    pl = sub.add_parser("login", help="Login and store session cookie")
    pl.add_argument("--email", default=DEFAULT_ADMIN_EMAIL)
    pl.add_argument("--password", default=DEFAULT_ADMIN_PASSWORD)
    pl.set_defaults(func=do_login)

    # me
    pm = sub.add_parser("me", help="Show current user")
    pm.set_defaults(func=do_me)

    # brands
    pb = sub.add_parser("brands", help="Brand operations")
    pb_sub = pb.add_subparsers(dest="action", required=True)

    pbl = pb_sub.add_parser("list", help="List brands")
    pbl.add_argument("--q", default="")
    pbl.add_argument("--page", type=int, default=1)
    pbl.add_argument("--page-size", type=int, default=20)
    pbl.set_defaults(func=do_brands)

    pbc = pb_sub.add_parser("create", help="Create a brand")
    pbc.add_argument("--name", required=True)
    pbc.add_argument("--slug")
    pbc.add_argument("--description")
    pbc.add_argument("--website")
    pbc.add_argument("--logo-url")
    pbc.set_defaults(func=do_brands)

    pbu = pb_sub.add_parser("update", help="Update a brand")
    pbu.add_argument("--id", required=True)
    pbu.add_argument("--name")
    pbu.add_argument("--slug")
    pbu.add_argument("--description", nargs="?", const=None)
    pbu.add_argument("--website", nargs="?", const=None)
    pbu.add_argument("--logo-url", nargs="?", const=None)
    pbu.set_defaults(func=do_brands)

    pbd = pb_sub.add_parser("delete", help="Delete a brand")
    pbd.add_argument("--id", required=True)
    pbd.set_defaults(func=do_brands)

    # categories
    pc = sub.add_parser("categories", help="Category operations")
    pc_sub = pc.add_subparsers(dest="action", required=True)

    pcl = pc_sub.add_parser("list", help="List categories")
    pcl.add_argument("--q", default="")
    pcl.add_argument("--page", type=int, default=1)
    pcl.add_argument("--page-size", type=int, default=20)
    pcl.add_argument("--parent-id", help='UUID of parent. Use "root" for top-level.', default=None)
    pcl.set_defaults(func=do_categories)

    pcc = pc_sub.add_parser("create", help="Create a category")
    pcc.add_argument("--name", required=True)
    pcc.add_argument("--slug")
    pcc.add_argument("--description")
    pcc.add_argument("--parent-id")
    pcc.set_defaults(func=do_categories)

    pcu = pc_sub.add_parser("update", help="Update a category")
    pcu.add_argument("--id", required=True)
    pcu.add_argument("--name")
    pcu.add_argument("--slug")
    pcu.add_argument("--description", nargs="?", const=None)
    pcu.add_argument("--parent-id", nargs="?", const=None)
    pcu.set_defaults(func=do_categories)

    pcd = pc_sub.add_parser("delete", help="Delete a category")
    pcd.add_argument("--id", required=True)
    pcd.set_defaults(func=do_categories)

    # demo
    pd = sub.add_parser("demo", help="Run end-to-end demo flow (login -> brand/category CRUD)")
    pd.add_argument("--email", default=DEFAULT_ADMIN_EMAIL)
    pd.add_argument("--password", default=DEFAULT_ADMIN_PASSWORD)
    pd.set_defaults(func=do_demo)

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
