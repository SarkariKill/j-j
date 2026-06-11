# ============================================================
#   agents/azure_ad_agent.py — Step 4: Azure AD Provisioning
#   Creates Trainee accounts in Azure AD for ELIGIBLE candidates
# ============================================================

import os
import token
import requests
from colorama import Fore, Style
from dotenv import load_dotenv

load_dotenv()

TENANT_ID     = os.getenv("TENANT_ID")
CLIENT_ID     = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
GRAPH_BASE    = "https://graph.microsoft.com/v1.0"


def get_access_token() -> str:
    """
    Gets Microsoft Graph API access token using client credentials flow.
    """
    url  = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
    data = {
        "grant_type"   : "client_credentials",
        "client_id"    : CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope"        : "https://graph.microsoft.com/.default",
    }
    response = requests.post(url, data=data)
    response.raise_for_status()
    token = response.json().get("access_token")
    print(f"{Fore.GREEN}✔ Microsoft Graph token acquired.{Style.RESET_ALL}")
    return token


def build_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type" : "application/json",
    }


def check_user_exists(token: str, name: str, domain: str) -> tuple:
    """Returns (object_id, upn) if exists, else (None, upn)"""
    name_parts = name.lower().replace(" ", ".")
    upn        = f"{name_parts}@{domain}"
    headers    = build_headers(token)
    url        = f"{GRAPH_BASE}/users/{upn}"
    response   = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json().get("id"), upn
    return None, upn


def create_trainee_in_ad(token: str, candidate: dict) -> dict:
    """
    Creates a Trainee user in Azure AD for an ELIGIBLE candidate.

    Args:
        token     : Graph API access token
        candidate : Cosmos DB candidate document

    Returns:
        dict with azure_ad_object_id, upn, temp_password, status
    """
    name       = candidate.get("name", "Unknown")
    email      = candidate.get("email", "")
    role       = candidate.get("applied_role", "Trainee")
    headers    = build_headers(token)

    print(f"\n{Fore.CYAN}  👤 Provisioning Azure AD account for: {name}{Style.RESET_ALL}")

    # ── Check if already exists ───────────────────────────────
    domain                = os.getenv("AD_DOMAIN")
    existing_id, upn      = check_user_exists(token, name, domain)
    if existing_id:
        print(f"  {Fore.YELLOW}⚠ User already exists in Azure AD (ID: {existing_id}). Skipping creation.{Style.RESET_ALL}")
        return {
            "azure_ad_object_id": existing_id,
            "upn"               : upn,        # ← correct UPN now
            "temp_password"     : None,
            "status"            : "ALREADY_EXISTS",
        }

    # ── Build UPN from email ──────────────────────────────────
    # UPN must use your tenant's verified domain
    # Format: firstname.lastname@yourtenant.onmicrosoft.com
    domain       = os.getenv("AD_DOMAIN")   # e.g. yourtenant.onmicrosoft.com
    name_parts   = name.lower().replace(" ", ".")
    upn          = f"{name_parts}@{domain}"
    temp_password = f"Onboard@{candidate.get('id', '001').split('_')[-1]}2026!"

    # ── User payload ──────────────────────────────────────────
    payload = {
        "accountEnabled"  : True,
        "displayName"     : name,
        "mailNickname"    : name.lower().replace(" ", "."),
        "userPrincipalName": upn,
        "mail"            : email,
        "jobTitle"        : "Trainee",
        "department"      : role,
        "passwordProfile" : {
            "forceChangePasswordNextSignIn": True,
            "password"                    : temp_password,
        },
        "usageLocation"   : "IN",   # Required for license assignment later
    }

    response = requests.post(
        f"{GRAPH_BASE}/users",
        headers=headers,
        json=payload,
    )

    if response.status_code == 201:
        user_data = response.json()
        object_id = user_data.get("id")
        print(f"  {Fore.GREEN}✔ Created: {name} | UPN: {upn} | ID: {object_id}{Style.RESET_ALL}")
        return {
            "azure_ad_object_id": object_id,
            "upn"               : upn,
            "temp_password"     : temp_password,
            "status"            : "CREATED",
        }
    else:
        error = response.json()
        print(f"  {Fore.RED}✘ Failed to create {name}: {error}{Style.RESET_ALL}")
        return {
            "azure_ad_object_id": None,
            "upn"               : upn,
            "temp_password"     : None,
            "status"            : "FAILED",
            "error"             : str(error),
        }


def provision_eligible_candidates(eligible_candidates: list) -> list:
    """
    Main function — provisions all ELIGIBLE candidates in Azure AD.

    Args:
        eligible_candidates: list of Cosmos DB candidate dicts

    Returns:
        list of provisioning results with AD details
    """
    print(f"\n{Fore.CYAN}{'='*60}")
    print(f"  STEP 4 — Azure AD Provisioning ({len(eligible_candidates)} candidates)")
    print(f"{'='*60}{Style.RESET_ALL}")

    if not eligible_candidates:
        print(f"{Fore.YELLOW}  ⚠ No eligible candidates to provision.{Style.RESET_ALL}")
        return []

    token   = get_access_token()
    results = []

    for candidate in eligible_candidates:
        result = create_trainee_in_ad(token, candidate)
        results.append({
            "candidate_id"      : candidate["id"],
            "candidate_name"    : candidate["name"],
            "email"             : candidate["email"],
            "azure_ad_object_id": result.get("azure_ad_object_id"),
            "upn"               : result.get("upn"),
            "temp_password"     : result.get("temp_password"),
            "ad_status"         : result.get("status"),
        })

    # ── Summary ───────────────────────────────────────────────
    created  = sum(1 for r in results if r["ad_status"] == "CREATED")
    existing = sum(1 for r in results if r["ad_status"] == "ALREADY_EXISTS")
    failed   = sum(1 for r in results if r["ad_status"] == "FAILED")

    print(f"\n  {Fore.GREEN}✔ Created  : {created}{Style.RESET_ALL}")
    print(f"  {Fore.YELLOW}⚠ Existing : {existing}{Style.RESET_ALL}")
    print(f"  {Fore.RED}✘ Failed   : {failed}{Style.RESET_ALL}")

    return results