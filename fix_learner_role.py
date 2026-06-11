# save as fix_learner_role.py
import requests, os, uuid
from dotenv import load_dotenv
load_dotenv()

TENANT_ID       = os.getenv("TENANT_ID")
CLIENT_ID       = os.getenv("CLIENT_ID")
CLIENT_SECRET   = os.getenv("CLIENT_SECRET")
SUBSCRIPTION_ID = os.getenv("AZURE_SUBSCRIPTION_ID")

url  = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
data = {
    "grant_type"   : "client_credentials",
    "client_id"    : CLIENT_ID,
    "client_secret": CLIENT_SECRET,
    "scope"        : "https://management.azure.com/.default",
}
token = requests.post(url, data=data).json()["access_token"]
headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

# List all custom roles and find Learner
url = f"https://management.azure.com/subscriptions/{SUBSCRIPTION_ID}/providers/Microsoft.Authorization/roleDefinitions?api-version=2022-04-01&$filter=type eq 'CustomRole'"
r   = requests.get(url, headers=headers)

for role in r.json().get("value", []):
    name = role["properties"]["roleName"]
    rid  = role["name"]
    print(f"Found custom role: '{name}' → ID: {rid}")