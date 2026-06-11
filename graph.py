# # ============================================================
# #   graph.py — LangGraph Workflow: Steps 3 + 4 + 5
# #   Step 3: IAM Skill Validation
# #   Step 4: Azure AD Provisioning
# #   Step 5: Email Notifications via MS Graph
# # ============================================================

# import datetime
# from typing import TypedDict, List, Optional
# from langgraph.graph import StateGraph, END
# from colorama import Fore, Style

# from cosmos_client import (
#     get_container,
#     fetch_pending_candidates,
#     update_candidate_status,
# )
# from agents.iam_validation_agent import run_iam_validation
# from agents.azure_ad_agent import provision_eligible_candidates
# from agents.mail_agent import send_all_notifications


# # ── LangGraph State Schema ────────────────────────────────────
# class OnboardingState(TypedDict):
#     candidates          : List[dict]
#     current_index       : int
#     validation_results  : List[dict]
#     eligible_candidates : List[dict]
#     rejected_candidates : List[dict]
#     eligible_ids        : List[str]
#     rejected_ids        : List[str]
#     ad_results          : List[dict]
#     mail_results        : dict
#     error               : Optional[str]


# # ── NODE 1: Fetch Candidates ──────────────────────────────────
# def fetch_candidates_node(state: OnboardingState) -> OnboardingState:
#     print(f"\n{Fore.CYAN}{'='*60}")
#     print(f"  NODE 1 — Fetching Pending Candidates from Cosmos DB")
#     print(f"{'='*60}{Style.RESET_ALL}")

#     try:
#         container  = get_container()
#         candidates = fetch_pending_candidates(container)

#         if not candidates:
#             print(f"{Fore.YELLOW}⚠ No PENDING_VALIDATION candidates found.{Style.RESET_ALL}")
#         else:
#             print(f"{Fore.GREEN}✔ Found {len(candidates)} pending candidate(s).{Style.RESET_ALL}")
#             for c in candidates:
#                 print(f"   → {c['name']} ({c['id']})")

#         return {
#             **state,
#             "candidates"         : candidates,
#             "current_index"      : 0,
#             "validation_results" : [],
#             "eligible_candidates": [],
#             "rejected_candidates": [],
#             "eligible_ids"       : [],
#             "rejected_ids"       : [],
#             "ad_results"         : [],
#             "mail_results"       : {},
#             "error"              : None,
#         }
#     except Exception as e:
#         err = f"Failed to fetch candidates: {str(e)}"
#         print(f"{Fore.RED}✘ {err}{Style.RESET_ALL}")
#         return {**state, "error": err, "candidates": []}


# # ── NODE 2: Validate Candidate (loops) ───────────────────────
# def validate_candidate_node(state: OnboardingState) -> OnboardingState:
#     candidates = state["candidates"]
#     idx        = state["current_index"]

#     if idx >= len(candidates):
#         return state

#     candidate = candidates[idx]
#     print(f"\n{Fore.CYAN}{'='*60}")
#     print(f"  NODE 2 — Validating Candidate {idx+1}/{len(candidates)}")
#     print(f"{'='*60}{Style.RESET_ALL}")

#     result = run_iam_validation(candidate)

#     validation_entry = {
#         "candidate_id"   : candidate["id"],
#         "candidate_name" : candidate["name"],
#         "email"          : candidate["email"],
#         "decision"       : result["decision"],
#         "match_percentage": result["match_percentage"],
#         "matched_skills" : result["matched_skills"],
#         "missing_skills" : result["missing_skills"],
#         "reasoning"      : result["reasoning"],
#     }

#     updated_results   = state["validation_results"] + [validation_entry]
#     updated_eligible  = state["eligible_ids"].copy()
#     updated_rejected  = state["rejected_ids"].copy()
#     updated_elig_docs = state["eligible_candidates"].copy()
#     updated_rej_docs  = state["rejected_candidates"].copy()

#     # Enrich candidate doc with validation results for later use
#     enriched = {
#         **candidate,
#         "matched_skills_found": result["matched_skills"],
#         "missing_skills"      : result["missing_skills"],
#         "match_percentage"    : result["match_percentage"],
#     }

#     if result["decision"] == "ELIGIBLE":
#         updated_eligible.append(candidate["id"])
#         updated_elig_docs.append(enriched)
#     else:
#         updated_rejected.append(candidate["id"])
#         updated_rej_docs.append(enriched)

#     return {
#         **state,
#         "validation_results"  : updated_results,
#         "eligible_ids"        : updated_eligible,
#         "rejected_ids"        : updated_rejected,
#         "eligible_candidates" : updated_elig_docs,
#         "rejected_candidates" : updated_rej_docs,
#         "current_index"       : idx + 1,
#     }


