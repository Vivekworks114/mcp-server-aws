#!/usr/bin/env python3
"""
Test script for Bedrock AgentCore Runtime
Usage: python test_agent.py [AGENT_RUNTIME_ARN] [COMPANY_ID] [PROMPT]
"""
import boto3
import json
import uuid
import sys
import os

# Configuration - can be overridden via environment variables or command line
AGENT_RUNTIME_ARN = os.getenv(
    "AGENT_RUNTIME_ARN",
    "arn:aws:bedrock-agentcore:us-east-1:876610982461:runtime/pk_agent_001c9c14-qeACVuHrkp"
)
COMPANY_ID = os.getenv(
    "COMPANY_ID",
    "001c9c14-6c34-475b-9a61-8b8a08b59758"  # Updated to match deployed agent
)
REGION = os.getenv("AWS_REGION", "us-east-1")
PROMPT = "What are your business hours?"

# Override with command line arguments if provided
if len(sys.argv) > 1:
    AGENT_RUNTIME_ARN = sys.argv[1]
if len(sys.argv) > 2:
    COMPANY_ID = sys.argv[2]
if len(sys.argv) > 3:
    PROMPT = sys.argv[3]

print(f"Testing Agent Runtime:")
print(f"  ARN: {AGENT_RUNTIME_ARN}")
print(f"  Company ID: {COMPANY_ID}")
print(f"  Prompt: {PROMPT}")
print(f"  Region: {REGION}")
print()

client = boto3.client("bedrock-agentcore", region_name=REGION)
session_id = f"test-{uuid.uuid4().hex}"[:33]

payload = json.dumps({
    "prompt": PROMPT,
    "company_id": COMPANY_ID
})

try:
    print("Invoking agent runtime...")
    resp = client.invoke_agent_runtime(
        agentRuntimeArn=AGENT_RUNTIME_ARN,
        runtimeSessionId=session_id,
        payload=payload,
        qualifier="DEFAULT",
    )

    body = resp["response"].read()
    response_data = json.loads(body.decode())
    
    print("\n" + "="*60)
    print("RESPONSE:")
    print("="*60)
    print(json.dumps(response_data, indent=2))
    
    # Extract and print the text response if available
    if "output" in response_data:
        output = response_data["output"]
        if "message" in output:
            message_obj = output["message"]
            if "content" in message_obj:
                print("\n" + "="*60)
                print("AGENT RESPONSE TEXT:")
                print("="*60)
                for content_item in message_obj["content"]:
                    if "text" in content_item:
                        print(content_item["text"])
    elif "result" in response_data:
        print("\n" + "="*60)
        print("AGENT RESPONSE:")
        print("="*60)
        print(response_data["result"])
        
except Exception as e:
    print(f"\nERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)