# Requirements Document

## Introduction

This document specifies the requirements for a serverless RAG-based AI chat service powered by AWS Bedrock. The system provides a Lambda-based API endpoint that processes user questions using retrieval-augmented generation (RAG) — retrieving relevant context from uploaded PDF documents before generating responses with Claude 3 Haiku. A second Lambda handles asynchronous PDF ingestion, converting documents into searchable vector embeddings stored in S3 Vectors. The system includes hibernation mode for cost management, automated CI/CD deployment, and budget alerting.

## Glossary

- **Chat_Service**: The AWS Lambda function (`lambda/chat/handler.py`) that processes chat requests and returns AI-generated responses
- **Ingestion_Service**: The AWS Lambda function (`lambda/ingestion/ingestion.py`) that processes PDF uploads and stores vector embeddings
- **Bedrock_Client**: AWS Bedrock service integration used for both AI inference (Claude) and text embedding (Titan)
- **RAG_Pipeline**: The retrieval-augmented generation flow: embed question → query S3 Vectors → inject context → generate response
- **Vector_Store**: AWS S3 Vectors service storing document chunk embeddings in the `aws-docs-index` index
- **Hibernation_Controller**: Component that manages system availability based on the `SYSTEM_STATE` environment variable
- **Deployment_Pipeline**: GitHub Actions workflow that automates infrastructure and code deployment
- **Container_Registry**: AWS ECR repository storing Lambda container images
- **Infrastructure_Stack**: CloudFormation templates defining all AWS resources

---

## Requirements

### Requirement 1: Chat Request Processing

**User Story:** As an API consumer, I want to send chat questions to the service and receive AI-generated responses informed by my uploaded documents.

#### Acceptance Criteria

1. WHEN a request is received with a `"question"` field, THE Chat_Service SHALL invoke the RAG_Pipeline with that question
2. WHEN a request is received without a `"question"` field, THE Chat_Service SHALL use `"hello"` as the default question
3. WHEN the Bedrock_Client returns a response, THE Chat_Service SHALL return HTTP 200 with the AI-generated text and source document references in JSON format
4. THE Chat_Service SHALL parse the request body as JSON and extract the `question` field
5. THE Chat_Service SHALL accept an optional `history` array of prior conversation turns and include them in the Bedrock request
6. THE Chat_Service SHALL return a JSON body containing both a `response` string and a `sources` array

### Requirement 2: RAG Retrieval

**User Story:** As an API consumer, I want responses grounded in my uploaded documents so that answers are accurate and relevant to my content.

#### Acceptance Criteria

1. WHEN processing a question, THE RAG_Pipeline SHALL embed the question using the Titan embedding model (`amazon.titan-embed-text-v2:0`)
2. THE RAG_Pipeline SHALL query the S3 Vectors index `aws-docs-index` with the question embedding, retrieving the top 3 most similar chunks
3. WHEN matching vectors are found, THE RAG_Pipeline SHALL extract the `text` and `source` fields from vector metadata to build context
4. WHEN matching vectors are found, THE Chat_Service SHALL inject the retrieved context into the system prompt for Bedrock inference
5. WHEN no matching vectors are found, THE Chat_Service SHALL fall back to a generic AWS assistant system prompt without context
6. THE Chat_Service SHALL include the source document keys in the response `sources` array

### Requirement 3: AI Model Integration

**User Story:** As a system operator, I want the service to use AWS Bedrock Claude 3 Haiku for cost-efficient, high-quality AI responses.

#### Acceptance Criteria

1. THE Bedrock_Client SHALL use model ID `anthropic.claude-3-haiku-20240307-v1:0` for chat inference
2. THE Bedrock_Client SHALL configure a maximum token limit of 1024 for responses
3. WHEN invoking the model, THE Bedrock_Client SHALL use the `converse` API
4. THE Bedrock_Client SHALL format user questions as messages with role `"user"` and content as a text array
5. THE Bedrock_Client SHALL extract response text from `response["output"]["message"]["content"][0]["text"]`
6. WHEN conversation history is provided, THE Bedrock_Client SHALL prepend prior turns to the messages array before the current question

### Requirement 4: PDF Upload Support

**User Story:** As an API consumer, I want to upload PDF documents to the service so that they can be indexed and used to answer my questions.

#### Acceptance Criteria

1. WHEN a request is received with `"action": "presign"`, THE Chat_Service SHALL generate a presigned S3 PUT URL for the specified filename
2. THE presigned URL SHALL target the documents S3 bucket with `ContentType: application/pdf`
3. THE presigned URL SHALL expire after 300 seconds
4. THE Chat_Service SHALL return the presigned URL in a JSON body with key `upload_url`
5. THE documents S3 bucket SHALL be configured with CORS to allow PUT and GET from any origin