# # ── NODE 3: Update Cosmos DB ──────────────────────────────────
# def update_cosmos_node(state: OnboardingState) -> OnboardingState:
#     print(f"\n{Fore.CYAN}{'='*60}")
#     print(f"  NODE 3 — Updating Cosmos DB with Validation Results")
#     print(f"{'='*60}{Style.RESET_ALL}")

#     try:
#         container = get_container()
#         for result in state["validation_results"]:
#             extra_fields = {
#                 "validation_result"    : result["decision"],
#                 "match_percentage"     : result["match_percentage"],
#                 "matched_skills_found" : result["matched_skills"],
#                 "missing_skills"       : result["missing_skills"],
#                 "validation_reasoning" : result["reasoning"],
#                 "validated_at"         : datetime.datetime.utcnow().isoformat() + "Z",
#             }
#             update_candidate_status(
#                 container    = container,
#                 candidate_id = result["candidate_id"],
#                 new_status   = result["decision"],
#                 extra_fields = extra_fields,
#             )
#         return state
#     except Exception as e:
#         err = f"Failed to update Cosmos DB: {str(e)}"
#         print(f"{Fore.RED}✘ {err}{Style.RESET_ALL}")
#         return {**state, "error": err}


# # ── NODE 4: Provision Azure AD ────────────────────────────────
# def provision_azure_ad_node(state: OnboardingState) -> OnboardingState:
#     eligible = state["eligible_candidates"]

#     if not eligible:
#         print(f"\n{Fore.YELLOW}⚠ No eligible candidates — skipping Azure AD provisioning.{Style.RESET_ALL}")
#         return {**state, "ad_results": []}

#     try:
#         ad_results = provision_eligible_candidates(eligible)

#         # Write AD details back to Cosmos DB
#         container = get_container()
#         for result in ad_results:
#             if result.get("azure_ad_object_id"):
#                 update_candidate_status(
#                     container    = container,
#                     candidate_id = result["candidate_id"],
#                     new_status   = "AD_PROVISIONED",
#                     extra_fields = {
#                         "azure_ad_object_id": result["azure_ad_object_id"],
#                         "upn"               : result["upn"],
#                         "ad_status"         : result["ad_status"],
#                         "provisioned_at"    : datetime.datetime.utcnow().isoformat() + "Z",
#                     },
#                 )

#         return {**state, "ad_results": ad_results}

#     except Exception as e:
#         err = f"Azure AD provisioning failed: {str(e)}"
#         print(f"{Fore.RED}✘ {err}{Style.RESET_ALL}")
#         return {**state, "error": err, "ad_results": []}


# # ── NODE 5: Send Emails ───────────────────────────────────────
# def send_emails_node(state: OnboardingState) -> OnboardingState:
#     try:
#         mail_results = send_all_notifications(
#             eligible_candidates = state["eligible_candidates"],
#             rejected_candidates = state["rejected_candidates"],
#             ad_results          = state["ad_results"],
#         )
#         return {**state, "mail_results": mail_results}
#     except Exception as e:
#         err = f"Email sending failed: {str(e)}"
#         print(f"{Fore.RED}✘ {err}{Style.RESET_ALL}")
#         return {**state, "error": err}


# # ── NODE 6: Final Summary ─────────────────────────────────────
# def summary_node(state: OnboardingState) -> OnboardingState:
#     results      = state["validation_results"]
#     ad_results   = state["ad_results"]
#     mail_results = state["mail_results"]

#     print(f"\n{Fore.CYAN}{'='*60}")
#     print(f"  FINAL SUMMARY — Steps 3 + 4 + 5")
#     print(f"{'='*60}{Style.RESET_ALL}")

#     print(f"\n  📋 VALIDATION (Step 3)")
#     print(f"     Total Processed : {len(results)}")
#     print(f"     ✅ Eligible      : {len(state['eligible_ids'])}")
#     print(f"     ❌ Rejected      : {len(state['rejected_ids'])}")

#     for r in results:
#         icon  = "✅" if r["decision"] == "ELIGIBLE" else "❌"
#         color = Fore.GREEN if r["decision"] == "ELIGIBLE" else Fore.RED
#         print(f"\n     {icon} {color}{r['candidate_name']}{Style.RESET_ALL} — {r['match_percentage']}% match")
#         print(f"        Matched : {r['matched_skills']}")
#         print(f"        Missing : {r['missing_skills']}")

#     print(f"\n  👤 AZURE AD PROVISIONING (Step 4)")
#     if ad_results:
#         for r in ad_results:
#             icon = "✅" if r["ad_status"] in ["CREATED", "ALREADY_EXISTS"] else "❌"
#             print(f"     {icon} {r['candidate_name']} → {r['ad_status']} | UPN: {r.get('upn', 'N/A')}")
#     else:
#         print(f"     No AD accounts created.")

