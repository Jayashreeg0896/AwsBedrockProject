# Test Suite for Serverless Bedrock Chat

## Overview

This test suite provides comprehensive coverage for the serverless bedrock chat system, including unit tests, property-based tests, and infrastructure validation tests. The test suite validates all 27 correctness properties defined in the design document.

## Setup

Install test dependencies:

```bash
pip install -r requirements-dev.txt
```

## Running Tests

Run all tests:
```bash
pytest
```

Run specific test categories:
```bash
pytest -m unit              # Unit tests only
pytest -m property          # Property-based tests only
pytest -m infrastructure    # Infrastructure tests only
```

Run specific test files:
```bash
pytest tests/unit/test_handler.py
pytest tests/unit/test_configuration.py
pytest tests/property/test_request_properties.py
pytest tests/property/test_response_properties.py
pytest tests/property/test_bedrock_properties.py
pytest tests/infrastructure/test_cloudformation.py
pytest tests/infrastructure/test_pipeline.py
```

Run with verbose output:
```bash
pytest -v
```

Generate coverage report:
```bash
pytest --cov=lambda --cov-report=html
```

## Test Structure

```
tests/
├── unit/                   # Unit tests for Lambda components
│   ├── test_handler.py         # Lambda handler behavior tests
│   └── test_configuration.py   # Bedrock configuration tests
├── property/               # Property-based tests using hypothesis
│   ├── test_request_properties.py    # Properties 1, 3, 7
│   ├── test_response_properties.py   # Properties 2, 4, 8
│   └── test_bedrock_properties.py    # Properties 5, 6
└── infrastructure/         # Infrastructure validation tests
    ├── test_cloudformation.py        # Properties 12-17, 26
    └── test_pipeline.py              # Properties 18-25, 27
```

## Test Coverage

### Unit Tests (tests/unit/)
- **test_handler.py**: Lambda handler behavior
  - Default question when field is missing
  - Hibernation mode returns HTTP 503
  - Active mode processes requests
  - Bedrock API failure handling
  
- **test_configuration.py**: Bedrock configuration
  - Model ID is Claude 3 Haiku
  - Max tokens is 200
  - Uses converse API

### Property-Based Tests (tests/property/)
Each property test runs 100+ iterations with randomly generated inputs:

- **test_request_properties.py**:
  - Property 1: Question forwarding to Bedrock
  - Property 3: Request parsing from JSON
  - Property 7: Invalid JSON handling
  
- **test_response_properties.py**:
  - Property 2: Successful response format (200 + valid JSON)
  - Property 4: Response JSON structure
  - Property 8: Error status codes
  
- **test_bedrock_properties.py**:
  - Property 5: Message role formatting (user role)
  - Property 6: Response text extraction

### Infrastructure Tests (tests/infrastructure/)
Static analysis of configuration files:

- **test_cloudformation.py**:
  - Foundation template: IAM roles and permissions
  - ECR template: Repository definition
  - GitHub user template: Deployer permissions
  - App template: Lambda function configuration
  - Resource tagging validation
  - Cross-stack parameter validation
  
- **test_pipeline.py**:
  - GitHub Actions workflow trigger
  - AWS authentication configuration
  - Docker build/tag/push steps
  - CloudFormation deployment
  - Required secrets validation
  - Bootstrap script deployment sequence
  - IAM capabilities flags

## Mocking Strategy

### Bedrock Client Mocking
- Mock `boto3.client('bedrock-runtime')` for all unit and property tests
- Use `unittest.mock.patch` to intercept Bedrock calls
- Mock both successful responses and error conditions

### Environment Variable Mocking
- Mock `os.environ` for hibernation state tests
- Test both "ACTIVE" and "HIBERNATED" states
- Use `@patch.dict(os.environ, {...})` decorator

### CloudFormation Template Testing
- Use `pyyaml` to parse and validate templates
- Assert on specific resource properties
- No mocking required - static analysis only

## Property-Based Testing

Property-based tests use the Hypothesis library to generate random test inputs and verify that properties hold across all inputs. Each property test:

1. Generates 100+ random test cases
2. Verifies the property holds for all cases
3. Reports any counterexamples found
4. References the design document property number

Example property test structure:
```python
@given(question=st.text(min_size=1, max_size=500))
@settings(max_examples=100)
def test_property(self, question):
    # Test that property holds for any question
    ...
```

## Troubleshooting

### Import Errors
If you see import errors for `lambda.handler`, ensure you're running pytest from the project root directory.

### Disk Space Issues
If pip install fails with "No space left on device", free up disk space before installing dependencies.

### Test Failures
- Check that all CloudFormation templates are in `infra/` directory
- Verify GitHub Actions workflow is in `.github/workflows/deploy.yaml`
- Ensure bootstrap script is in project root as `bootstrap.sh`

## Continuous Integration

These tests are designed to run in CI/CD pipelines. Add to your GitHub Actions workflow:

```yaml
- name: Install test dependencies
  run: pip install -r requirements-dev.txt

- name: Run tests
  run: pytest -v

- name: Generate coverage report
  run: pytest --cov=lambda --cov-report=xml
```

## Coverage Goals

- Unit tests: 100% coverage of Lambda handler code
- Property tests: All 8 application logic properties validated
- Infrastructure tests: All 19 infrastructure/configuration properties validated
- Total: 27 correctness properties verified
