# ============================================================
#   cosmos_client.py — Azure Cosmos DB Connection & Helpers
# ============================================================

import os
from azure.cosmos import CosmosClient, PartitionKey, exceptions
from dotenv import load_dotenv
from colorama import Fore, Style

load_dotenv()

# ── Cosmos DB Config ─────────────────────────────────────────
COSMOS_ENDPOINT      = os.getenv("COSMOS_ENDPOINT")
COSMOS_KEY           = os.getenv("COSMOS_KEY")
COSMOS_DATABASE_NAME = os.getenv("COSMOS_DATABASE_NAME", "OnboardingDB")
COSMOS_CONTAINER     = os.getenv("COSMOS_CONTAINER_NAME", "Candidates")


def get_container():
    """
    Returns the Cosmos DB container client.
    Creates database and container if they don't exist yet.
    """
    client    = CosmosClient(COSMOS_ENDPOINT, credential=COSMOS_KEY)
    database  = client.create_database_if_not_exists(id=COSMOS_DATABASE_NAME)
    container = database.create_container_if_not_exists(
        id=COSMOS_CONTAINER,
        partition_key=PartitionKey(path="/id"),
        offer_throughput=400          # free-tier friendly (400 RU/s)
    )
    return container


def fetch_pending_candidates(container):
    """
    Fetches all candidates whose status is PENDING_VALIDATION.
    Returns a list of candidate dicts.
    """
    query = "SELECT * FROM c WHERE c.status = 'PENDING_VALIDATION'"
    items = list(container.query_items(query=query, enable_cross_partition_query=True))
    return items


def fetch_all_candidates(container):
    """
    Fetches every candidate regardless of status (useful for testing).
    """
    query = "SELECT * FROM c"
    items = list(container.query_items(query=query, enable_cross_partition_query=True))
    return items


def update_candidate_status(container, candidate_id: str, new_status: str, extra_fields: dict = None):
    """
    Updates a candidate's status field in Cosmos DB.
    Optionally merges in extra_fields (e.g. validation_result, missing_skills).

    Args:
        container     : Cosmos DB container client
        candidate_id  : document 'id' field value
        new_status    : one of ELIGIBLE / REJECTED / PENDING_VALIDATION
        extra_fields  : additional key-value pairs to patch into the document
    """
    try:
        # Read the existing item first (required for replace)
        item = container.read_item(item=candidate_id, partition_key=candidate_id)

        # Apply updates
        item["status"] = new_status
        if extra_fields:
            item.update(extra_fields)

        # Write back
        container.replace_item(item=candidate_id, body=item)
        print(f"{Fore.GREEN}✔ Updated [{candidate_id}] → status: {new_status}{Style.RESET_ALL}")
    except exceptions.CosmosResourceNotFoundError:
        print(f"{Fore.RED}✘ Candidate [{candidate_id}] not found in Cosmos DB.{Style.RESET_ALL}")


def insert_sample_candidates(container):
    """
    Inserts mock candidate documents for testing Step 3.
    Safe to run multiple times — skips existing IDs.
    """
    samples = [
        {
            "id": "candidate_001",
            "name": "Rahul Sharma",
            "email": "adi.sarkar2004@gmail.com",
            "phone": "+91-9876543210",
            "skillset": ["Python", "Azure", "REST APIs", "SQL"],
            "experience_years": 2,
            "applied_role": "Software Engineer",
            "company_required_skills": ["Python", "Azure", "Docker"],
            "status": "PENDING_VALIDATION",
            "servicenow_profile_id": "SN-MOCK-001",
            "created_at": "2026-05-24T10:00:00Z"
        },
        {
            "id": "candidate_002",
            "name": "Priya Verma",
            "email": "aditya.sarkar1803@gmail.com",
            "phone": "+91-9123456789",
            "skillset": ["Java", "Spring Boot", "MySQL"],
            "experience_years": 1,
            "applied_role": "Backend Developer",
            "company_required_skills": ["Python", "Azure", "Docker", "Kubernetes"],
            "status": "PENDING_VALIDATION",
            "servicenow_profile_id": "SN-MOCK-002",
            "created_at": "2026-05-24T10:05:00Z"
        },
        {
            "id": "candidate_003",
            "name": "Arjun Das",
            "email": "aditya.sarkar.jobhunt.2004@gmail.com",
            "phone": "+91-9988776655",
            "skillset": ["Python", "Machine Learning", "TensorFlow", "Azure", "Docker", "Kubernetes"],
            "experience_years": 3,
            "applied_role": "ML Engineer",
            "company_required_skills": ["Python", "Azure", "Docker", "Kubernetes"],
            "status": "PENDING_VALIDATION",
            "servicenow_profile_id": "SN-MOCK-003",
            "created_at": "2026-05-24T10:10:00Z"
        },
        {
            "id": "candidate_004",
            "name": "Sneha Patel",
            "email": "pookieteddy2004@gmail.com",
            "phone": "+91-9001122334",
            "skillset": ["ReactJS", "Node.js", "MongoDB", "AWS"],
            "experience_years": 2,
            "applied_role": "Full Stack Developer",
            "company_required_skills": ["React", "NodeJS", "MongoDB"],
            "status": "PENDING_VALIDATION",
            "servicenow_profile_id": "SN-MOCK-004",
            "created_at": "2026-05-24T10:15:00Z"
        },
    ]

    print(f"\n{Fore.CYAN}📦 Inserting sample candidates into Cosmos DB...{Style.RESET_ALL}")
    for doc in samples:
        try:
            container.create_item(body=doc)
            print(f"  {Fore.GREEN}✔ Inserted: {doc['name']} ({doc['id']}){Style.RESET_ALL}")
        except exceptions.CosmosResourceExistsError:
            print(f"  {Fore.YELLOW}⚠ Already exists (skipped): {doc['id']}{Style.RESET_ALL}")

    print(f"{Fore.CYAN}✅ Sample data ready.\n{Style.RESET_ALL}")