#     print(f"\n  📧 EMAIL NOTIFICATIONS (Step 5)")
#     print(f"     ✔ Sent   : {mail_results.get('sent', 0)}")
#     print(f"     ✘ Failed : {mail_results.get('failed', 0)}")

#     print(f"\n{Fore.GREEN}  ✔ All steps completed. Cosmos DB updated.{Style.RESET_ALL}")
#     print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}\n")

#     return state


# # ── Conditional Edge ──────────────────────────────────────────
# def should_continue_validation(state: OnboardingState) -> str:
#     if state["current_index"] < len(state["candidates"]):
#         return "continue"
#     return "done"


# # ── Build Graph ───────────────────────────────────────────────
# def build_validation_graph() -> StateGraph:
#     graph = StateGraph(OnboardingState)

#     graph.add_node("fetch_candidates",   fetch_candidates_node)
#     graph.add_node("validate_candidate", validate_candidate_node)
#     graph.add_node("update_cosmos",      update_cosmos_node)
#     graph.add_node("provision_azure_ad", provision_azure_ad_node)
#     graph.add_node("send_emails",        send_emails_node)
#     graph.add_node("summary",            summary_node)

#     graph.set_entry_point("fetch_candidates")
#     graph.add_edge("fetch_candidates", "validate_candidate")

#     graph.add_conditional_edges(
#         "validate_candidate",
#         should_continue_validation,
#         {
#             "continue": "validate_candidate",
#             "done"    : "update_cosmos",
#         }
#     )

#     graph.add_edge("update_cosmos",      "provision_azure_ad")
#     graph.add_edge("provision_azure_ad", "send_emails")
#     graph.add_edge("send_emails",        "summary")
#     graph.add_edge("summary",            END)

#     return graph.compile()


# ============================================================
#   graph.py — LangGraph Workflow: Steps 3 + 4 + 5 + 6
# ============================================================

















# import datetime
# from typing import TypedDict, List, Optional
# from langgraph.graph import StateGraph, END
# from colorama import Fore, Style

# from cosmos_client import (
#     get_container,
#     fetch_pending_candidates,
#     update_candidate_status,
# )
# from agents.iam_validation_agent import run_iam_validation
# from agents.azure_ad_agent import provision_eligible_candidates
# from agents.mail_agent import send_all_notifications
# from agents.rbac_agent import assign_learner_roles


# # ── LangGraph State Schema ────────────────────────────────────
# class OnboardingState(TypedDict):
#     candidates          : List[dict]
#     current_index       : int
#     validation_results  : List[dict]
#     eligible_candidates : List[dict]
#     rejected_candidates : List[dict]
#     eligible_ids        : List[str]
#     rejected_ids        : List[str]
#     ad_results          : List[dict]
#     rbac_results        : List[dict]
#     mail_results        : dict
#     error               : Optional[str]


# # ── NODE 1: Fetch Candidates ──────────────────────────────────
# def fetch_candidates_node(state: OnboardingState) -> OnboardingState:
#     print(f"\n{Fore.CYAN}{'='*60}")
#     print(f"  NODE 1 — Fetching Pending Candidates from Cosmos DB")
#     print(f"{'='*60}{Style.RESET_ALL}")

#     try:
#         container  = get_container()
#         candidates = fetch_pending_candidates(container)

#         if not candidates:
#             print(f"{Fore.YELLOW}⚠ No PENDING_VALIDATION candidates found.{Style.RESET_ALL}")
#         else:
#             print(f"{Fore.GREEN}✔ Found {len(candidates)} pending candidate(s).{Style.RESET_ALL}")
#             for c in candidates:
#                 print(f"   → {c['name']} ({c['id']})")

#         return {
#             **state,
#             "candidates"         : candidates,
#             "current_index"      : 0,
#             "validation_results" : [],
#             "eligible_candidates": [],
#             "rejected_candidates": [],
#             "eligible_ids"       : [],
#             "rejected_ids"       : [],
#             "ad_results"         : [],
#             "rbac_results"       : [],
#             "mail_results"       : {},
#             "error"              : None,
#         }
#     except Exception as e:
#         err = f"Failed to fetch candidates: {str(e)}"
#         print(f"{Fore.RED}✘ {err}{Style.RESET_ALL}")
#         return {**state, "error": err, "candidates": []}


# # ── NODE 2: Validate Candidate (loops) ───────────────────────
# def validate_candidate_node(state: OnboardingState) -> OnboardingState:
#     candidates = state["candidates"]
#     idx        = state["current_index"]

#     if idx >= len(candidates):
#         return state

#     candidate = candidates[idx]
#     print(f"\n{Fore.CYAN}{'='*60}")
#     print(f"  NODE 2 — Validating Candidate {idx+1}/{len(candidates)}")
#     print(f"{'='*60}{Style.RESET_ALL}")