### Requirement 5: PDF Ingestion Pipeline

**User Story:** As a system operator, I want uploaded PDFs automatically processed into searchable vector embeddings so that the RAG pipeline has up-to-date knowledge.

#### Acceptance Criteria

1. WHEN a PDF file is uploaded to the documents S3 bucket, THE Ingestion_Service SHALL be triggered automatically via S3 event notification
2. THE Ingestion_Service SHALL skip non-PDF files without error
3. WHEN processing a PDF, THE Ingestion_Service SHALL use AWS Textract asynchronous text detection to extract text
4. THE Ingestion_Service SHALL poll the Textract job until it reaches `SUCCEEDED` or `FAILED` status
5. THE Ingestion_Service SHALL chunk extracted text using a sliding window of 500 words with 50-word overlap
6. THE Ingestion_Service SHALL embed each chunk using the Titan embedding model (`amazon.titan-embed-text-v2:0`)
7. THE Ingestion_Service SHALL store embeddings in the S3 Vectors index `aws-docs-index` with metadata containing `source`, `text`, and `chunk_id`
8. THE Ingestion_Service SHALL batch vector writes in groups of up to 100 per API call
9. WHEN vectors already exist for a document key, THE Ingestion_Service SHALL skip Textract processing to avoid redundant cost
10. THE Ingestion_Service SHALL create the S3 Vectors index if it does not already exist (cosine distance, float32, dimension 1024)

### Requirement 6: Hibernation Mode

**User Story:** As a system operator, I want to control system availability through hibernation to manage operational costs.

#### Acceptance Criteria

1. WHEN the `SYSTEM_STATE` environment variable is `"HIBERNATED"`, THE Hibernation_Controller SHALL prevent request processing
2. WHEN the system is hibernated, THE Chat_Service SHALL return HTTP 503 with an appropriate message
3. WHEN the `SYSTEM_STATE` environment variable is `"ACTIVE"`, THE Hibernation_Controller SHALL allow normal request processing
4. THE Hibernation_Controller SHALL check the environment variable on each request
5. THE `SYSTEM_STATE` parameter SHALL default to `HIBERNATED` in the CI/CD pipeline deployment to prevent accidental cost

### Requirement 7: Containerized Lambda Deployment

**User Story:** As a developer, I want both Lambda functions packaged as containers for consistent dependency management and deployment.

#### Acceptance Criteria

1. THE Chat_Service SHALL run in a container based on the AWS Python 3.12 Lambda base image (`public.ecr.aws/lambda/python:3.12`)
2. THE Ingestion_Service SHALL run in a container based on the AWS Python 3.12 Lambda base image
3. WHEN building containers, THE Deployment_Pipeline SHALL include only the handler code (no additional dependencies beyond the base image)
4. THE Container_Registry SHALL store both Lambda images in the same ECR repository (`bedrock-agent`), differentiated by tag prefix (`chat-<sha>` and `ingestion-<sha>`)
5. THE Deployment_Pipeline SHALL tag all images with the Git commit SHA for traceability

### Requirement 8: Infrastructure as Code

**User Story:** As a DevOps engineer, I want all infrastructure defined in CloudFormation for declarative, consistent resource management.

#### Acceptance Criteria

1. THE Infrastructure_Stack SHALL define IAM roles with Bedrock, CloudWatch Logs, S3, S3 Vectors, and Textract permissions in `foundation.yaml`
2. THE Infrastructure_Stack SHALL define the ECR repository in `ecr.yaml`
3. THE Infrastructure_Stack SHALL define the GitHub deployer IAM user in `github-user.yaml`
4. THE Infrastructure_Stack SHALL define both Lambda functions, the Function URL, and all Lambda permissions in `app.yaml`
5. THE Infrastructure_Stack SHALL define the documents S3 bucket with CORS and S3 event notification in `knowledgebase.yaml`
6. THE Infrastructure_Stack SHALL define AWS Budgets alerts and SNS topic in `budget.yaml`
7. WHEN deploying infrastructure, THE Infrastructure_Stack SHALL apply `Project`, `Owner`, `Environment`, `Component`, and `CostCenter` tags to all resources
8. THE Infrastructure_Stack SHALL use parameters for cross-stack references (`LambdaRoleArn`, `IngestionFunctionArn`) and configuration values
9. THE `app.yaml` stack SHALL expose a public Lambda Function URL with CORS open to all origins

