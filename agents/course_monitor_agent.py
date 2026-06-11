# ============================================================
#   agents/course_monitor_agent.py — Step 8
#   Checks course completion every 10 mins
#   Marks FAILED if deadline exceeded without completion
# ============================================================

import os
import time
import datetime
import sys
from colorama import Fore, Style
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from cosmos_client import get_container, update_candidate_status

load_dotenv()

COURSE_DEADLINE_MINUTES  = int(os.getenv("COURSE_DEADLINE_MINUTES", "60"))
MONITOR_INTERVAL_SECONDS = int(os.getenv("MONITOR_INTERVAL_SECONDS", "600"))  # 10 mins default


def check_all_trainees() -> dict:
    """
    Checks all active trainees:
    - COMPLETED via portal → mark COURSE_COMPLETED
    - Deadline exceeded   → mark COURSE_FAILED
    - Still in progress   → leave as is
    """
    print(f"\n{Fore.CYAN}{'='*60}")
    print(f"  STEP 8 — Course Monitor ({datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")
    print(f"{'='*60}{Style.RESET_ALL}")

    container = get_container()
    query     = """
        SELECT * FROM c
        WHERE c.status IN ('IN_TRAINING', 'MEETING_INVITED', 'RBAC_ASSIGNED', 'COURSE_COMPLETED')
    """
    trainees  = list(container.query_items(query=query, enable_cross_partition_query=True))

    if not trainees:
        print(f"  {Fore.YELLOW}⚠ No active trainees found.{Style.RESET_ALL}")
        return {"completed": [], "failed": [], "in_progress": []}

    print(f"  📋 Checking {len(trainees)} active trainee(s)...\n")

    completed   = []
    failed      = []
    in_progress = []

    for trainee in trainees:
        name          = trainee.get("name", "Unknown")
        cid           = trainee["id"]
        course_status = trainee.get("course_status", "NOT_STARTED")
        start_time    = trainee.get("course_start_time")
        watch_pct     = trainee.get("watch_percentage", 0)

        print(f"  👤 {name}")
        print(f"     Course Status  : {course_status}")
        print(f"     Watch Progress : {watch_pct}%")

        # ── Completed via portal ──────────────────────────────
        if (course_status == "COMPLETED" or trainee.get("status") == "COURSE_COMPLETED") and not trainee.get("certificate_sent"):
            print(f"     {Fore.GREEN}✅ COMPLETED{Style.RESET_ALL}")
            update_candidate_status(
                container    = container,
                candidate_id = cid,
                new_status   = "COURSE_COMPLETED",
                extra_fields = {
                    "monitor_checked_at": datetime.datetime.utcnow().isoformat() + "Z"
                }
            )
            completed.append(trainee)

        # ── Check deadline ────────────────────────────────────
        elif start_time:
            start_dt    = datetime.datetime.fromisoformat(start_time.replace("Z", ""))
            elapsed_min = (datetime.datetime.utcnow() - start_dt).total_seconds() / 60
            remaining   = COURSE_DEADLINE_MINUTES - elapsed_min

            print(f"     Elapsed        : {elapsed_min:.1f} mins")
            print(f"     Remaining      : {max(0, remaining):.1f} mins")

            if elapsed_min > COURSE_DEADLINE_MINUTES:
                print(f"     {Fore.RED}❌ DEADLINE EXCEEDED → FAILED{Style.RESET_ALL}")
                update_candidate_status(
                    container    = container,
                    candidate_id = cid,
                    new_status   = "COURSE_FAILED",
                    extra_fields = {
                        "course_status"  : "FAILED",
                        "failed_reason"  : "Deadline exceeded without completing course",
                        "failed_at"      : datetime.datetime.utcnow().isoformat() + "Z",
                        "elapsed_minutes": round(elapsed_min, 1),
                    }
                )
                failed.append(trainee)
            else:
                print(f"     {Fore.YELLOW}⏳ IN PROGRESS{Style.RESET_ALL}")
                in_progress.append(trainee)

        # ── Not started yet ───────────────────────────────────
        else:
            print(f"     {Fore.YELLOW}⬜ NOT STARTED YET{Style.RESET_ALL}")
            in_progress.append(trainee)

        print()

    print(f"  ✅ Completed   : {len(completed)}")
    print(f"  ❌ Failed      : {len(failed)}")
    print(f"  ⏳ In Progress : {len(in_progress)}")

    return {
        "completed"  : completed,
        "failed"     : failed,
        "in_progress": in_progress,
    }


def run_monitor_loop(callback=None):
    """
    Loops every MONITOR_INTERVAL_SECONDS.
    Stops when no more active trainees remain.
    """
    print(f"\n{Fore.CYAN}🔄 Course Monitor Started{Style.RESET_ALL}")
    print(f"   Interval : every {MONITOR_INTERVAL_SECONDS // 60} min(s)")
    print(f"   Deadline : {COURSE_DEADLINE_MINUTES} minutes\n")

    while True:
        results = check_all_trainees()
        if callback:
            callback(results)

        if not results["in_progress"]:
            print(f"\n{Fore.GREEN}✔ All trainees processed. Monitor stopping.{Style.RESET_ALL}")
            break

        print(f"\n  ⏰ Next check in {MONITOR_INTERVAL_SECONDS // 60} min(s)...")
        time.sleep(MONITOR_INTERVAL_SECONDS)


def run_single_check() -> dict:
    """Single check — used by pipeline or manual trigger."""
    return check_all_trainees()