import boto3, os, json

SYSTEM_STATE = os.getenv("SYSTEM_STATE", "ACTIVE")
bedrock = boto3.client("bedrock-runtime")

def handler(event, context):

    if SYSTEM_STATE == "HIBERNATED":
        return {"statusCode": 503, "body": "System parked"}

    body = json.loads(event.get("body", "{}"))
    q = body.get("question", "hello")

    r = bedrock.invoke_model(
        modelId="anthropic.claude-3-sonnet-20240229-v1:0",
        body=json.dumps({
            "messages":[{"role":"user","content":q}],
            "max_tokens":200
        })
    )

    return {"statusCode": 200, "body": r["body"].read().decode()}