### Requirement 9: Automated CI/CD Pipeline

**User Story:** As a developer, I want automated deployment on code changes so that updates ship quickly and reliably.

#### Acceptance Criteria

1. WHEN code is pushed to the `main` branch, THE Deployment_Pipeline SHALL trigger automatically
2. THE Deployment_Pipeline SHALL authenticate to AWS using GitHub secrets (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`)
3. THE Deployment_Pipeline SHALL build and push the chat Lambda container image to ECR
4. THE Deployment_Pipeline SHALL build and push the ingestion Lambda container image to ECR
5. THE Deployment_Pipeline SHALL create the S3 Vectors bucket (`bedrock-rag-vectors-<AccountId>`) if it does not already exist
6. THE Deployment_Pipeline SHALL deploy the Foundation, App, Knowledgebase, and Budget CloudFormation stacks in order
7. THE Deployment_Pipeline SHALL pass the `IngestionFunctionArn` output from the App stack as a parameter to the Knowledgebase stack
8. THE Deployment_Pipeline SHALL use stored secrets for AWS credentials, ECR URI, Lambda role ARN, stack name, tags, and alert email

### Requirement 10: Bootstrap Process

**User Story:** As a system administrator, I want an automated bootstrap script to set up the initial infrastructure before the CI/CD pipeline can run.

#### Acceptance Criteria

1. THE bootstrap script SHALL deploy the Foundation, ECR, and GitHub deployer stacks in sequence
2. THE bootstrap script SHALL use `--capabilities CAPABILITY_NAMED_IAM` for stacks that create IAM resources
3. THE bootstrap script SHALL exit immediately on any deployment failure (`set -e`)
4. WHEN bootstrap completes, the outputs SHALL provide the values needed to configure GitHub secrets (`LambdaRoleArn`, `RepoUri`)

### Requirement 11: Cost Management

**User Story:** As a system operator, I want budget alerts so that I am notified before costs exceed acceptable thresholds.

#### Acceptance Criteria

1. THE Infrastructure_Stack SHALL define a monthly budget of $10 USD for the project
2. THE Infrastructure_Stack SHALL send email and SNS alerts at 50%, 80%, and 100% of actual spend
3. THE Infrastructure_Stack SHALL send an email and SNS alert when forecasted spend exceeds 100% of the budget
4. THE budget alert email address SHALL be configurable via a CloudFormation parameter (`AlertEmail`)

### Requirement 12: Error Handling and Logging

**User Story:** As a system operator, I want proper error handling and logging to troubleshoot issues effectively.

#### Acceptance Criteria

1. WHEN JSON parsing fails, THE Chat_Service SHALL handle the error gracefully without crashing
2. WHEN Bedrock API calls fail, THE Chat_Service SHALL handle the error gracefully and return an appropriate HTTP status code
3. WHEN RAG retrieval fails, THE Chat_Service SHALL log the error and fall back to responding without context
4. WHEN Textract processing fails, THE Ingestion_Service SHALL raise an exception with the job failure details
5. THE Chat_Service SHALL log all requests and errors to CloudWatch Logs
6. THE Ingestion_Service SHALL log processing progress (job ID, status, chunk count, batch writes) to CloudWatch Logs
7. WHEN errors occur, THE Chat_Service SHALL return appropriate HTTP status codes (503 for hibernation, non-200 for other errors)

### Requirement 13: Security and Permissions

**User Story:** As a security engineer, I want least-privilege IAM permissions to minimize security risks.

#### Acceptance Criteria

1. THE Lambda execution role SHALL have only the Bedrock permissions required: `bedrock:InvokeModel`
2. THE Lambda execution role SHALL have CloudWatch Logs write permissions: `logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:PutLogEvents`
3. THE Lambda execution role SHALL have S3 permissions scoped to the documents bucket ARN: `s3:GetObject`, `s3:PutObject`, `s3:ListBucket`, `s3:DeleteObject`
4. THE Lambda execution role SHALL have S3 Vectors permissions: `CreateIndex`, `DeleteIndex`, `GetIndex`, `ListIndexes`, `PutVectors`, `QueryVectors`, `DeleteVectors`, `GetVectors`
5. THE Lambda execution role SHALL have Textract permissions: `textract:StartDocumentTextDetection`, `textract:GetDocumentTextDetection`
6. THE GitHub deployer IAM user SHALL have only deployment-related permissions: ECR push, CloudFormation full access, Lambda full access, and IAM PassRole
7. THE Infrastructure_Stack SHALL use `CAPABILITY_NAMED_IAM` only when required for stacks that create IAM resources
