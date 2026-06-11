import requests
from requests.auth import HTTPBasicAuth
import json

# ======================
# CONFIG
# ======================
INSTANCE = "https://dev196606.service-now.com"
USERNAME = "admin"
PASSWORD = "z9-W6YsvxIS^"
OUTPUT_FILE = "servicenow_users.json"

# ======================
# SAFE API CALL
# ======================
def safe_get(url, params=None):
    response = requests.get(
        url,
        auth=HTTPBasicAuth(USERNAME, PASSWORD),
        headers={"Accept": "application/json"},
        params=params
    )
    print("\nURL:", response.url)
    print("STATUS:", response.status_code)
    try:
        data = response.json()
    except Exception:
        print("RAW RESPONSE:", response.text)
        return None
    if "result" not in data:
        print("ERROR RESPONSE:", data)
        return None
    return data["result"]

# ======================
# GET USERS
# ======================
def get_users():
    url = f"{INSTANCE}/api/now/table/sys_user"
    params = {
        "active": "true",
        "sysparm_fields": "sys_id,name,user_name,email,department,u_skillset",
        "sysparm_limit": "10"
    }
    return safe_get(url, params)

# ======================
# GET ROLES
# ======================
def get_roles(user_id):
    url = f"{INSTANCE}/api/now/table/sys_user_has_role"
    params = {
        "sysparm_query": f"user={user_id}",
        "sysparm_fields": "role",
        "sysparm_limit": "100"
    }
    roles = safe_get(url, params)
    if not roles:
        return []
    return [r.get("role") for r in roles if r.get("role")]

# ======================
# BUILD FINAL PROFILE
# ======================
def build_user_profile():
    users = get_users()
    if not users:
        print("No users fetched. Check authentication or permissions.")
        return []

    final_data = []
    for u in users:
        user_id = u.get("sys_id")
        final_data.append({
            "user_id": user_id,
            "name": u.get("name"),
            "username": u.get("user_name"),
            "email": u.get("email"),
            "department": (
                u.get("department", {}).get("display_value")
                if isinstance(u.get("department"), dict)
                else u.get("department")
            ),
            "roles": get_roles(user_id),
            "skillset": u.get("u_skillset", "Not Available")
        })
    return final_data

# ======================
# RUN
# ======================
if __name__ == "__main__":
    result = build_user_profile()

    if result:
        # Save to JSON file
        with open(OUTPUT_FILE, "w") as f:
            json.dump(result, f, indent=2)
        print(f"\n✅ Done! {len(result)} users saved to '{OUTPUT_FILE}'")

        # Also print to console
        print("\n🔥 FINAL OUTPUT:")
        print(json.dumps(result, indent=2))
    else:
        print("❌ No data to save.")