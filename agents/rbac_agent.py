# ============================================================
#   agents/rbac_agent.py — Step 6: Azure RBAC Role Assignment
#   Creates custom Learner + Contributor roles
#   Assigns Learner role to all eligible trainees
# ============================================================

import os
import uuid
import requests
from colorama import Fore, Style
from dotenv import load_dotenv

load_dotenv()

TENANT_ID       = os.getenv("TENANT_ID")
CLIENT_ID       = os.getenv("CLIENT_ID")
CLIENT_SECRET   = os.getenv("CLIENT_SECRET")
SUBSCRIPTION_ID = os.getenv("AZURE_SUBSCRIPTION_ID")
RESOURCE_GROUP  = os.getenv("AZURE_RESOURCE_GROUP", "onboarding-rg")

MGMT_BASE       = "https://management.azure.com"
GRAPH_BASE      = "https://graph.microsoft.com/v1.0"

# ── Scope for role definitions and assignments ────────────────
SUBSCRIPTION_SCOPE = f"/subscriptions/{SUBSCRIPTION_ID}"
RG_SCOPE           = f"/subscriptions/{SUBSCRIPTION_ID}/resourceGroups/{RESOURCE_GROUP}"


# ── Get Tokens ────────────────────────────────────────────────
def get_management_token() -> str:
    """Token for Azure Resource Management (RBAC)."""
    url  = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
    data = {
        "grant_type"   : "client_credentials",
        "client_id"    : CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope"        : "https://management.azure.com/.default",
    }
    r = requests.post(url, data=data)
    r.raise_for_status()
    print(f"{Fore.GREEN}✔ Azure Management token acquired.{Style.RESET_ALL}")
    return r.json()["access_token"]


def get_graph_token() -> str:
    """Token for Microsoft Graph (to fetch user object IDs)."""
    url  = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
    data = {
        "grant_type"   : "client_credentials",
        "client_id"    : CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope"        : "https://graph.microsoft.com/.default",
    }
    r = requests.post(url, data=data)
    r.raise_for_status()
    return r.json()["access_token"]


# ── Custom Role Definitions ───────────────────────────────────

LEARNER_ROLE = {
    "properties": {
        "roleName"   : "Learner",
        "description": "Read-only access to training course resources. Assigned to onboarding trainees.",
        "assignableScopes": [SUBSCRIPTION_SCOPE],
        "permissions": [
            {
                "actions": [
                    "Microsoft.Resources/subscriptions/resourceGroups/read",
                    "Microsoft.Storage/storageAccounts/read",
                    "Microsoft.Storage/storageAccounts/blobServices/containers/read",
                    "Microsoft.Storage/storageAccounts/blobServices/read",
                ],
                "notActions"    : [],
                "dataActions"   : [
                    "Microsoft.Storage/storageAccounts/blobServices/containers/blobs/read",
                ],
                "notDataActions": [],
            }
        ],
    }
}

CONTRIBUTOR_ROLE = {
    "properties": {
        "roleName"   : "CourseContributor",
        "description": "Read and write access to company resources. Assigned after training completion.",
        "assignableScopes": [SUBSCRIPTION_SCOPE],
        "permissions": [
            {
                "actions": [
                    "Microsoft.Resources/subscriptions/resourceGroups/read",
                    "Microsoft.Storage/storageAccounts/read",
                    "Microsoft.Storage/storageAccounts/blobServices/containers/read",
                    "Microsoft.Storage/storageAccounts/blobServices/read",
                    "Microsoft.Storage/storageAccounts/blobServices/containers/write",
                    "Microsoft.Storage/storageAccounts/blobServices/write",
                ],
                "notActions"    : [],
                "dataActions"   : [
                    "Microsoft.Storage/storageAccounts/blobServices/containers/blobs/read",
                    "Microsoft.Storage/storageAccounts/blobServices/containers/blobs/write",
                ],
                "notDataActions": [],
            }
        ],
    }
}


