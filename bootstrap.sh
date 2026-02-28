#!/bin/bash
set -e

PROJECT="AwsBedrockProject"
OWNER="Jayashree"
ENV="dev"

echo "Deploying foundation..."
aws cloudformation deploy \
  --stack-name bedrock-foundation \
  --template-file infra/foundation.yaml \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides \
    ProjectTag=$PROJECT OwnerTag=$OWNER EnvTag=$ENV

echo "Deploying ECR..."
aws cloudformation deploy \
  --stack-name bedrock-ecr \
  --template-file infra/ecr.yaml

echo "Deploying GitHub user..."
aws cloudformation deploy \
  --stack-name github-deployer \
  --template-file infra/github-user.yaml \
  --capabilities CAPABILITY_NAMED_IAM

echo "Done."
