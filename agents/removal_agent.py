# ============================================================
#   agents/removal_agent.py — Step 9
#   Removes FAILED trainees from Azure AD + sends removal mail
# ============================================================

import os
import smtplib
import requests
import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from colorama import Fore, Style
from dotenv import load_dotenv

load_dotenv()

TENANT_ID       = os.getenv("TENANT_ID")
CLIENT_ID       = os.getenv("CLIENT_ID")
CLIENT_SECRET   = os.getenv("CLIENT_SECRET")
GMAIL_SENDER    = os.getenv("GMAIL_SENDER")
GMAIL_PASSWORD  = os.getenv("GMAIL_APP_PASSWORD")
COMPANY_NAME    = os.getenv("COMPANY_NAME", "Johnson & Johnson")
GRAPH_BASE      = "https://graph.microsoft.com/v1.0"
MGMT_BASE       = "https://management.azure.com"
SUBSCRIPTION_ID = os.getenv("AZURE_SUBSCRIPTION_ID")
RESOURCE_GROUP  = os.getenv("AZURE_RESOURCE_GROUP", "onboarding-rg")


def get_graph_token() -> str:
    url  = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
    data = {
        "grant_type"   : "client_credentials",
        "client_id"    : CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope"        : "https://graph.microsoft.com/.default",
    }
    return requests.post(url, data=data).json()["access_token"]


def get_mgmt_token() -> str:
    url  = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
    data = {
        "grant_type"   : "client_credentials",
        "client_id"    : CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope"        : "https://management.azure.com/.default",
    }
    return requests.post(url, data=data).json()["access_token"]


def disable_azure_ad_user(graph_token: str, upn: str) -> bool:
    """
    Disables (not deletes) Azure AD user account.
    Safer than deletion — can be restored if needed.
    """
    headers = {
        "Authorization": f"Bearer {graph_token}",
        "Content-Type" : "application/json",
    }
    url = f"{GRAPH_BASE}/users/{upn}"
    r   = requests.patch(url, headers=headers, json={"accountEnabled": False})

    if r.status_code == 204:
        print(f"  {Fore.GREEN}✔ Azure AD account disabled: {upn}{Style.RESET_ALL}")
        return True
    else:
        print(f"  {Fore.RED}✘ Failed to disable {upn}: {r.status_code} — {r.text}{Style.RESET_ALL}")
        return False


def revoke_rbac_roles(mgmt_token: str, graph_token: str, upn: str) -> bool:
    """
    Revokes all RBAC role assignments for the user on the resource group.
    """
    scope   = f"/subscriptions/{SUBSCRIPTION_ID}/resourceGroups/{RESOURCE_GROUP}"
    url     = f"{MGMT_BASE}{scope}/providers/Microsoft.Authorization/roleAssignments"
    headers = {"Authorization": f"Bearer {mgmt_token}"}
    params  = {"api-version": "2022-04-01"}

    # Get user object ID first
    graph_headers = {"Authorization": f"Bearer {graph_token}"}
    user_r        = requests.get(f"{GRAPH_BASE}/users/{upn}?$select=id", headers=graph_headers)

    if user_r.status_code != 200:
        print(f"  {Fore.YELLOW}⚠ Could not fetch user ID for RBAC revocation: {upn}{Style.RESET_ALL}")
        return False

    object_id = user_r.json().get("id")

    # List all assignments for this user
    list_r      = requests.get(url, headers=headers, params={**params, "$filter": f"principalId eq '{object_id}'"})
    assignments = list_r.json().get("value", [])

    if not assignments:
        print(f"  {Fore.YELLOW}⚠ No RBAC assignments found for {upn}{Style.RESET_ALL}")
        return True

    # Delete each assignment
    for assignment in assignments:
        assignment_id = assignment["name"]
        del_url       = f"{MGMT_BASE}{scope}/providers/Microsoft.Authorization/roleAssignments/{assignment_id}"
        del_r         = requests.delete(del_url, headers=headers, params=params)

        if del_r.status_code in [200, 204]:
            print(f"  {Fore.GREEN}✔ RBAC role revoked for {upn}{Style.RESET_ALL}")
        else:
            print(f"  {Fore.YELLOW}⚠ Could not revoke role: {del_r.status_code}{Style.RESET_ALL}")

    return True


