import os
import time
import subprocess
import sys
from dotenv import load_dotenv
from agents.excel_project_expiry_agent import process_excel_project_expiry

load_dotenv()

PIPELINE_INTERVAL_SECONDS = int(os.getenv("PIPELINE_INTERVAL_SECONDS", "180"))


def run_main_pipeline():
    print("\n🚀 Checking for new PENDING_VALIDATION candidates...")

    from graph import build_validation_graph

    graph = build_validation_graph()

    initial_state = {
        "candidates": [],
        "current_index": 0,
        "validation_results": [],
        "eligible_candidates": [],
        "rejected_candidates": [],
        "eligible_ids": [],
        "rejected_ids": [],
        "ad_results": [],
        "rbac_results": [],
        "mail_results": {},
        "meeting_results": {},
        "error": None,
    }

    final_state = graph.invoke(initial_state)

    if final_state.get("error"):
        print("❌ Main pipeline error:", final_state["error"])
    else:
        print("✅ Main pipeline check completed.")


def run_course_monitor_once():
    print("\n🎥 Checking course progress / certificate / promotion...")

    from cosmos_client import get_container
    from agents.course_monitor_agent import run_single_check
    from agents.removal_agent import process_failed_trainees
    from agents.certificate_agent import process_completed_trainees
    from agents.promotion_agent import promote_completed_trainees
    #from agents.project_allocation_agent import process_project_expiry_termination

    container = get_container()
    results = run_single_check()

    failed_list = results.get("failed", [])
    completed_list = results.get("completed", [])

    if failed_list:
        full_failed = []
        for c in failed_list:
            try:
                full_failed.append(container.read_item(item=c["id"], partition_key=c["id"]))
            except Exception:
                full_failed.append(c)

        process_failed_trainees(full_failed, container)

    if completed_list:
        full_completed = []
        for c in completed_list:
            try:
                full_completed.append(container.read_item(item=c["id"], partition_key=c["id"]))
            except Exception:
                full_completed.append(c)

        process_completed_trainees(full_completed, container)
        promote_completed_trainees(full_completed, container)
    
    #process_project_expiry_termination(container)
    process_excel_project_expiry(container)
    print("✅ Course monitor check completed.")


def start_course_portal():
    print("\n🌐 Starting course portal on http://localhost:8000")

    subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "course_portal.app:app",
            "--host",
            "0.0.0.0",
            "--port",
            "8000",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    time.sleep(3)
    print("✅ Course portal running.")
    print("📊 Admin dashboard: http://localhost:8000/admin")


def main():
    print("\n🤖 Automated Onboarding System Started")
    print(f"⏰ Checking every {PIPELINE_INTERVAL_SECONDS // 60} minute(s)")

    start_course_portal()

    while True:
        try:
            run_main_pipeline()
            run_course_monitor_once()

        except Exception as e:
            print("❌ Automation cycle error:", e)

        print(f"\n⏳ Next full pipeline check in {PIPELINE_INTERVAL_SECONDS // 60} minute(s)...")
        time.sleep(PIPELINE_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()