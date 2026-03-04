# Implementation Plan: Serverless Bedrock Chat

## Overview

This implementation plan focuses on creating comprehensive test coverage for the existing serverless bedrock chat system. The system is already deployed and functional, so the primary tasks involve writing unit tests, property-based tests, and infrastructure validation tests to ensure correctness and maintainability.

## Tasks

- [x] 1. Set up testing infrastructure
  - Create test directory structure (tests/unit, tests/property, tests/infrastructure)
  - Install testing dependencies: pytest, hypothesis, pytest-mock, pyyaml
  - Configure pytest with appropriate settings
  - _Requirements: Testing Strategy_

- [x] 2. Implement Lambda handler unit tests
  - [x] 2.1 Write test for default question behavior
    - Test that missing "question" field uses "whats your name?" as default
    - Mock Bedrock client to verify invocation
    - _Requirements: 1.2_
  
  - [x] 2.2 Write test for hibernation mode
    - Test SYSTEM_STATE="HIBERNATED" returns HTTP 503
    - Test response includes error message
    - Mock environment variable
    - _Requirements: 3.1, 3.2, 3.5_
  
  - [x] 2.3 Write test for active mode
    - Test SYSTEM_STATE="ACTIVE" allows normal processing
    - Mock Bedrock client and verify invocation
    - _Requirements: 3.3_
  
  - [x] 2.4 Write test for Bedrock API failure handling
    - Mock Bedrock client to raise exception
    - Verify graceful error handling and appropriate status code
    - _Requirements: 8.2_

- [x] 3. Implement property-based tests for request processing
  - [x] 3.1 Write property test for question forwarding
    - **Property 1: Question forwarding to Bedrock**
    - **Validates: Requirements 1.1**
    - Generate random question strings
    - Mock Bedrock client and verify exact question is passed
    - Run 100+ iterations
  
  - [x] 3.2 Write property test for request parsing
    - **Property 3: Request parsing**
    - **Validates: Requirements 1.4**
    - Generate random JSON bodies with question fields
    - Verify correct extraction of question value
    - Run 100+ iterations
  
  - [x] 3.3 Write property test for invalid JSON handling
    - **Property 7: Invalid JSON handling**
    - **Validates: Requirements 8.1**
    - Generate invalid JSON strings
    - Verify graceful error handling without crashes
    - Run 100+ iterations

- [x] 4. Implement property-based tests for response handling
  - [x] 4.1 Write property test for successful response format
    - **Property 2: Successful response format**
    - **Validates: Requirements 1.3**
    - Generate random Bedrock responses
    - Verify status code 200 and valid JSON body
    - Run 100+ iterations
  
  - [x] 4.2 Write property test for response JSON structure
    - **Property 4: Response JSON structure**
    - **Validates: Requirements 1.5**
    - Generate random responses
    - Verify all responses are valid JSON
    - Run 100+ iterations
  
  - [x] 4.3 Write property test for error status codes
    - **Property 8: Error status codes**
    - **Validates: Requirements 8.5**
    - Generate various error conditions
    - Verify non-200 status codes returned
    - Run 100+ iterations

- [x] 5. Implement property-based tests for Bedrock integration
  - [x] 5.1 Write property test for message role formatting
    - **Property 5: Message role formatting**
    - **Validates: Requirements 2.4**
    - Generate random question strings
    - Verify message structure has role "user"
    - Run 100+ iterations
  
  - [x] 5.2 Write property test for response text extraction
    - **Property 6: Response text extraction**
    - **Validates: Requirements 2.5**
    - Generate random Bedrock response structures
    - Verify successful text extraction from nested object
    - Run 100+ iterations

- [x] 6. Implement configuration validation tests
  - [x] 6.1 Write test for Bedrock model configuration
    - Verify model ID is "anthropic.claude-3-haiku-20240307-v1:0"
    - Verify max tokens is 200
    - _Requirements: 2.1, 2.2_
  
  - [x] 6.2 Write test for Bedrock API method
    - Verify converse API is used (not invoke_model)
    - _Requirements: 2.3_

- [x] 7. Checkpoint - Ensure all application tests pass
  - Run pytest on all unit and property tests
  - Verify 100% pass rate
  - Ask the user if questions arise