def build_removal_email(candidate: dict) -> tuple:
    """Builds removal notification email."""
    name          = candidate.get("name", "Candidate")
    role          = candidate.get("applied_role", "Trainee")
    failed_reason = candidate.get("failed_reason", "Course not completed within deadline")
    watch_pct     = candidate.get("watch_percentage", 0)
    elapsed       = candidate.get("elapsed_minutes", 0)

    subject = f"Important: Access Removal Notice — {COMPANY_NAME}"

    html_body = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: auto; border: 1px solid #e0e0e0; border-radius: 8px; overflow: hidden;">

      <div style="background-color: #c62828; padding: 30px; text-align: center;">
        <h1 style="color: white; margin: 0;">⚠ Access Removal Notice</h1>
        <p style="color: #ffcdd2; margin: 8px 0 0;">{COMPANY_NAME} — Onboarding Program</p>
      </div>

      <div style="padding: 30px; background-color: #ffffff;">
        <p style="font-size: 16px;">Dear <strong>{name}</strong>,</p>

        <p>We regret to inform you that your access to the <strong>{COMPANY_NAME}</strong>
        onboarding portal and training resources has been <strong>revoked</strong>.</p>

        <div style="background: #fff3f3; border-left: 4px solid #c62828; padding: 16px; border-radius: 4px; margin: 20px 0;">
          <h3 style="color: #c62828; margin: 0 0 10px;">📋 Reason for Removal</h3>
          <p style="margin: 0; color: #555;">{failed_reason}</p>
        </div>

        <h3 style="color: #555;">📊 Your Course Progress at Time of Removal</h3>
        <table style="width:100%; border-collapse:collapse;">
          <tr>
            <td style="padding:8px; background:#f5f5f5; font-weight:bold; width:50%;">Video Watched</td>
            <td style="padding:8px;">{watch_pct:.1f}%</td>
          </tr>
          <tr>
            <td style="padding:8px; background:#f5f5f5; font-weight:bold;">Time Elapsed</td>
            <td style="padding:8px;">{elapsed:.1f} minutes</td>
          </tr>
          <tr>
            <td style="padding:8px; background:#f5f5f5; font-weight:bold;">Required to Pass</td>
            <td style="padding:8px;">90% watch + within 60 minutes</td>
          </tr>
        </table>

        <h3 style="color: #555; margin-top: 20px;">🔒 What Has Been Removed</h3>
        <ul style="color: #444; line-height: 1.8;">
          <li>Azure AD account has been <strong>disabled</strong></li>
          <li>All portal access and RBAC roles <strong>revoked</strong></li>
          <li>Training course access <strong>removed</strong></li>
        </ul>

        <hr style="border: none; border-top: 1px solid #e0e0e0; margin: 20px 0;">

        <h3 style="color: #0078d4;">💡 What You Can Do</h3>
        <ul style="color: #444; line-height: 1.8;">
          <li>Contact HR to request <strong>re-enrollment</strong></li>
          <li>Review the course material and ensure you have adequate time</li>
          <li>Make sure you have a stable internet connection for video watching</li>
        </ul>

        <p style="margin-top: 20px;">If you believe this is an error, please contact HR immediately.</p>
        <p>Best regards,<br><strong>HR Onboarding Team</strong><br>{COMPANY_NAME}</p>
      </div>

      <div style="background-color: #f5f5f5; padding: 15px; text-align: center;">
        <p style="color: #999; font-size: 12px; margin: 0;">
          This is an automated message from {COMPANY_NAME} Onboarding System.
        </p>
      </div>
    </div>
    """
    return subject, html_body


def send_removal_email(to_email: str, subject: str, html_body: str) -> bool:
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = f"{COMPANY_NAME} HR <{GMAIL_SENDER}>"
        msg["To"]      = to_email
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_SENDER, GMAIL_PASSWORD)
            server.sendmail(GMAIL_SENDER, to_email, msg.as_string())
        return True
    except Exception as e:
        print(f"  {Fore.RED}✘ Mail error: {e}{Style.RESET_ALL}")
        return False


def process_failed_trainees(failed_candidates: list, container) -> list:
    """
    Main Step 9 function:
    1. Disable Azure AD account
    2. Revoke RBAC roles
    3. Send removal email
    4. Update Cosmos DB

    Args:
        failed_candidates : list of COURSE_FAILED candidate dicts
        container         : Cosmos DB container client

    Returns:
        list of removal results
    """
    print(f"\n{Fore.CYAN}{'='*60}")
    print(f"  STEP 9 — Removing Failed Trainees ({len(failed_candidates)})")
    print(f"{'='*60}{Style.RESET_ALL}")

    if not failed_candidates:
        print(f"  {Fore.YELLOW}⚠ No failed trainees to process.{Style.RESET_ALL}")
        return []

    graph_token = get_graph_token()
    mgmt_token  = get_mgmt_token()
    results     = []

    for candidate in failed_candidates:
        name  = candidate.get("name", "Unknown")
        cid   = candidate["id"]
        email = candidate.get("email", "")
        upn   = candidate.get("upn", "")

        print(f"\n  👤 Processing removal: {name}")

        ad_disabled    = False
        rbac_revoked   = False
        mail_sent      = False

        # ── 1. Disable Azure AD account ───────────────────────
        if upn:
            ad_disabled  = disable_azure_ad_user(graph_token, upn)
            rbac_revoked = revoke_rbac_roles(mgmt_token, graph_token, upn)
        else:
            print(f"  {Fore.YELLOW}⚠ No UPN found — skipping AD/RBAC removal{Style.RESET_ALL}")

        # ── 2. Send removal email ─────────────────────────────
        if email:
            subject, html_body = build_removal_email(candidate)
            mail_sent          = send_removal_email(email, subject, html_body)
            if mail_sent:
                print(f"  {Fore.GREEN}✔ Removal email sent → {email}{Style.RESET_ALL}")

        # ── 3. Update Cosmos DB ───────────────────────────────
        update_candidate_status(
            container    = container,
            candidate_id = cid,
            new_status   = "REMOVED",
            extra_fields = {
                "removal_reason"   : "Course not completed within deadline",
                "ad_disabled"      : ad_disabled,
                "rbac_revoked"     : rbac_revoked,
                "removal_mail_sent": mail_sent,
                "removed_at"       : datetime.datetime.utcnow().isoformat() + "Z",
            }
        )

        results.append({
            "candidate_id" : cid,
            "name"         : name,
            "email"        : email,
            "ad_disabled"  : ad_disabled,
            "rbac_revoked" : rbac_revoked,
            "mail_sent"    : mail_sent,
        })

    # ── Summary ───────────────────────────────────────────────
    print(f"\n  {Fore.RED}🗑 Removal Summary:{Style.RESET_ALL}")
    for r in results:
        print(f"     {r['name']}: AD={'✅' if r['ad_disabled'] else '❌'} | RBAC={'✅' if r['rbac_revoked'] else '❌'} | Mail={'✅' if r['mail_sent'] else '❌'}")

    return results