#     result = run_iam_validation(candidate)

#     validation_entry = {
#         "candidate_id"   : candidate["id"],
#         "candidate_name" : candidate["name"],
#         "email"          : candidate["email"],
#         "decision"       : result["decision"],
#         "match_percentage": result["match_percentage"],
#         "matched_skills" : result["matched_skills"],
#         "missing_skills" : result["missing_skills"],
#         "reasoning"      : result["reasoning"],
#     }

#     updated_results   = state["validation_results"] + [validation_entry]
#     updated_eligible  = state["eligible_ids"].copy()
#     updated_rejected  = state["rejected_ids"].copy()
#     updated_elig_docs = state["eligible_candidates"].copy()
#     updated_rej_docs  = state["rejected_candidates"].copy()

#     enriched = {
#         **candidate,
#         "matched_skills_found": result["matched_skills"],
#         "missing_skills"      : result["missing_skills"],
#         "match_percentage"    : result["match_percentage"],
#     }

#     if result["decision"] == "ELIGIBLE":
#         updated_eligible.append(candidate["id"])
#         updated_elig_docs.append(enriched)
#     else:
#         updated_rejected.append(candidate["id"])
#         updated_rej_docs.append(enriched)

#     return {
#         **state,
#         "validation_results"  : updated_results,
#         "eligible_ids"        : updated_eligible,
#         "rejected_ids"        : updated_rejected,
#         "eligible_candidates" : updated_elig_docs,
#         "rejected_candidates" : updated_rej_docs,
#         "current_index"       : idx + 1,
#     }


# # ── NODE 3: Update Cosmos DB ──────────────────────────────────
# def update_cosmos_node(state: OnboardingState) -> OnboardingState:
#     print(f"\n{Fore.CYAN}{'='*60}")
#     print(f"  NODE 3 — Updating Cosmos DB with Validation Results")
#     print(f"{'='*60}{Style.RESET_ALL}")

#     try:
#         container = get_container()
#         for result in state["validation_results"]:
#             extra_fields = {
#                 "validation_result"    : result["decision"],
#                 "match_percentage"     : result["match_percentage"],
#                 "matched_skills_found" : result["matched_skills"],
#                 "missing_skills"       : result["missing_skills"],
#                 "validation_reasoning" : result["reasoning"],
#                 "validated_at"         : datetime.datetime.utcnow().isoformat() + "Z",
#             }
#             update_candidate_status(
#                 container    = container,
#                 candidate_id = result["candidate_id"],
#                 new_status   = result["decision"],
#                 extra_fields = extra_fields,
#             )
#         return state
#     except Exception as e:
#         err = f"Failed to update Cosmos DB: {str(e)}"
#         print(f"{Fore.RED}✘ {err}{Style.RESET_ALL}")
#         return {**state, "error": err}


# # ── NODE 4: Provision Azure AD ────────────────────────────────
# def provision_azure_ad_node(state: OnboardingState) -> OnboardingState:
#     eligible = state["eligible_candidates"]

#     if not eligible:
#         print(f"\n{Fore.YELLOW}⚠ No eligible candidates — skipping Azure AD provisioning.{Style.RESET_ALL}")
#         return {**state, "ad_results": []}

#     try:
#         ad_results = provision_eligible_candidates(eligible)

#         container = get_container()
#         for result in ad_results:
#             if result.get("azure_ad_object_id"):
#                 update_candidate_status(
#                     container    = container,
#                     candidate_id = result["candidate_id"],
#                     new_status   = "AD_PROVISIONED",
#                     extra_fields = {
#                         "azure_ad_object_id": result["azure_ad_object_id"],
#                         "upn"               : result["upn"],
#                         "ad_status"         : result["ad_status"],
#                         "provisioned_at"    : datetime.datetime.utcnow().isoformat() + "Z",
#                     },
#                 )

#         return {**state, "ad_results": ad_results}

#     except Exception as e:
#         err = f"Azure AD provisioning failed: {str(e)}"
#         print(f"{Fore.RED}✘ {err}{Style.RESET_ALL}")
#         return {**state, "error": err, "ad_results": []}


# # ── NODE 5: Assign RBAC Learner Role ─────────────────────────
# def assign_rbac_node(state: OnboardingState) -> OnboardingState:
#     try:
#         rbac_results = assign_learner_roles(state["ad_results"])

#         # Update Cosmos DB with RBAC info
#         container = get_container()
#         for result in rbac_results:
#             if result.get("rbac_status") in ["ASSIGNED", "ALREADY_ASSIGNED"]:
#                 update_candidate_status(
#                     container    = container,
#                     candidate_id = result["candidate_id"],
#                     new_status   = "RBAC_ASSIGNED",
#                     extra_fields = {
#                         "rbac_role"         : "Learner",
#                         "rbac_status"       : result["rbac_status"],
#                         "rbac_assignment_id": result.get("assignment_id"),
#                         "rbac_assigned_at"  : datetime.datetime.utcnow().isoformat() + "Z",
#                     },
#                 )

