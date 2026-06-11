# ============================================================
#   main.py — Entry Point for Step 3 IAM Validation Pipeline
# ============================================================

import sys
import pandas as pd
from colorama import Fore, Style, init

init(autoreset=True)  # Colorama auto-reset after each print

from cosmos_client import get_container, insert_sample_candidates
from graph import build_validation_graph


def main():
    print(f"""
{Fore.CYAN}╔══════════════════════════════════════════════════════════╗
║     ENTERPRISE ONBOARDING AUTOMATION — STEP 3            ║
║     IAM Skill Validation via DeepSeek + LangGraph         ║
╚══════════════════════════════════════════════════════════╝{Style.RESET_ALL}
""")

    # ── Optional: seed test data ──────────────────────────────
    if "--seed" in sys.argv:
        print(f"{Fore.YELLOW}🌱 Seeding sample candidates into Cosmos DB...{Style.RESET_ALL}")
        container = get_container()
        insert_sample_candidates(container)

    # ── Build and run the LangGraph pipeline ──────────────────
    print(f"{Fore.CYAN}🚀 Starting LangGraph Validation Pipeline...{Style.RESET_ALL}")

    graph = build_validation_graph()

    # Initial state — all fields required by OnboardingState TypedDict
    initial_state = {
        "candidates"         : [],
        "current_index"      : 0,
        "validation_results" : [],
        "eligible_ids"       : [],
        "rejected_ids"       : [],
        "error"              : None,
    }

    # Run the graph
    final_state = graph.invoke(initial_state)

    # ── Check for errors ──────────────────────────────────────
    if final_state.get("error"):
        print(f"\n{Fore.RED}❌ Pipeline ended with error: {final_state['error']}{Style.RESET_ALL}")
        sys.exit(1)

    print(f"\n{Fore.GREEN}🎉 Step 3 Pipeline completed successfully!{Style.RESET_ALL}")
    print(f"   Next Step → Step 4: EligibilityDecisionAgent")
    print(f"   Next Step → Step 5: MailNotificationAgent (send selection/rejection mails)\n")


if __name__ == "__main__":
    main()