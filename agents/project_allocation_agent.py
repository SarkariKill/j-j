# import datetime
# from colorama import Fore, Style

# from cosmos_client import update_candidate_status
# from agents.removal_agent import (
#     get_graph_token,
#     get_mgmt_token,
#     disable_azure_ad_user,
#     revoke_rbac_roles,
#     send_removal_email
# )


# def build_project_termination_email(candidate: dict):
#     name = candidate.get("name", "Candidate")
#     allocation = candidate.get("project_allocation", {})

#     project_name = allocation.get("project_name", "Current Project")
#     end_date = allocation.get("project_end_date", "Project End Date")

#     subject = "Project Allocation Ended - Access Termination Notice"

#     html_body = f"""
#     <div style="font-family: Arial, sans-serif; max-width: 650px; margin: auto;">
#         <h2 style="color:#c62828;">Access Termination Notice</h2>

#         <p>Dear <strong>{name}</strong>,</p>

#         <p>Your allocation to project <strong>{project_name}</strong> ended on 
#         <strong>{end_date}</strong>.</p>

#         <p>As there is no future project allocation assigned to you, your company access has been terminated.</p>

#         <h3>Removed Access:</h3>
#         <ul>
#             <li>Azure AD account disabled</li>
#             <li>RBAC roles revoked</li>
#             <li>Company project access removed</li>
#         </ul>

#         <p>If you think this is a mistake, please contact your supervisor or HR.</p>

#         <p>Regards,<br><strong>IAM Automation Team</strong></p>
#     </div>
#     """

#     return subject, html_body


# def fetch_expired_users_without_future_allocation(container):
#     today = datetime.date.today().isoformat()

#     query = """
#     SELECT * FROM c
#     WHERE IS_DEFINED(c.project_allocation)
#     AND c.project_allocation.project_end_date <= @today
#     AND c.project_allocation.future_allocation = false
#     AND c.status != 'TERMINATED'
#     AND c.status != 'REMOVED'
#     """

#     params = [
#         {"name": "@today", "value": today}
#     ]

#     return list(container.query_items(
#         query=query,
#         parameters=params,
#         enable_cross_partition_query=True
#     ))


# def process_project_expiry_termination(container):
#     print(f"\n{Fore.CYAN}{'='*60}")
#     print(" STEP 11 — Project Allocation Expiry Check")
#     print(f"{'='*60}{Style.RESET_ALL}")

#     expired_users = fetch_expired_users_without_future_allocation(container)

#     if not expired_users:
#         print(f"{Fore.YELLOW}No expired users without future allocation found.{Style.RESET_ALL}")
#         return []

#     graph_token = get_graph_token()
#     mgmt_token = get_mgmt_token()

#     results = []

#     for user in expired_users:
#         cid = user["id"]
#         name = user.get("name", "Unknown")
#         email = user.get("email", "")
#         upn = user.get("upn", "")

#         print(f"\nProcessing project expiry termination: {name}")

#         ad_disabled = False
#         rbac_revoked = False
#         mail_sent = False

#         if upn:
#             ad_disabled = disable_azure_ad_user(graph_token, upn)
#             rbac_revoked = revoke_rbac_roles(mgmt_token, graph_token, upn)
#         else:
#             print(f"{Fore.YELLOW}No UPN found, skipping Azure AD/RBAC removal.{Style.RESET_ALL}")

#         if email:
#             subject, html_body = build_project_termination_email(user)
#             mail_sent = send_removal_email(email, subject, html_body)

#             if mail_sent:
#                 print(f"{Fore.GREEN}Termination mail sent to {email}{Style.RESET_ALL}")

#         update_candidate_status(
#             container=container,
#             candidate_id=cid,
#             new_status="TERMINATED",
#             extra_fields={
#                 "termination_reason": "Project ended and no future allocation found",
#                 "ad_disabled": ad_disabled,
#                 "rbac_revoked": rbac_revoked,
#                 "termination_mail_sent": mail_sent,
#                 "terminated_at": datetime.datetime.utcnow().isoformat() + "Z"
#             }
#         )

#         results.append({
#             "candidate_id": cid,
#             "name": name,
#             "email": email,
#             "ad_disabled": ad_disabled,
#             "rbac_revoked": rbac_revoked,
#             "mail_sent": mail_sent
#         })

#     return results