import datetime
import pandas as pd
from colorama import Fore, Style

from cosmos_client import update_candidate_status
from agents.removal_agent import (
    get_graph_token,
    get_mgmt_token,
    disable_azure_ad_user,
    revoke_rbac_roles,
    send_removal_email
)

EXCEL_FILE = "project_allocations.xlsx"


def build_supervisor_termination_email(user, allocation):
    user_name = user.get("name", allocation.get("name", "User"))
    user_email = user.get("email", allocation.get("email", ""))
    project_name = allocation.get("project_name", "Project")
    project_end_date = allocation.get("project_end_date", "")
    supervisor_name = allocation.get("supervisor_name", "Supervisor")

    subject = f"User Terminated After Project End Date - {user_name}"

    html_body = f"""
    <div style="font-family: Arial, sans-serif; max-width: 650px; margin: auto;">
        <h2 style="color:#c62828;">User Access Termination Notification</h2>

        <p>Dear <strong>{supervisor_name}</strong>,</p>

        <p>This is to inform you that the below user has been terminated automatically because their project end date has passed.</p>

        <table border="1" cellpadding="8" cellspacing="0" style="border-collapse: collapse;">
            <tr><td><strong>User Name</strong></td><td>{user_name}</td></tr>
            <tr><td><strong>User Email</strong></td><td>{user_email}</td></tr>
            <tr><td><strong>Project Name</strong></td><td>{project_name}</td></tr>
            <tr><td><strong>Project End Date</strong></td><td>{project_end_date}</td></tr>
        </table>

        <p>The user's Azure AD account has been disabled, RBAC access has been revoked, and the user's status has been updated in the system.</p>

        <p>Regards,<br><strong>IAM Automation Team</strong></p>
    </div>
    """

    return subject, html_body


def load_project_allocations_from_excel():
    df = pd.read_excel(EXCEL_FILE)

    required_columns = [
        "name",
        "email",
        "project_name",
        "project_end_date",
        "supervisor_name",
        "supervisor_email",
        "future_allocation"
    ]

    for col in required_columns:
        if col not in df.columns:
            raise Exception(f"Missing column in Excel: {col}")

    df["email"] = df["email"].astype(str).str.lower().str.strip()
    df["supervisor_email"] = df["supervisor_email"].astype(str).str.strip()
    df["project_end_date"] = pd.to_datetime(df["project_end_date"]).dt.date

    return df


def fetch_contributor_users(container):
    query = """
    SELECT * FROM c
    WHERE c.status = 'CONTRIBUTOR'
    OR c.status = 'PROMOTED_TO_CONTRIBUTOR'
    """

    return list(container.query_items(
        query=query,
        enable_cross_partition_query=True
    ))


def process_excel_project_expiry(container):
    print(f"\n{Fore.CYAN}{'='*60}")
    print(" DAILY AGENT — Excel Project Expiry Check")
    print(f"{'='*60}{Style.RESET_ALL}")

    today = datetime.date.today()

    allocations_df = load_project_allocations_from_excel()
    contributors = fetch_contributor_users(container)

    if not contributors:
        print(f"{Fore.YELLOW}No contributor users found.{Style.RESET_ALL}")
        return []

    graph_token = get_graph_token()
    mgmt_token = get_mgmt_token()

    results = []

    for user in contributors:
        user_email = user.get("email", "").lower().strip()
        match = allocations_df[allocations_df["email"] == user_email]

        if match.empty:
            print(f"{Fore.YELLOW}No Excel allocation found for {user_email}{Style.RESET_ALL}")
            continue

        allocation = match.iloc[0].to_dict()

        project_end_date = allocation["project_end_date"]
        future_allocation = str(allocation.get("future_allocation", "No")).lower().strip()

        has_future_allocation = future_allocation in ["yes", "true", "1"]

        if project_end_date >= today:
            print(f"{Fore.GREEN}Active project: {user.get('name')} till {project_end_date}{Style.RESET_ALL}")
            continue

        if has_future_allocation:
            print(f"{Fore.GREEN}Future allocation exists for {user.get('name')}, skipping termination.{Style.RESET_ALL}")
            continue

        print(f"{Fore.RED}Project expired. Terminating: {user.get('name')}{Style.RESET_ALL}")

        upn = user.get("upn", "")
        supervisor_email = allocation.get("supervisor_email", "")

        ad_disabled = False
        rbac_revoked = False
        supervisor_mail_sent = False

        if upn:
            ad_disabled = disable_azure_ad_user(graph_token, upn)
            rbac_revoked = revoke_rbac_roles(mgmt_token, graph_token, upn)
        else:
            print(f"{Fore.YELLOW}No UPN found for {user.get('name')}. Skipping AD/RBAC removal.{Style.RESET_ALL}")

        if supervisor_email:
            subject, html_body = build_supervisor_termination_email(user, allocation)
            supervisor_mail_sent = send_removal_email(supervisor_email, subject, html_body)

        update_candidate_status(
            container=container,
            candidate_id=user["id"],
            new_status="TERMINATED",
            extra_fields={
                "termination_reason": "Project end date passed and no future allocation found in Excel",
                "project_name": allocation.get("project_name"),
                "project_end_date": str(project_end_date),
                "supervisor_name": allocation.get("supervisor_name"),
                "supervisor_email": supervisor_email,
                "ad_disabled": ad_disabled,
                "rbac_revoked": rbac_revoked,
                "supervisor_mail_sent": supervisor_mail_sent,
                "terminated_at": datetime.datetime.utcnow().isoformat() + "Z"
            }
        )

        results.append({
            "name": user.get("name"),
            "email": user_email,
            "project_end_date": str(project_end_date),
            "supervisor_email": supervisor_email,
            "terminated": True
        })

    return results