#         return {**state, "rbac_results": rbac_results}

#     except Exception as e:
#         err = f"RBAC assignment failed: {str(e)}"
#         print(f"{Fore.RED}✘ {err}{Style.RESET_ALL}")
#         return {**state, "error": err, "rbac_results": []}


# # ── NODE 6: Send Emails ───────────────────────────────────────
# def send_emails_node(state: OnboardingState) -> OnboardingState:
#     try:
#         mail_results = send_all_notifications(
#             eligible_candidates = state["eligible_candidates"],
#             rejected_candidates = state["rejected_candidates"],
#             ad_results          = state["ad_results"],
#         )
#         return {**state, "mail_results": mail_results}
#     except Exception as e:
#         err = f"Email sending failed: {str(e)}"
#         print(f"{Fore.RED}✘ {err}{Style.RESET_ALL}")
#         return {**state, "error": err}


# # ── NODE 7: Final Summary ─────────────────────────────────────
# def summary_node(state: OnboardingState) -> OnboardingState:
#     results      = state["validation_results"]
#     ad_results   = state["ad_results"]
#     rbac_results = state["rbac_results"]
#     mail_results = state["mail_results"]

#     print(f"\n{Fore.CYAN}{'='*60}")
#     print(f"  FINAL SUMMARY — Steps 3 + 4 + 5 + 6")
#     print(f"{'='*60}{Style.RESET_ALL}")

#     print(f"\n  📋 VALIDATION (Step 3)")
#     print(f"     Total : {len(results)} | ✅ Eligible: {len(state['eligible_ids'])} | ❌ Rejected: {len(state['rejected_ids'])}")
#     for r in results:
#         icon  = "✅" if r["decision"] == "ELIGIBLE" else "❌"
#         color = Fore.GREEN if r["decision"] == "ELIGIBLE" else Fore.RED
#         print(f"     {icon} {color}{r['candidate_name']}{Style.RESET_ALL} — {r['match_percentage']}% match")

#     print(f"\n  👤 AZURE AD PROVISIONING (Step 4)")
#     if ad_results:
#         for r in ad_results:
#             icon = "✅" if r["ad_status"] in ["CREATED", "ALREADY_EXISTS"] else "❌"
#             print(f"     {icon} {r['candidate_name']} → {r['ad_status']} | UPN: {r.get('upn', 'N/A')}")
#     else:
#         print(f"     No AD accounts created.")

#     print(f"\n  🔐 RBAC ASSIGNMENT (Step 6)")
#     if rbac_results:
#         for r in rbac_results:
#             icon = "✅" if r["rbac_status"] in ["ASSIGNED", "ALREADY_ASSIGNED"] else "❌"
#             print(f"     {icon} {r['candidate_name']} → {r['rbac_status']} | Role: {r['role_assigned']}")
#     else:
#         print(f"     No RBAC assignments made.")

#     print(f"\n  📧 EMAIL NOTIFICATIONS (Step 5)")
#     print(f"     ✔ Sent: {mail_results.get('sent', 0)} | ✘ Failed: {mail_results.get('failed', 0)}")

#     print(f"\n{Fore.GREEN}  ✔ All steps completed. Cosmos DB updated.{Style.RESET_ALL}")
#     print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}\n")

#     return state


# # ── Conditional Edge ──────────────────────────────────────────
# def should_continue_validation(state: OnboardingState) -> str:
#     if state["current_index"] < len(state["candidates"]):
#         return "continue"
#     return "done"


# # ── Build Graph ───────────────────────────────────────────────
# def build_validation_graph() -> StateGraph:
#     graph = StateGraph(OnboardingState)

#     graph.add_node("fetch_candidates",   fetch_candidates_node)
#     graph.add_node("validate_candidate", validate_candidate_node)
#     graph.add_node("update_cosmos",      update_cosmos_node)
#     graph.add_node("provision_azure_ad", provision_azure_ad_node)
#     graph.add_node("assign_rbac",        assign_rbac_node)
#     graph.add_node("send_emails",        send_emails_node)
#     graph.add_node("summary",            summary_node)

#     graph.set_entry_point("fetch_candidates")
#     graph.add_edge("fetch_candidates", "validate_candidate")

#     graph.add_conditional_edges(
#         "validate_candidate",
#         should_continue_validation,
#         {
#             "continue": "validate_candidate",
#             "done"    : "update_cosmos",
#         }
#     )

