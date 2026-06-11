from cosmos_client import get_container

container = get_container()
query = "SELECT * FROM c"
items = list(container.query_items(query=query, enable_cross_partition_query=True))

for item in items:
    container.delete_item(item=item["id"], partition_key=item["id"])
    print(f"🗑 Deleted: {item.get('name', item['id'])}")

print(f"✅ Cosmos DB cleared — {len(items)} documents deleted.")