from cosmos_client import get_container

container = get_container()
query = "SELECT c.id, c.name, c.email, c.status FROM c"
items = list(container.query_items(query=query, enable_cross_partition_query=True))

for item in items:
    print(f"ID: {item['id']} | Name: {item.get('name')} | Email: {item.get('email')} | Status: {item.get('status')}")