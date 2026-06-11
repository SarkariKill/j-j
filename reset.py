from cosmos_client import get_container

container = get_container()
query = "SELECT * FROM c"
items = list(container.query_items(query=query, enable_cross_partition_query=True))

for item in items:
    item["status"] = "PENDING_VALIDATION"
    container.replace_item(item=item["id"], body=item)
    print(f"✔ Reset: {item['name']} ({item['email']}) → PENDING_VALIDATION")

print("✅ All candidates reset — emails untouched.")