#     graph.add_edge("update_cosmos",      "provision_azure_ad")
#     graph.add_edge("provision_azure_ad", "assign_rbac")
#     graph.add_edge("assign_rbac",        "send_emails")
#     graph.add_edge("send_emails",        "summary")
#     graph.add_edge("summary",            END)

#     return graph.compile()












# ============================================================
#   graph.py — LangGraph Workflow: Steps 3 + 4 + 5 + 6 + 7
# ============================================================

import datetime
from typing import TypedDict, List, Optional
from langgraph.graph import StateGraph, END
from colorama import Fore, Style

from cosmos_client import (
    get_container,
    fetch_pending_candidates,
    update_candidate_status,
)
from agents.iam_validation_agent import run_iam_validation
from agents.azure_ad_agent import provision_eligible_candidates
from agents.mail_agent import send_all_notifications
from agents.rbac_agent import assign_learner_roles
from agents.onboarding_meeting_agent import send_onboarding_meeting_invites


# ── LangGraph State Schema ────────────────────────────────────
class OnboardingState(TypedDict):
    candidates           : List[dict]
    current_index        : int
    validation_results   : List[dict]
    eligible_candidates  : List[dict]
    rejected_candidates  : List[dict]
    eligible_ids         : List[str]
    rejected_ids         : List[str]
    ad_results           : List[dict]
    rbac_results         : List[dict]
    mail_results         : dict
    meeting_results      : dict
    error                : Optional[str]


# ── NODE 1: Fetch Candidates ──────────────────────────────────
def fetch_candidates_node(state: OnboardingState) -> OnboardingState:
    print(f"\n{Fore.CYAN}{'='*60}")
    print(f"  NODE 1 — Fetching Pending Candidates from Cosmos DB")
    print(f"{'='*60}{Style.RESET_ALL}")

    try:
        container  = get_container()
        candidates = fetch_pending_candidates(container)

        if not candidates:
            print(f"{Fore.YELLOW}⚠ No PENDING_VALIDATION candidates found.{Style.RESET_ALL}")
        else:
            print(f"{Fore.GREEN}✔ Found {len(candidates)} pending candidate(s).{Style.RESET_ALL}")
            for c in candidates:
                print(f"   → {c['name']} ({c['id']})")

        return {
            **state,
            "candidates"         : candidates,
            "current_index"      : 0,
            "validation_results" : [],
            "eligible_candidates": [],
            "rejected_candidates": [],
            "eligible_ids"       : [],
            "rejected_ids"       : [],
            "ad_results"         : [],
            "rbac_results"       : [],
            "mail_results"       : {},
            "meeting_results"    : {},
            "error"              : None,
        }
    except Exception as e:
        err = f"Failed to fetch candidates: {str(e)}"
        print(f"{Fore.RED}✘ {err}{Style.RESET_ALL}")
        return {**state, "error": err, "candidates": []}


# ── NODE 2: Validate Candidate (loops) ───────────────────────
def validate_candidate_node(state: OnboardingState) -> OnboardingState:
    candidates = state["candidates"]
    idx        = state["current_index"]

    if idx >= len(candidates):
        return state

    candidate = candidates[idx]
    print(f"\n{Fore.CYAN}{'='*60}")
    print(f"  NODE 2 — Validating Candidate {idx+1}/{len(candidates)}")
    print(f"{'='*60}{Style.RESET_ALL}")

    result           = run_iam_validation(candidate)
    validation_entry = {
        "candidate_id"    : candidate["id"],
        "candidate_name"  : candidate["name"],
        "email"           : candidate["email"],
        "decision"        : result["decision"],
        "match_percentage": result["match_percentage"],
        "matched_skills"  : result["matched_skills"],
        "missing_skills"  : result["missing_skills"],
        "reasoning"       : result["reasoning"],
    }

    updated_results   = state["validation_results"] + [validation_entry]
    updated_eligible  = state["eligible_ids"].copy()
    updated_rejected  = state["rejected_ids"].copy()
    updated_elig_docs = state["eligible_candidates"].copy()
    updated_rej_docs  = state["rejected_candidates"].copy()

    enriched = {
        **candidate,
        "matched_skills_found": result["matched_skills"],
        "missing_skills"      : result["missing_skills"],
        "match_percentage"    : result["match_percentage"],
    }

    if result["decision"] == "ELIGIBLE":
        updated_eligible.append(candidate["id"])
        updated_elig_docs.append(enriched)
    else:
        updated_rejected.append(candidate["id"])
        updated_rej_docs.append(enriched)

    return {
        **state,
        "validation_results"  : updated_results,
        "eligible_ids"        : updated_eligible,
        "rejected_ids"        : updated_rejected,
        "eligible_candidates" : updated_elig_docs,
        "rejected_candidates" : updated_rej_docs,
        "current_index"       : idx + 1,
    }


