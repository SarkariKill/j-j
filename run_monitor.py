#!/usr/bin/env python3
# ============================================================
#   run_monitor.py — Steps 8 + 9 + 10 + 11
#   Step 8  : Monitor course completion every N mins
#   Step 9  : Auto-remove failed trainees
#   Step 10 : Generate + send completion certificate
#   Step 11 : Upgrade RBAC + Promote Trainee → Employee
# ============================================================

import sys
import os
from colorama import Fore, Style, init

init(autoreset=True)

from cosmos_client import get_container
from agents.course_monitor_agent import run_monitor_loop, run_single_check
from agents.removal_agent import process_failed_trainees
from agents.certificate_agent import process_completed_trainees
from agents.promotion_agent import promote_completed_trainees


def handle_monitor_results(results: dict):
    """
    Callback after each monitor check.
    Step 9  → failed candidates
    Step 10 → certificate for completed
    Step 11 → RBAC upgrade + AD promotion
    """
    failed_list    = results.get("failed", [])
    completed_list = results.get("completed", [])
    container      = get_container()

    # ── Step 9: Remove failed trainees ───────────────────────
    if failed_list:
        print(f"\n{Fore.RED}⚡ {len(failed_list)} failed — triggering Step 9 (Removal)...{Style.RESET_ALL}")
        full_failed = []
        for candidate in failed_list:
            try:
                item = container.read_item(item=candidate["id"], partition_key=candidate["id"])
                full_failed.append(item)
            except Exception:
                full_failed.append(candidate)
        process_failed_trainees(full_failed, container)

    # ── Step 10 + 11: Certificate + Promotion ─────────────────
    if completed_list:
        print(f"\n{Fore.GREEN}🎉 {len(completed_list)} completed — triggering Steps 10 + 11...{Style.RESET_ALL}")
        full_completed = []
        for candidate in completed_list:
            try:
                item = container.read_item(item=candidate["id"], partition_key=candidate["id"])
                full_completed.append(item)
            except Exception:
                full_completed.append(candidate)

        # Step 10 — Send certificate
        process_completed_trainees(full_completed, container)

        # Step 11 — Upgrade RBAC + Promote to Employee
        promote_completed_trainees(full_completed, container)


def main():
    print(f"""
{Fore.CYAN}╔══════════════════════════════════════════════════════════╗
║     COURSE MONITOR — Steps 8 + 9 + 10 + 11               ║
║     Step 8  : Monitor completion every N mins             ║
║     Step 9  : Auto-remove failed trainees                 ║
║     Step 10 : Generate + send completion certificate      ║
║     Step 11 : Upgrade RBAC + Promote Trainee → Employee   ║
╚══════════════════════════════════════════════════════════╝{Style.RESET_ALL}
""")

    if "--once" in sys.argv:
        print(f"{Fore.CYAN}🔍 Running single check...{Style.RESET_ALL}")
        results = run_single_check()
        handle_monitor_results(results)
    else:
        run_monitor_loop(callback=handle_monitor_results)

    print(f"\n{Fore.GREEN}✔ Monitor finished.{Style.RESET_ALL}\n")


if __name__ == "__main__":
    main()