- [x] 8. Implement CloudFormation template validation tests
  - [x] 8.1 Write test for foundation.yaml IAM permissions
    - Parse YAML and verify IAM role exists
    - Verify Bedrock invoke permission present
    - Verify CloudWatch Logs write permission present
    - _Requirements: 5.1, 9.1, 9.2_
  
  - [x] 8.2 Write test for ecr.yaml repository definition
    - Parse YAML and verify ECR repository resource exists
    - _Requirements: 5.2_
  
  - [x] 8.3 Write test for github-user.yaml IAM user
    - Parse YAML and verify IAM user exists
    - Verify deployment permissions (ECR, CloudFormation, Lambda, IAM)
    - _Requirements: 5.3, 9.3_
  
  - [x] 8.4 Write test for app.yaml Lambda function
    - Parse YAML and verify Lambda function resource exists
    - Verify container image configuration
    - Verify SYSTEM_STATE environment variable defined
    - _Requirements: 5.4, 5.7_
  
  - [x] 8.5 Write test for resource tagging
    - Parse all templates and verify tag parameters exist
    - Verify tags are applied to resources
    - _Requirements: 5.5_
  
  - [x] 8.6 Write test for cross-stack parameters
    - Parse app.yaml and verify ImageUri parameter exists
    - Verify LambdaRoleArn parameter exists
    - _Requirements: 5.6, 9.4_

- [x] 9. Implement GitHub Actions workflow validation tests
  - [x] 9.1 Write test for workflow trigger configuration
    - Parse deploy.yaml and verify trigger on push to main
    - _Requirements: 6.1_
  
  - [x] 9.2 Write test for AWS authentication
    - Verify workflow uses AWS_ACCESS_KEY_ID secret
    - Verify workflow uses AWS_SECRET_ACCESS_KEY secret
    - _Requirements: 6.2_
  
  - [x] 9.3 Write test for Docker build step
    - Verify workflow includes docker build command
    - Verify correct Dockerfile path
    - _Requirements: 6.3_
  
  - [x] 9.4 Write test for image tagging strategy
    - Verify workflow tags with Git commit SHA
    - _Requirements: 6.4_
  
  - [x] 9.5 Write test for ECR push step
    - Verify workflow includes ECR push command
    - _Requirements: 6.5_
  
  - [x] 9.6 Write test for CloudFormation deployment step
    - Verify workflow includes CloudFormation deploy command
    - Verify new image URI is passed as parameter
    - _Requirements: 6.6_
  
  - [x] 9.7 Write test for required secrets usage
    - Verify workflow references all required secrets
    - Check: AWS credentials, ECR_REPO_URI, LAMBDA_ROLE_ARN, STACK_NAME, tags
    - _Requirements: 6.7_

- [x] 10. Implement bootstrap script validation tests
  - [x] 10.1 Write test for deployment sequence
    - Parse bootstrap.sh and verify stack deployment order
    - Verify foundation deployed before ECR
    - Verify ECR deployed before GitHub user
    - _Requirements: 7.1, 7.5_
  
  - [x] 10.2 Write test for CloudFormation outputs
    - Verify foundation.yaml defines role ARN output
    - Verify ecr.yaml defines repository URI output
    - _Requirements: 7.2_
  
  - [x] 10.3 Write test for IAM capabilities flag
    - Parse bootstrap.sh commands
    - Verify --capabilities CAPABILITY_NAMED_IAM used for IAM stacks
    - _Requirements: 9.5_

- [x] 11. Checkpoint - Ensure all infrastructure tests pass
  - Run pytest on all infrastructure validation tests
  - Verify all CloudFormation templates are valid
  - Verify all workflow configurations are correct
  - Ask the user if questions arise

- [x] 12. Create test documentation
  - Document how to run tests locally
  - Document test coverage expectations
  - Document mocking strategies used
  - Add README in tests/ directory

- [x] 13. Final checkpoint - Complete test suite validation
  - Run full test suite (unit + property + infrastructure)
  - Verify all tests pass
  - Generate coverage report
  - Ensure all 27 properties are tested
  - Ask the user if questions arise

## Notes

- The application code already exists and is functional
- Focus is on comprehensive test coverage to ensure correctness
- Property tests use hypothesis library with 100+ iterations each
- Infrastructure tests use static analysis of YAML and shell scripts
- Each property test references its design document property number
- Unit tests cover specific examples and edge cases
- Checkpoints ensure incremental validation
- All property-based tests are required for complete coverage
