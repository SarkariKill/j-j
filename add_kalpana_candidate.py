from datetime import datetime, timezone
from cosmos_client import get_container

container = get_container()

kalpana = {
    "id": "candidate_005",
    "name": "Kalpana Raj",
    "email": "adi.sarkar6347@gmail.com",
    "phone": "+91-9876543210",
    "skillset": [
        "Python",
        "Azure",
        "REST APIs",
        "SQL"
    ],
    "experience_years": 2,
    "applied_role": "Software Engineer",
    "company_required_skills": [
        "Python",
        "Azure",
        "Docker"
    ],
    "status": "PENDING_VALIDATION",
    "servicenow_profile_id": "SN-MOCK-005",
    "created_at": datetime.now(timezone.utc).isoformat()
}

try:
    existing = container.read_item(
        item="candidate_005",
        partition_key="candidate_005"
    )

    # Replace old Kalpana with clean fresh candidate
    container.replace_item(
        item="candidate_005",
        body=kalpana
    )

    print("✔ Existing Kalpana candidate replaced with clean fresh record.")

except Exception:
    container.create_item(body=kalpana)
    print("✔ New Kalpana candidate inserted.")

print("✅ Kalpana is now ready for automated pipeline.")
print("Status: PENDING_VALIDATION")