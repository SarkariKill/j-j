#!/usr/bin/env python3
# ============================================================
#   start.py — ONE CLICK STARTUP
#   Starts entire onboarding pipeline in one command
#
#   Usage: python start.py
#   Options:
#     python start.py --fresh    ← clears DB and reseeds
#     python start.py --monitor  ← skip pipeline, only monitor
# ============================================================

import os
import sys
import time
import threading
import subprocess
import webbrowser
from colorama import Fore, Style, init

init(autoreset=True)

BANNER = f"""
{Fore.CYAN}╔══════════════════════════════════════════════════════════════╗
║       ENTERPRISE ONBOARDING AUTOMATION                       ║
║       Johnson & Johnson — One Click Startup                  ║
╠══════════════════════════════════════════════════════════════╣
║  Step 3  : IAM Skill Validation                              ║
║  Step 4  : Azure AD Provisioning                             ║
║  Step 5  : Email Notifications                               ║
║  Step 6  : RBAC Role Assignment                              ║
║  Step 7  : Onboarding Meeting + Course Link                  ║
║  Step 8  : Course Completion Monitor                         ║
║  Step 9  : Remove Failed Trainees                            ║
║  Step 10 : Generate + Send Certificates                      ║
╚══════════════════════════════════════════════════════════════╝{Style.RESET_ALL}
"""


# ── Helpers ───────────────────────────────────────────────────

def log(msg: str, color=Fore.WHITE):
    print(f"{color}{msg}{Style.RESET_ALL}")


def log_section(title: str):
    print(f"\n{Fore.CYAN}{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}{Style.RESET_ALL}")


def run_python(script: str, args: list = []) -> bool:
    """Runs a python script in the same process directory."""
    cmd    = [sys.executable, script] + args
    result = subprocess.run(cmd, cwd=os.path.dirname(os.path.abspath(__file__)))
    return result.returncode == 0


# ── Phase 1: Fresh Start (optional) ──────────────────────────

def phase_fresh_start():
    log_section("PHASE 0 — Fresh Start (clearing DB + reseeding)")

    # Clear Cosmos DB
    log("🗑  Clearing Cosmos DB...", Fore.YELLOW)
    from cosmos_client import get_container
    container = get_container()
    items     = list(container.query_items(
        query="SELECT * FROM c",
        enable_cross_partition_query=True
    ))
    for item in items:
        container.delete_item(item=item["id"], partition_key=item["id"])
        log(f"   Deleted: {item.get('name', item['id'])}", Fore.YELLOW)

    log(f"✅ Cleared {len(items)} documents from Cosmos DB", Fore.GREEN)

    # Reseed
    log("\n🌱 Seeding fresh candidates...", Fore.CYAN)
    from cosmos_client import insert_sample_candidates
    insert_sample_candidates(container)


# ── Phase 2: Main Pipeline ────────────────────────────────────

def phase_main_pipeline():
    log_section("PHASE 1 — Running Main Onboarding Pipeline (Steps 3-7)")

    from graph import build_validation_graph

    graph = build_validation_graph()
    initial_state = {
        "candidates"         : [],
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

    final_state = graph.invoke(initial_state)

    if final_state.get("error"):
        log(f"❌ Pipeline error: {final_state['error']}", Fore.RED)
        return False

    log("\n✅ Main pipeline completed successfully!", Fore.GREEN)
    return True


# ── Phase 3: Course Portal ────────────────────────────────────

def phase_start_portal():
    log_section("PHASE 2 — Starting Course Portal (Step 8 tracking)")

    # Kill anything already running on port 8000
    os.system("lsof -ti:8000 | xargs kill -9 2>/dev/null || true")
    time.sleep(1)

    def run_portal():
        portal_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "course_portal", "app.py"
        )
        os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), "course_portal"))
        subprocess.run([
            sys.executable, "-m", "uvicorn",
            "app:app",
            "--host", "0.0.0.0",
            "--port", "8000",
            "--log-level", "warning"
        ])

    portal_thread        = threading.Thread(target=run_portal, daemon=True)
    portal_thread.start()

    # Wait for portal to be ready
    log("⏳ Waiting for course portal to start...", Fore.YELLOW)
    time.sleep(3)
    log("✅ Course portal started at http://localhost:8000", Fore.GREEN)
    log("📊 Admin dashboard: http://localhost:8000/admin", Fore.GREEN)

    return portal_thread


