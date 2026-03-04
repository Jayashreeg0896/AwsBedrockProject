---
inclusion: always
---

# Project Structure

## Directory Layout

```
/
├── .github/
│   └── workflows/
│       └── deploy.yaml  # GitHub Actions CI/CD pipeline
│
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
├── tests/               # Comprehensive test suite
│   ├── unit/           # Unit tests for Lambda components
│   │   ├── test_handler.py
│   │   └── test_configuration.py
│   ├── property/       # Property-based tests (100+ iterations each)
│   │   ├── test_request_properties.py
│   │   ├── test_response_properties.py
│   │   └── test_bedrock_properties.py
│   ├── infrastructure/ # Infrastructure validation tests
│   │   ├── test_cloudformation.py
│   │   ├── test_pipeline.py
│   │   └── cfn_yaml_loader.py
│   └── README.md       # Test documentation
│
├── bootstrap.sh         # Initial infrastructure setup script
├── requirements-dev.txt # Test dependencies
└── pytest.ini          # Pytest configuration
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
- Automated deployment on push to `main` branch
- Pipeline: checkout → build Docker image → push to ECR → deploy via CloudFormation
- Images tagged with Git commit SHA for traceability

### GitHub Actions Workflow
- Trigger: Push to `main` branch
- Steps: AWS auth → ECR login → Docker build/tag/push → CloudFormation deploy
- Required secrets: AWS credentials, ECR URI, Lambda role ARN, stack name, tags

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

## Testing

### Test Coverage
- **47 tests** validating all 27 correctness properties
- **Unit tests**: Lambda handler behavior, configuration validation
- **Property-based tests**: 8 properties with 100+ iterations each (800+ test cases)
- **Infrastructure tests**: CloudFormation templates, CI/CD pipeline, bootstrap script

### Running Tests
```bash
# Install test dependencies
pip install -r requirements-dev.txt

# Run all tests
python -m pytest -v

# Run specific test categories
python -m pytest -m unit              # Unit tests only
python -m pytest -m property          # Property-based tests only
python -m pytest -m infrastructure    # Infrastructure tests only
```

### Test Structure
- `tests/unit/` - Unit tests for Lambda components
- `tests/property/` - Property-based tests using Hypothesis
- `tests/infrastructure/` - CloudFormation and pipeline validation
- `tests/README.md` - Comprehensive testing documentation
