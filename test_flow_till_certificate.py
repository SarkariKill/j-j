# test_flow_till_certificate.py

import datetime
from cosmos_client import get_container, fetch_all_candidates, update_candidate_status
from graph import build_validation_graph
from agents.certificate_agent import process_completed_trainees


def print_all_status(title):
    container = get_container()
    candidates = fetch_all_candidates(container)

    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)

    for c in candidates:
        print(
            f"ID: {c['id']} | "
            f"Name: {c.get('name')} | "
            f"Email: {c.get('email')} | "
            f"Status: {c.get('status')} | "
            f"Course: {c.get('course_status')} | "
            f"Certificate: {c.get('certificate_sent')}"
        )


def run_main_pipeline():
    print("\n🚀 Running flow from validation till course invitation...")

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
        print("❌ Pipeline failed:", final_state["error"])
        return False

    print("✅ Main pipeline completed.")
    return True


def simulate_course_completion():
    print("\n🎓 Simulating course completion for invited/active trainees...")

    container = get_container()

    query = """
    SELECT * FROM c 
    WHERE c.status IN ('MEETING_INVITED', 'RBAC_ASSIGNED', 'IN_TRAINING')
    """

    trainees = list(container.query_items(
        query=query,
        enable_cross_partition_query=True
    ))

    if not trainees:
        print("⚠ No active trainees found for course completion.")
        return []

    completed = []

    for trainee in trainees:
        cid = trainee["id"]

        update_candidate_status(
            container=container,
            candidate_id=cid,
            new_status="COURSE_COMPLETED",
            extra_fields={
                "course_status": "COMPLETED",
                "watch_percentage": 100,
                "course_completed_at": datetime.datetime.utcnow().isoformat() + "Z",
                "certificate_sent": False,
            }
        )

        updated_item = container.read_item(item=cid, partition_key=cid)
        completed.append(updated_item)

    print(f"✅ Marked {len(completed)} trainee(s) as COURSE_COMPLETED.")
    return completed


def generate_certificates(completed_candidates):
    print("\n📜 Generating and sending certificates...")

    container = get_container()

    if not completed_candidates:
        print("⚠ No completed candidates found.")
        return

    process_completed_trainees(completed_candidates, container)


def main():
    print_all_status("BEFORE TEST")

    success = run_main_pipeline()
    if not success:
        return

    print_all_status("AFTER MAIN PIPELINE")

    completed_candidates = simulate_course_completion()

    print_all_status("AFTER COURSE COMPLETION SIMULATION")

    generate_certificates(completed_candidates)

    print_all_status("FINAL STATUS AFTER CERTIFICATE GENERATION")

    print("\n✅ Test completed till certificate generation.")


if __name__ == "__main__":
    main()