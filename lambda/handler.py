import boto3, os, json

SYSTEM_STATE = os.getenv("SYSTEM_STATE", "ACTIVE")
bedrock = boto3.client("bedrock-runtime")

def handler(event, context):

    if SYSTEM_STATE == "HIBERNATED":
        return {"statusCode": 503, "body": "System parked"}

    body = json.loads(event.get("body", "{}"))
    q = body.get("question", "hello")

    response = bedrock.invoke_model(
        modelId="anthropic.claude-3-haiku-20240307-v1:0",
        contentType="application/json",
        accept="application/json",
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 200,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": q}
                    ]
                }
            ]
        })
    )

    result = json.loads(response["body"].read())

    return {
        "statusCode": 200,
        "body": json.dumps(result)
    }