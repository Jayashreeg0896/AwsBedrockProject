---
inclusion: always
---

# Technology Stack

## Core Technologies
- **Runtime**: Python 3.12
- **Platform**: AWS Lambda (containerized)
- **AI Model**: AWS Bedrock - Claude 3 Sonnet (anthropic.claude-3-sonnet-20240229-v1:0)
- **Infrastructure**: AWS CloudFormation
- **Container**: Docker with AWS Lambda base image

## Key AWS Services
- Lambda (compute)
- ECR (container registry)
- IAM (permissions)
- Bedrock (AI inference)
- CloudWatch Logs

## Dependencies
- `boto3` - AWS SDK for Python

## Common Commands

### Bootstrap Infrastructure
```bash
# Initial setup (foundation, ECR, GitHub deployer user)
./bootstrap.sh

# After bootstrap, configure GitHub secrets:
# - AWS_ACCESS_KEY_ID
# - AWS_SECRET_ACCESS_KEY
# - AWS_REGION
# - ECR_REPO_URI
# - LAMBDA_ROLE_ARN
# - STACK_NAME
# - PROJECT
# - OWNER
# - ENV
```

### Docker
```bash
# Build Lambda container
docker build -f lambda/Dockerfile.dockerfile -t bedrock-agent lambda/

# Tag for ECR
docker tag bedrock-agent:latest <account-id>.dkr.ecr.<region>.amazonaws.com/bedrock-agent:latest

# Push to ECR
docker push <account-id>.dkr.ecr.<region>.amazonaws.com/bedrock-agent:latest
```

### CloudFormation Deployment
```bash
# Deploy foundation (IAM roles)
aws cloudformation deploy --template-file infra/foundation.yaml --stack-name bedrock-foundation --capabilities CAPABILITY_NAMED_IAM --parameter-overrides ProjectTag=<project> OwnerTag=<owner> EnvTag=<env>

# Deploy ECR repository
aws cloudformation deploy --template-file infra/ecr.yaml --stack-name bedrock-ecr

# Deploy GitHub deployer user
aws cloudformation deploy --template-file infra/github-user.yaml --stack-name github-deployer --capabilities CAPABILITY_NAMED_IAM

# Deploy application
aws cloudformation deploy --template-file infra/app.yaml --stack-name bedrock-app --parameter-overrides ImageUri=<ecr-uri> LambdaRoleArn=<role-arn> ProjectTag=<project> OwnerTag=<owner> EnvTag=<env> SystemState=ACTIVE
```

## Configuration

### Lambda Environment Variables
- `SYSTEM_STATE`: Controls hibernation mode (ACTIVE/HIBERNATED)
- Configured via CloudFormation parameters

### GitHub Actions Secrets
Required for CI/CD pipeline:
- `AWS_ACCESS_KEY_ID` - GitHub deployer user access key
- `AWS_SECRET_ACCESS_KEY` - GitHub deployer user secret key
- `AWS_REGION` - AWS region for deployment
- `ECR_REPO_URI` - Full ECR repository URI
- `LAMBDA_ROLE_ARN` - ARN of Lambda execution role (from foundation stack)
- `STACK_NAME` - CloudFormation stack name for app (e.g., bedrock-app)
- `PROJECT` - Project tag value
- `OWNER` - Owner tag value
- `ENV` - Environment tag value (dev/prod)
