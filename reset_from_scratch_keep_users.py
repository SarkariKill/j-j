from cosmos_client import get_container

container = get_container()

RESET_FIELDS = [
    "azure_ad_object_id",
    "upn",
    "ad_status",
    "rbac_status",
    "rbac_role",
    "meeting_link",
    "meeting_id",
    "meeting_invited_at",
    "course_link",
    "course_status",
    "course_start_time",
    "course_completed_at",
    "watch_percentage",
    "watched_seconds",
    "certificate_sent",
    "certificate_sent_at",
    "promoted_at",
    "promotion_status",
    "employee_status",
]

items = list(container.query_items(
    query="SELECT * FROM c",
    enable_cross_partition_query=True
))

for item in items:
    item["status"] = "PENDING_VALIDATION"

    for field in RESET_FIELDS:
        item.pop(field, None)

    # item["project_allocation"] = {
    #     "project_name": "Johnson & Johnson IAM Project",
    #     "project_start_date": "2026-06-01",
    #     "project_end_date": "2026-06-10",
    #     "future_allocation": False,
        
    #     # "future_allocation": true,
    #     # "future_project_name": "Next Project Name",
    #     "future_project_name": None
    # }

    container.replace_item(item=item["id"], body=item)

    print(f"✔ Reset from scratch: {item['name']} ({item['email']})")

print("✅ Done. Users kept in Cosmos DB, but flow/course/certificate/project allocation data reset.")