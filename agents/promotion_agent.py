from datetime import datetime, timezone
from cosmos_client import update_candidate_status



def promote_completed_trainees(completed_candidates, container):
    print("\n🚀 Promoting certified users from Learner → Contributor...")

    promoted = 0

    for candidate in completed_candidates:
        candidate_id = candidate["id"]
        name = candidate.get("name")
        email = candidate.get("email")

        if not candidate.get("certificate_sent"):
            print(f"⚠ Skipping {name}: certificate not sent yet.")
            continue

        if candidate.get("rbac_role") == "Contributor":
            print(f"⚠ Skipping {name}: already Contributor.")
            continue

        update_candidate_status(
            container=container,
            candidate_id=candidate_id,
            new_status="EMPLOYEE",
            extra_fields={
                "rbac_role": "Contributor",
                "rbac_status": "PROMOTED_TO_CONTRIBUTOR",
                "promotion_status": "PROMOTED",
                "promoted_at": datetime.now(timezone.utc).isoformat()
            }
        )

        subject = "Congratulations! Your Access Has Been Upgraded"

        body = f"""
Hi {name},

Congratulations on successfully completing your onboarding course.

Your certificate has been generated and sent to your registered email.

Your access role has now been upgraded:

Previous Role: Learner
New Role: Contributor

You can now access contributor-level resources in the system.

Regards,
Onboarding Team
"""

        send_email(
            to_email=email,
            subject=subject,
            body=body
        )

        print(f"✔ Promoted {name} → Contributor and sent mail.")
        promoted += 1

    print(f"✅ Total promoted: {promoted}")