def get_existing_role_id(token: str, role_name: str) -> str | None:
    """
    Checks if a custom role already exists by name.
    Returns role definition ID if found, else None.
    """
    url     = f"{MGMT_BASE}/subscriptions/{SUBSCRIPTION_ID}/providers/Microsoft.Authorization/roleDefinitions"
    params  = {
        "api-version": "2022-04-01",
        "$filter"    : "type eq 'CustomRole'",   # fetch ALL custom roles
    }
    headers = {"Authorization": f"Bearer {token}"}
    r       = requests.get(url, headers=headers, params=params)

    if r.status_code == 200:
        for role in r.json().get("value", []):
            if role["properties"]["roleName"] == role_name:
                print(f"  {Fore.YELLOW}⚠ Role '{role_name}' already exists (ID: {role['name']}). Skipping creation.{Style.RESET_ALL}")
                return role["name"]
    return None


def create_or_get_custom_role(token: str, role_payload: dict) -> str | None:
    """
    Creates a custom role if it doesn't exist yet.
    Returns the role definition ID (GUID).
    """
    role_name = role_payload["properties"]["roleName"]
    headers   = {
        "Authorization": f"Bearer {token}",
        "Content-Type" : "application/json",
    }

    # Check if already exists
    existing_id = get_existing_role_id(token, role_name)
    if existing_id:
        print(f"  {Fore.YELLOW}⚠ Role '{role_name}' already exists (ID: {existing_id}). Skipping creation.{Style.RESET_ALL}")
        return existing_id

    # Create new role with a fresh GUID
    role_guid = str(uuid.uuid4())
    url       = (
        f"{MGMT_BASE}/subscriptions/{SUBSCRIPTION_ID}"
        f"/providers/Microsoft.Authorization/roleDefinitions/{role_guid}"
        f"?api-version=2022-04-01"
    )

    r = requests.put(url, headers=headers, json=role_payload)

    if r.status_code in [200, 201]:
        created_id = r.json()["name"]
        print(f"  {Fore.GREEN}✔ Created custom role: '{role_name}' (ID: {created_id}){Style.RESET_ALL}")
        return created_id
    else:
        print(f"  {Fore.RED}✘ Failed to create role '{role_name}': {r.status_code} — {r.text}{Style.RESET_ALL}")
        return None


def get_user_object_id(graph_token: str, upn: str) -> str | None:
    """
    Fetches the Azure AD Object ID of a user by their UPN.
    """
    headers  = {"Authorization": f"Bearer {graph_token}"}
    url      = f"{GRAPH_BASE}/users/{upn}?$select=id,displayName"
    r        = requests.get(url, headers=headers)

    if r.status_code == 200:
        return r.json().get("id")
    print(f"  {Fore.RED}✘ Could not fetch Object ID for {upn}: {r.status_code}{Style.RESET_ALL}")
    return None


def check_assignment_exists(mgmt_token: str, scope: str, user_object_id: str, role_def_id: str) -> bool:
    """
    Checks if a role assignment already exists for this user + role.
    """
    url     = f"{MGMT_BASE}{scope}/providers/Microsoft.Authorization/roleAssignments"
    params  = {
        "api-version": "2022-04-01",
        "$filter"    : f"principalId eq '{user_object_id}'",
    }
    headers = {"Authorization": f"Bearer {mgmt_token}"}
    r       = requests.get(url, headers=headers, params=params)

    if r.status_code == 200:
        assignments = r.json().get("value", [])
        for a in assignments:
            if role_def_id in a["properties"].get("roleDefinitionId", ""):
                return True
    return False


def assign_role_to_user(
    mgmt_token    : str,
    graph_token   : str,
    upn           : str,
    role_def_id   : str,
    role_name     : str,
    scope         : str,
) -> dict:
    """
    Assigns a role to a user at the given scope.

    Args:
        mgmt_token  : Azure Management token
        graph_token : Microsoft Graph token
        upn         : User Principal Name
        role_def_id : Role definition GUID
        role_name   : Human readable role name (for logging)
        scope       : Azure resource scope

    Returns:
        dict with assignment status
    """
    # Get user's Object ID from Azure AD
    object_id = get_user_object_id(graph_token, upn)
    if not object_id:
        return {"upn": upn, "status": "FAILED", "reason": "User not found in Azure AD"}

    # Check if already assigned
    if check_assignment_exists(mgmt_token, scope, object_id, role_def_id):
        print(f"  {Fore.YELLOW}⚠ Role '{role_name}' already assigned to {upn}. Skipping.{Style.RESET_ALL}")
        return {"upn": upn, "status": "ALREADY_ASSIGNED"}

    # Create assignment
    assignment_guid = str(uuid.uuid4())
    url             = (
        f"{MGMT_BASE}{scope}"
        f"/providers/Microsoft.Authorization/roleAssignments/{assignment_guid}"
        f"?api-version=2022-04-01"
    )
    headers = {
        "Authorization": f"Bearer {mgmt_token}",
        "Content-Type" : "application/json",
    }
    payload = {
        "properties": {
            "roleDefinitionId": f"{SUBSCRIPTION_SCOPE}/providers/Microsoft.Authorization/roleDefinitions/{role_def_id}",
            "principalId"     : object_id,
            "principalType"   : "User",
        }
    }

    r = requests.put(url, headers=headers, json=payload)

    if r.status_code in [200, 201]:
        print(f"  {Fore.GREEN}✔ Assigned '{role_name}' → {upn}{Style.RESET_ALL}")
        return {
            "upn"              : upn,
            "status"           : "ASSIGNED",
            "assignment_id"    : assignment_guid,
            "role_name"        : role_name,
        }
    else:
        error = r.text
        print(f"  {Fore.RED}✘ Failed to assign '{role_name}' to {upn}: {r.status_code} — {error}{Style.RESET_ALL}")
        return {"upn": upn, "status": "FAILED", "reason": error}


