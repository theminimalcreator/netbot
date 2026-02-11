import requests
import os
from dotenv import load_dotenv

# Load key directly
load_dotenv()
API_KEY = os.getenv("DEVTO_API_KEY")
BASE_URL = "https://dev.to/api"

masked_key = f"{API_KEY[:4]}...{API_KEY[-4:]}" if API_KEY else "None"
print(f"🔑 Using API Key: {masked_key}")

if not API_KEY:
    print("❌ Critical: No API Key found.")
    exit(1)

headers = {
    "api-key": API_KEY,
    "Content-Type": "application/json",
    "User-Agent": "NetBot/2.0"
}

def test_endpoint(method, endpoint, json_data=None, params=None):
    url = f"{BASE_URL}{endpoint}"
    print(f"\n📡 Request: {method} {url}")
    if params: print(f"   Params: {params}")
    if json_data: print(f"   Body: {json_data}")
    
    try:
        response = requests.request(method, url, headers=headers, json=json_data, params=params)
        print(f"📊 Response Code: {response.status_code}")
        try:
            print(f"📝 Response Body: {response.json()}")
        except:
            print(f"📝 Response Text: {response.text[:200]}...")
        return response
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

# 1. Test Auth (Get Me)
print("\n--- Test 1: Authentication ---")
data = test_endpoint("GET", "/users/me")
if not data or data.status_code != 200:
    print("❌ Auth failed. Stopping.")
    exit(1)
else:
    print("✅ Auth successful.")

# 2. Get Article (Validate ID)
# Use the article ID from logs: 3162779 (or 3180115)
article_id = 3162779
print(f"\n--- Test 2: Get Article {article_id} ---")
test_endpoint("GET", f"/articles/{article_id}")

# 3. Test Comment (POST)
# Trying various permutations based on research
print(f"\n--- Test 3: Create Comment on {article_id} ---")

# Method A: Query Param `a_id` (Documented in V0 but seemingly widely used)
print("👉 Attempt A: Query Param a_id")
test_endpoint("POST", "/comments", 
              json_data={"comment": {"body_markdown": "Test comment A (automated)"}},
              params={"a_id": article_id})

# Method B: Body payload
print("👉 Attempt B: Body Payload (commentable_id)")
test_endpoint("POST", "/comments", 
              json_data={
                  "comment": {
                      "body_markdown": "Test comment B (automated)",
                      "commentable_id": article_id,
                      "commentable_type": "Article"
                  }
              })

# 4. Test Reaction (POST)
print(f"\n--- Test 4: Create Reaction on {article_id} ---")
test_endpoint("POST", "/reactions", 
              json_data={
                  "reactable_id": article_id,
                  "reactable_type": "Article",
                  "category": "like"
              })