# ── NODE 3: Update Cosmos DB ──────────────────────────────────
def update_cosmos_node(state: OnboardingState) -> OnboardingState:
    print(f"\n{Fore.CYAN}{'='*60}")
    print(f"  NODE 3 — Updating Cosmos DB with Validation Results")
    print(f"{'='*60}{Style.RESET_ALL}")

    try:
        container = get_container()
        for result in state["validation_results"]:
            extra_fields = {
                "validation_result"    : result["decision"],
                "match_percentage"     : result["match_percentage"],
                "matched_skills_found" : result["matched_skills"],
                "missing_skills"       : result["missing_skills"],
                "validation_reasoning" : result["reasoning"],
                "validated_at"         : datetime.datetime.utcnow().isoformat() + "Z",
            }
            update_candidate_status(
                container    = container,
                candidate_id = result["candidate_id"],
                new_status   = result["decision"],
                extra_fields = extra_fields,
            )
        return state
    except Exception as e:
        err = f"Failed to update Cosmos DB: {str(e)}"
        print(f"{Fore.RED}✘ {err}{Style.RESET_ALL}")
        return {**state, "error": err}


# ── NODE 4: Provision Azure AD ────────────────────────────────
def provision_azure_ad_node(state: OnboardingState) -> OnboardingState:
    eligible = state["eligible_candidates"]

    if not eligible:
        print(f"\n{Fore.YELLOW}⚠ No eligible candidates — skipping Azure AD provisioning.{Style.RESET_ALL}")
        return {**state, "ad_results": []}

    try:
        ad_results = provision_eligible_candidates(eligible)
        container  = get_container()

        for result in ad_results:
            if result.get("azure_ad_object_id"):
                update_candidate_status(
                    container    = container,
                    candidate_id = result["candidate_id"],
                    new_status   = "AD_PROVISIONED",
                    extra_fields = {
                        "azure_ad_object_id": result["azure_ad_object_id"],
                        "upn"               : result["upn"],
                        "ad_status"         : result["ad_status"],
                        "provisioned_at"    : datetime.datetime.utcnow().isoformat() + "Z",
                    },
                )

        return {**state, "ad_results": ad_results}

    except Exception as e:
        err = f"Azure AD provisioning failed: {str(e)}"
        print(f"{Fore.RED}✘ {err}{Style.RESET_ALL}")
        return {**state, "error": err, "ad_results": []}


# ── NODE 5: Assign RBAC Learner Role ─────────────────────────
def assign_rbac_node(state: OnboardingState) -> OnboardingState:
    try:
        rbac_results = assign_learner_roles(state["ad_results"])
        container    = get_container()

        for result in rbac_results:
            if result.get("rbac_status") in ["ASSIGNED", "ALREADY_ASSIGNED"]:
                update_candidate_status(
                    container    = container,
                    candidate_id = result["candidate_id"],
                    new_status   = "RBAC_ASSIGNED",
                    extra_fields = {
                        "rbac_role"         : "Learner",
                        "rbac_status"       : result["rbac_status"],
                        "rbac_assignment_id": result.get("assignment_id"),
                        "rbac_assigned_at"  : datetime.datetime.utcnow().isoformat() + "Z",
                    },
                )

        return {**state, "rbac_results": rbac_results}

    except Exception as e:
        err = f"RBAC assignment failed: {str(e)}"
        print(f"{Fore.RED}✘ {err}{Style.RESET_ALL}")
        return {**state, "error": err, "rbac_results": []}


# ── NODE 6: Send Selection/Rejection Emails ───────────────────
def send_emails_node(state: OnboardingState) -> OnboardingState:
    try:
        mail_results = send_all_notifications(
            eligible_candidates = state["eligible_candidates"],
            rejected_candidates = state["rejected_candidates"],
            ad_results          = state["ad_results"],
        )
        return {**state, "mail_results": mail_results}
    except Exception as e:
        err = f"Email sending failed: {str(e)}"
        print(f"{Fore.RED}✘ {err}{Style.RESET_ALL}")
        return {**state, "error": err}


# ── NODE 7: Send Onboarding Meeting Invites ───────────────────
def send_meeting_invites_node(state: OnboardingState) -> OnboardingState:
    try:
        meeting_results = send_onboarding_meeting_invites(
            eligible_candidates = state["eligible_candidates"],
            ad_results          = state["ad_results"],
        )

        # Update Cosmos DB with meeting info
        container = get_container()
        for candidate in state["eligible_candidates"]:
            update_candidate_status(
                container    = container,
                candidate_id = candidate["id"],
                new_status   = "MEETING_INVITED",
                extra_fields = {
                    "meeting_date"      : meeting_results.get("meeting_date"),
                    "meeting_time"      : meeting_results.get("meeting_time"),
                    "meeting_link"      : meeting_results.get("meeting_link"),
                    "meeting_invited_at": datetime.datetime.utcnow().isoformat() + "Z",
                },
            )

        return {**state, "meeting_results": meeting_results}

    except Exception as e:
        err = f"Meeting invite failed: {str(e)}"
        print(f"{Fore.RED}✘ {err}{Style.RESET_ALL}")
        return {**state, "error": err}