# ── Main Function ─────────────────────────────────────────────

def assign_learner_roles(ad_results: list) -> list:
    """
    Main function for Step 6:
    1. Creates custom Learner and CourseContributor roles
    2. Assigns Learner role to all provisioned trainees

    Args:
        ad_results: list of Azure AD provisioning results from Step 4

    Returns:
        list of RBAC assignment results
    """
    print(f"\n{Fore.CYAN}{'='*60}")
    print(f"  STEP 6 — RBAC Role Assignment")
    print(f"{'='*60}{Style.RESET_ALL}")

    if not ad_results:
        print(f"{Fore.YELLOW}  ⚠ No AD results — skipping RBAC assignment.{Style.RESET_ALL}")
        return []

    mgmt_token  = get_management_token()
    graph_token = get_graph_token()

    # ── Create custom roles ───────────────────────────────────
    print(f"\n  {Fore.CYAN}📋 Setting up Custom Roles...{Style.RESET_ALL}")
    learner_role_id     = create_or_get_custom_role(mgmt_token, LEARNER_ROLE)
    contributor_role_id = create_or_get_custom_role(mgmt_token, CONTRIBUTOR_ROLE)

    if not learner_role_id:
        print(f"{Fore.RED}✘ Could not create Learner role. Aborting RBAC step.{Style.RESET_ALL}")
        return []

    print(f"\n  {Fore.CYAN}👥 Assigning Learner Role to Trainees...{Style.RESET_ALL}")

    rbac_results = []
    for ad_user in ad_results:
        # Only assign to successfully provisioned users
        if ad_user.get("ad_status") not in ["CREATED", "ALREADY_EXISTS"]:
            continue

        upn  = ad_user.get("upn")
        name = ad_user.get("candidate_name")

        if not upn:
            print(f"  {Fore.RED}✘ No UPN for {name} — skipping.{Style.RESET_ALL}")
            continue

        print(f"\n  👤 Processing: {name} ({upn})")

        result = assign_role_to_user(
            mgmt_token  = mgmt_token,
            graph_token = graph_token,
            upn         = upn,
            role_def_id = learner_role_id,
            role_name   = "Learner",
            scope       = RG_SCOPE,
        )

        rbac_results.append({
            "candidate_id"  : ad_user.get("candidate_id"),
            "candidate_name": name,
            "upn"           : upn,
            "role_assigned" : "Learner",
            "rbac_status"   : result.get("status"),
            "assignment_id" : result.get("assignment_id"),
        })

    # ── Summary ───────────────────────────────────────────────
    assigned = sum(1 for r in rbac_results if r["rbac_status"] == "ASSIGNED")
    existing = sum(1 for r in rbac_results if r["rbac_status"] == "ALREADY_ASSIGNED")
    failed   = sum(1 for r in rbac_results if r["rbac_status"] == "FAILED")

    print(f"\n  {Fore.GREEN}✔ Assigned  : {assigned}{Style.RESET_ALL}")
    print(f"  {Fore.YELLOW}⚠ Existing  : {existing}{Style.RESET_ALL}")
    print(f"  {Fore.RED}✘ Failed    : {failed}{Style.RESET_ALL}")

    return rbac_results