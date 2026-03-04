import boto3, os, json

SYSTEM_STATE = os.getenv("SYSTEM_STATE", "ACTIVE")
bedrock = boto3.client("bedrock-runtime")

def handler(event, context):

    if SYSTEM_STATE == "HIBERNATED":
        return {"statusCode": 503, "body": "System parked"}

    body = json.loads(event.get("body", "{}"))
    q = body.get("question", "hello")

    response = bedrock.converse(
        modelId="anthropic.claude-3-haiku-20240307-v1:0",
        messages=[
            {
                "role": "user",
                "content": [{"text": q}]
            }
        ],
        inferenceConfig={"maxTokens": 200}
    )

    result = response["output"]["message"]["content"][0]["text"]

    return {
        "statusCode": 200,
        "body": json.dumps({"response": result})
    }