import os
import sys
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import db

def test_llm_logging():
    print("🧪 Testing LLM Logging...")
    
    # Mock data
    provider = "test_provider"
    model = "test-model-001"
    user_prompt = "Hello, world!"
    system_prompt = "You are a test bot."
    response = "{\"text\": \"Hello! This is a test response.\"}"
    parameters = {"temperature": 0.7}
    metrics = {
        "input_tokens": 10,
        "output_tokens": 5,
        "total_cost": 0.0001
    }
    metadata = {
        "test_run": True,
        "environment": "dev"
    }

    print("📝 Logging interaction...")
    log_id = db.log_llm_interaction(
        provider=provider,
        model=model,
        user_prompt=user_prompt,
        response=response,
        system_prompt=system_prompt,
        parameters=parameters,
        metrics=metrics,
        metadata=metadata
    )

    if log_id:
        print(f"✅ Logged successfully! ID: {log_id}")
        
        # Verify by fetching
        print("🔍 Verifying insertion...")
        try:
            res = db.client.table("llm_logs").select("*").eq("id", log_id).execute()
            if res.data and res.data[0]["id"] == log_id:
                print("✅ Internal verification passed: Record found in DB.")
                print(f"   -> Provider: {res.data[0]['provider']}")
                print(f"   -> Prompt: {res.data[0]['user_prompt']}")
                print(f"   -> Response: {res.data[0]['response']}")
            else:
                print("❌ Record not found after insertion!")
        except Exception as e:
            print(f"❌ Verification failed: {e}")

    else:
        print("❌ Failed to log interaction.")

if __name__ == "__main__":
    load_dotenv()
    test_llm_logging()