# ── NODE 8: Final Summary ─────────────────────────────────────
def summary_node(state: OnboardingState) -> OnboardingState:
    results         = state["validation_results"]
    ad_results      = state["ad_results"]
    rbac_results    = state["rbac_results"]
    mail_results    = state["mail_results"]
    meeting_results = state["meeting_results"]

    print(f"\n{Fore.CYAN}{'='*60}")
    print(f"  FINAL SUMMARY — Steps 3 + 4 + 5 + 6 + 7")
    print(f"{'='*60}{Style.RESET_ALL}")

    print(f"\n  📋 VALIDATION (Step 3)")
    print(f"     Total : {len(results)} | ✅ Eligible: {len(state['eligible_ids'])} | ❌ Rejected: {len(state['rejected_ids'])}")
    for r in results:
        icon  = "✅" if r["decision"] == "ELIGIBLE" else "❌"
        color = Fore.GREEN if r["decision"] == "ELIGIBLE" else Fore.RED
        print(f"     {icon} {color}{r['candidate_name']}{Style.RESET_ALL} — {r['match_percentage']}% match")

    print(f"\n  👤 AZURE AD PROVISIONING (Step 4)")
    for r in ad_results:
        icon = "✅" if r["ad_status"] in ["CREATED", "ALREADY_EXISTS"] else "❌"
        print(f"     {icon} {r['candidate_name']} → {r['ad_status']} | UPN: {r.get('upn', 'N/A')}")

    print(f"\n  🔐 RBAC ASSIGNMENT (Step 6)")
    if rbac_results:
        for r in rbac_results:
            icon = "✅" if r["rbac_status"] in ["ASSIGNED", "ALREADY_ASSIGNED"] else "❌"
            print(f"     {icon} {r['candidate_name']} → {r['rbac_status']} | Role: {r['role_assigned']}")
    else:
        print(f"     No RBAC assignments made.")

    print(f"\n  📧 EMAIL NOTIFICATIONS (Step 5)")
    print(f"     ✔ Sent: {mail_results.get('sent', 0)} | ✘ Failed: {mail_results.get('failed', 0)}")

    print(f"\n  📅 ONBOARDING MEETING INVITES (Step 7)")
    print(f"     ✔ Sent    : {meeting_results.get('sent', 0)}")
    print(f"     ✘ Failed  : {meeting_results.get('failed', 0)}")
    print(f"     📅 Date   : {meeting_results.get('meeting_date', 'N/A')}")
    print(f"     ⏰ Time   : {meeting_results.get('meeting_time', 'N/A')}")
    print(f"     🔗 Link   : {meeting_results.get('meeting_link', 'N/A')}")

    print(f"\n{Fore.GREEN}  ✔ All steps completed. Cosmos DB updated.{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}\n")

    return state


# ── Conditional Edge ──────────────────────────────────────────
def should_continue_validation(state: OnboardingState) -> str:
    if state["current_index"] < len(state["candidates"]):
        return "continue"
    return "done"


# ── Build Graph ───────────────────────────────────────────────
def build_validation_graph() -> StateGraph:
    graph = StateGraph(OnboardingState)

    graph.add_node("fetch_candidates",      fetch_candidates_node)
    graph.add_node("validate_candidate",    validate_candidate_node)
    graph.add_node("update_cosmos",         update_cosmos_node)
    graph.add_node("provision_azure_ad",    provision_azure_ad_node)
    graph.add_node("assign_rbac",           assign_rbac_node)
    graph.add_node("send_emails",           send_emails_node)
    graph.add_node("send_meeting_invites",  send_meeting_invites_node)
    graph.add_node("summary",              summary_node)

    graph.set_entry_point("fetch_candidates")
    graph.add_edge("fetch_candidates", "validate_candidate")

    graph.add_conditional_edges(
        "validate_candidate",
        should_continue_validation,
        {
            "continue": "validate_candidate",
            "done"    : "update_cosmos",
        }
    )

    graph.add_edge("update_cosmos",        "provision_azure_ad")
    graph.add_edge("provision_azure_ad",   "assign_rbac")
    graph.add_edge("assign_rbac",          "send_emails")
    graph.add_edge("send_emails",          "send_meeting_invites")
    graph.add_edge("send_meeting_invites", "summary")
    graph.add_edge("summary",              END)

    return graph.compile()