---
inclusion: always
---

# Project Structure

## Directory Layout

```
/
├── lambda/              # Lambda function code
│   ├── handler.py       # Main Lambda handler with Bedrock integration
│   └── Dockerfile.dockerfile  # Container definition for Lambda
│
├── infra/               # CloudFormation infrastructure templates
│   ├── foundation.yaml  # IAM roles and policies for Lambda
│   ├── ecr.yaml        # Container registry
│   ├── github-user.yaml # IAM user for GitHub Actions deployment
│   └── app.yaml        # Lambda function deployment
│
└── bootstrap.sh         # Initial infrastructure setup script
```

## Architecture Patterns

### Infrastructure as Code
- All AWS resources defined in CloudFormation YAML templates
- Multi-tier deployment: foundation → ECR → GitHub user → application
- Parameters used for cross-stack references and configuration
- Bootstrap script automates initial infrastructure setup

### CI/CD
- Dedicated IAM user (`github-bedrock-deployer`) for GitHub Actions
- Permissions for ECR push, CloudFormation deployment, Lambda updates, and IAM role passing

### Lambda Handler
- Single handler function in `lambda/handler.py`
- Event-driven with JSON body parsing
- Synchronous Bedrock model invocation
- Environment-based feature flags (hibernation mode)

### Containerized Lambda
- Uses AWS-provided Python 3.12 Lambda base image
- Minimal container with only handler code
- No requirements.txt (boto3 included in base image)

## Conventions

### Naming
- CloudFormation stacks: `bedrock-<component>` pattern (bedrock-foundation, bedrock-ecr, bedrock-app)
- GitHub deployer stack: `github-deployer`
- ECR repository: `bedrock-agent`
- Lambda function: `ChatFunction`
- IAM user: `github-bedrock-deployer`

### Tagging
- All resources tagged with: Project, Owner, Environment
- Tags passed as CloudFormation parameters

### Error Handling
- HTTP 503 returned when system is hibernated
- HTTP 200 for successful responses