# ── Phase 4: Monitor Loop ─────────────────────────────────────

def phase_start_monitor():
    log_section("PHASE 3 — Starting Course Monitor (Steps 8 + 9 + 10)")

    # Change back to main directory
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    from cosmos_client import get_container
    from agents.course_monitor_agent import run_monitor_loop
    from agents.removal_agent import process_failed_trainees
    from agents.certificate_agent import process_completed_trainees
    from agents.promotion_agent import promote_completed_trainees

    def handle_results(results: dict):
        failed_list    = results.get("failed", [])
        completed_list = results.get("completed", [])
        container      = get_container()

        if failed_list:
            log(f"\n⚡ {len(failed_list)} failed — triggering Step 9 (Removal)...", Fore.RED)
            full_failed = []
            for c in failed_list:
                try:
                    item = container.read_item(item=c["id"], partition_key=c["id"])
                    full_failed.append(item)
                except Exception:
                    full_failed.append(c)
            process_failed_trainees(full_failed, container)

        if completed_list:
            log(f"\n🎉 {len(completed_list)} completed — triggering Steps 10 + 11...", Fore.GREEN)
            full_completed = []
            for c in completed_list:
                try:
                    item = container.read_item(item=c["id"], partition_key=c["id"])
                    full_completed.append(item)
                except Exception:
                    full_completed.append(c)

            # Step 10 — Send certificate
            process_completed_trainees(full_completed, container)

            # Step 11 — Upgrade RBAC + Promote to Employee
            promote_completed_trainees(full_completed, container)

    run_monitor_loop(callback=handle_results)


# ── Print Access Links ────────────────────────────────────────

def print_access_links():
    log_section("🌐 ACCESS LINKS")

    from cosmos_client import get_container
    container = get_container()
    query     = "SELECT c.id, c.name, c.status FROM c WHERE c.status NOT IN ('REJECTED', 'REMOVED')"
    trainees  = list(container.query_items(query=query, enable_cross_partition_query=True))

    log("  Admin Dashboard:", Fore.CYAN)
    log("  → http://localhost:8000/admin\n", Fore.WHITE)

    log("  Trainee Course Links:", Fore.CYAN)
    for t in trainees:
        log(f"  → {t.get('name', t['id'])}: http://localhost:8000/course/{t['id']}", Fore.WHITE)

    print()


# ── MAIN ──────────────────────────────────────────────────────

def main():
    print(BANNER)

    fresh_start  = "--fresh"   in sys.argv
    monitor_only = "--monitor" in sys.argv

    # Change to script directory
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    try:
        # ── Phase 0: Fresh start ──────────────────────────────
        if fresh_start:
            phase_fresh_start()

        # ── Phase 1: Main pipeline ────────────────────────────
        if not monitor_only:
            success = phase_main_pipeline()
            if not success:
                log("❌ Pipeline failed. Check errors above.", Fore.RED)
                sys.exit(1)

        # ── Phase 2: Start course portal ──────────────────────
        phase_start_portal()

        # ── Print links ───────────────────────────────────────
        print_access_links()

        # ── Open admin dashboard in browser ───────────────────
        log("🌐 Opening admin dashboard in browser...", Fore.CYAN)
        time.sleep(1)
        webbrowser.open("http://localhost:8000/admin")

        log("\n" + "="*60, Fore.CYAN)
        log("  ✅ EVERYTHING IS RUNNING!", Fore.GREEN)
        log("  Press Ctrl+C to stop all services", Fore.YELLOW)
        log("="*60 + "\n", Fore.CYAN)

        # ── Phase 3: Monitor loop (blocking) ──────────────────
        phase_start_monitor()

    except KeyboardInterrupt:
        log("\n\n⛔ Shutting down all services...", Fore.YELLOW)
        log("✅ Done. Goodbye!", Fore.GREEN)
        sys.exit(0)

    except Exception as e:
        log(f"\n❌ Unexpected error: {e}", Fore.RED)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()