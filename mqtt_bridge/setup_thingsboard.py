"""
ThingsBoard Device Setup Script
Creates PLC_Gateway, MES_Monitor, and ERP_Monitor devices
and prints their access tokens.

Usage:
    python setup_thingsboard.py

You will be prompted for your ThingsBoard Cloud email and password.
"""

import json
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


def tb_request(path, *, method="GET", body=None, token=None):
    url = TB_HOST + path
    data = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if token:
        headers["X-Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
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


def main():
    print("=" * 55)
    print("  ThingsBoard Device Setup — IIND Factory Floor")
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
    print("  Copy these tokens into MQTT_implementation.md")
    print("  and the CODESYS GVL_MQTT / mqtt_publisher.py")
    print("=" * 55)
    for r in results:
        print(f"\n  {r['name']}")
        print(f"    Token: {r.get('token', 'ERROR')}")

    # Write tokens to a local file for reference
    out_path = "thingsboard_tokens.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nTokens also saved to mqtt_bridge/{out_path}")
    print("(Do not commit this file — add it to .gitignore)\n")


if __name__ == "__main__":
    main()
