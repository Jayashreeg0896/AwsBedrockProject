---
inclusion: always
---

# Product Overview

Serverless AI chat service powered by AWS Bedrock (Claude 3 Sonnet). The system provides a Lambda-based API endpoint that processes chat questions and returns AI-generated responses. Includes a hibernation mode controlled via environment variable for cost management.

## Deployment Model
- Fully automated CI/CD via GitHub Actions
- Containerized Lambda deployment with ECR
- Infrastructure as Code using CloudFormation
- Git commit SHA-based image tagging for version tracking
