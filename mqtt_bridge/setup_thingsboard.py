"""
ThingsBoard Device + Dashboard Setup Script
Creates devices (PLC_Gateway, MES_Monitor, ERP_Monitor),
patches dashboard JSONs with live device IDs, and imports them.

Usage:
    python setup_thingsboard.py

You will be prompted for your ThingsBoard Cloud email and password.
"""

import json
import os
import urllib.request
import urllib.error
import getpass

TB_HOST = "https://thingsboard.cloud"

DEVICES = [
    {
        "name": "PLC_Gateway",
        "type": "PLC",
        "description": "CODESYS PLC I/O signals — create/unload piece signals and dock materials",
    },
    {
        "name": "MES_Monitor",
        "type": "MES",
        "description": "Machine stats, tool stats, and unloading dock output from PostgreSQL",
    },
    {
        "name": "ERP_Monitor",
        "type": "ERP",
        "description": "Order KPIs, simulation day, and production schedule from PostgreSQL",
    },
]

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

DASHBOARDS = [
    {
        "path": os.path.join(SCRIPT_DIR, "dashboards", "thingsboard_mes_dashboard.json"),
        "title": "IIND MES Dashboard",
        "alias_to_device": {
            "MES_Monitor": "MES_Monitor",
        },
    },
    {
        "path": os.path.join(SCRIPT_DIR, "dashboards", "erp.json"),
        "title": "ERP",
        "alias_to_device": {
            "ERP System": "ERP_Monitor",
        },
    },
]


def tb_request(path, *, method="GET", body=None, token=None, parse_response=True):
    url = TB_HOST + path
    data = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if token:
        headers["X-Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read().decode()
            if not parse_response or not raw:
                return None
            return json.loads(raw)
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        raise RuntimeError(f"HTTP {e.code} {e.reason}: {body}") from e


def login(email, password):
    resp = tb_request(
        "/api/auth/login",
        method="POST",
        body={"username": email, "password": password},
    )
    return resp["token"]


def create_device(token, name, device_type, description):
    body = {
        "name": name,
        "type": device_type,
        "additionalInfo": {"description": description},
    }
    return tb_request("/api/device", method="POST", body=body, token=token)


def get_credentials(token, device_id):
    resp = tb_request(f"/api/device/{device_id}/credentials", token=token)
    return resp.get("credentialsId", "<unknown>")


def get_existing_devices(token):
    resp = tb_request("/api/tenant/devices?pageSize=50&page=0", token=token)
    return {d["name"]: d["id"]["id"] for d in resp.get("data", [])}


def get_existing_dashboards(token):
    resp = tb_request("/api/tenant/dashboards?pageSize=50&page=0", token=token)
    return {d["title"]: d["id"]["id"] for d in resp.get("data", [])}


def delete_dashboard(token, dashboard_id):
    tb_request(f"/api/dashboard/{dashboard_id}", method="DELETE", token=token, parse_response=False)


def import_dashboard(token, filepath, device_id_map, alias_to_device):
    with open(filepath, "r", encoding="utf-8") as f:
        dashboard = json.load(f)

    aliases = dashboard.get("configuration", {}).get("entityAliases", {})
    for alias_id, alias_obj in aliases.items():
        alias_name = alias_obj.get("alias", "")
        device_name = alias_to_device.get(alias_name)
        if device_name and device_name in device_id_map:
            old_id = alias_obj.get("filter", {}).get("singleEntity", {}).get("id")
            new_id = device_id_map[device_name]
            if old_id and old_id != new_id:
                alias_obj["filter"]["singleEntity"]["id"] = new_id
                print(f"         Patched alias '{alias_name}': {old_id[:8]}... -> {new_id[:8]}...")

    return tb_request("/api/dashboard", method="POST", body=dashboard, token=token)


def main():
    print("=" * 55)
    print("  ThingsBoard Setup — IIND Factory Floor")
    print("=" * 55)
    print(f"\nConnecting to: {TB_HOST}\n")

    email = input("ThingsBoard email: ").strip()
    password = getpass.getpass("ThingsBoard password: ")

    print("\nLogging in...")
    try:
        token = login(email, password)
    except RuntimeError as e:
        print(f"\nLogin failed: {e}")
        return

    print("Login successful.\n")

    # ── 1. Devices ──────────────────────────────────────────────
    existing = get_existing_devices(token)

    results = []
    for device in DEVICES:
        name = device["name"]
        if name in existing:
            print(f"[SKIP]   {name} already exists — fetching token...")
            device_id = existing[name]
        else:
            print(f"[CREATE] {name}...")
            try:
                created = create_device(
                    token, name, device["type"], device["description"]
                )
                device_id = created["id"]["id"]
            except RuntimeError as e:
                print(f"         Failed: {e}")
                results.append({"name": name, "token": "ERROR"})
                continue

        access_token = get_credentials(token, device_id)
        results.append({"name": name, "id": device_id, "token": access_token})
        print(f"         Device ID    : {device_id}")
        print(f"         Access Token : {access_token}\n")

    print("=" * 55)
    print("  Device Tokens")
    print("=" * 55)
    for r in results:
        print(f"\n  {r['name']}")
        print(f"    Token: {r.get('token', 'ERROR')}")

    # Write tokens to file
    out_path = os.path.join(SCRIPT_DIR, "thingsboard_tokens.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nTokens saved to {out_path}")
    print("(Do not commit this file)\n")

    # Build device name -> new device ID map
    name_to_id = {r["name"]: r["id"] for r in results if r.get("id")}

    # ── 2. Dashboards ───────────────────────────────────────────
    print("=" * 55)
    print("  Dashboard Import")
    print("=" * 55)

    existing_dashboards = get_existing_dashboards(token)
    print()

    for dash_cfg in DASHBOARDS:
        title = dash_cfg["title"]
        filepath = dash_cfg["path"]

        if not os.path.exists(filepath):
            print(f"[SKIP]   {title} — file not found: {filepath}")
            continue

        # Check if importable
        missing = [dn for dn in dash_cfg["alias_to_device"].values()
                   if dn not in name_to_id]
        if missing:
            print(f"[SKIP]   {title} — missing device(s): {missing}")
            continue

        # Delete existing dashboard with same title (replace)
        if title in existing_dashboards:
            old_id = existing_dashboards[title]
            print(f"[DELETE] {title} (old ID: {old_id[:8]}...)...")
            try:
                delete_dashboard(token, old_id)
                print(f"         Done.")
            except RuntimeError as e:
                print(f"         Delete failed: {e}")
                continue

        # Import with patched device IDs
        print(f"[IMPORT] {title}...")
        try:
            result = import_dashboard(
                token, filepath, name_to_id, dash_cfg["alias_to_device"]
            )
            new_id = result.get("id", {}).get("id", "<unknown>")
            print(f"         Dashboard ID : {new_id}")
            print(f"         OK\n")
        except RuntimeError as e:
            print(f"         Failed: {e}\n")

    print("=" * 55)
    print("  Done!")
    print("=" * 55)


if __name__ == "__main__":
    main()
