# Implementation Plan: Serverless Bedrock Chat (RAG Edition)

## Overview

This implementation plan covers the full serverless RAG-based chat system. The system has evolved from a simple Bedrock chat endpoint into a retrieval-augmented generation (RAG) pipeline that supports PDF document ingestion, vector search via S3 Vectors, and context-aware AI responses using Claude 3 Haiku.

The architecture includes:
- **Chat Lambda** (`lambda/chat/handler.py`): Handles chat requests, RAG retrieval, presigned URL generation, and Bedrock inference
- **Ingestion Lambda** (`lambda/ingestion/ingestion.py`): Processes PDF uploads via S3 events, runs Textract, chunks text, embeds with Titan, and stores vectors in S3 Vectors
- **Infrastructure**: Foundation (IAM), ECR, GitHub deployer, App (Chat + Ingestion Lambdas), Knowledgebase (S3 documents bucket), Budget stacks
- **CI/CD**: GitHub Actions pipeline deploying both Lambda images and all CloudFormation stacks

---

## Tasks

### Phase 1: Core Infrastructure

- [x] 1. Foundation stack (`infra/foundation.yaml`)
  - IAM role with Bedrock, CloudWatch Logs, S3, S3 Vectors, and Textract permissions
  - Outputs: `LambdaRoleArn`
  - _Requirements: 5.1, 9.1, 9.2_

- [x] 2. ECR repository stack (`infra/ecr.yaml`)
  - Single ECR repository `bedrock-agent` for both Lambda images
  - Outputs: `RepoUri`
  - _Requirements: 5.2_

- [x] 3. GitHub deployer stack (`infra/github-user.yaml`)
  - IAM user `github-bedrock-deployer` with ECR push, CloudFormation, Lambda, and IAM PassRole permissions
  - _Requirements: 5.3, 9.3_

- [x] 4. App stack (`infra/app.yaml`)
  - `ChatFunction`: container Lambda with `SYSTEM_STATE`, `DOCUMENTS_BUCKET`, `VECTORS_BUCKET` env vars, Function URL (CORS open), 60s timeout
  - `IngestionFunction`: container Lambda with `DOCUMENTS_BUCKET`, `VECTORS_BUCKET` env vars, 300s timeout
  - S3 invoke permission for `IngestionFunction`
  - Outputs: `FunctionUrl`, `IngestionFunctionArn`
  - Parameters: `ChatImageUri`, `IngestionImageUri`, `LambdaRoleArn`, `SystemState`, tags
  - _Requirements: 5.4, 5.7_

- [x] 5. Knowledgebase stack (`infra/knowledgebase.yaml`)
  - S3 bucket `bedrock-rag-documents-<AccountId>` with CORS and S3 event notification triggering `IngestionFunction` on `.pdf` uploads
  - Outputs: `DocumentsBucketName`, `DocumentsBucketArn`
  - _Requirements: 5.8_

- [x] 6. Budget stack (`infra/budget.yaml`)
  - AWS Budgets alert with configurable threshold and email notification
  - Parameters: `ProjectTag`, `OwnerTag`, `EnvTag`, `AlertEmail`

---

### Phase 2: Lambda Functions

- [x] 7. Chat Lambda (`lambda/chat/handler.py`)
  - [x] 7.1 Hibernation check — return 503 if `SYSTEM_STATE == "HIBERNATED"`
  - [x] 7.2 Presign action — generate S3 presigned PUT URL for PDF uploads (`action: "presign"`)
  - [x] 7.3 RAG retrieval — embed question with Titan (`amazon.titan-embed-text-v2:0`), query S3 Vectors index `aws-docs-index` (top-K=3), extract context and sources from metadata
  - [x] 7.4 System prompt construction — inject retrieved context when available; fall back to generic AWS assistant prompt
  - [x] 7.5 Conversation history support — accept `history` array and prepend prior turns to messages
  - [x] 7.6 Bedrock inference — call `converse` with Claude 3 Haiku (`anthropic.claude-3-haiku-20240307-v1:0`), `maxTokens: 1024`
  - [x] 7.7 Response — return `{ response, sources }` as JSON with status 200

- [x] 8. Ingestion Lambda (`lambda/ingestion/ingestion.py`)
  - [x] 8.1 Index bootstrap — create S3 Vectors index `aws-docs-index` (cosine, float32, dim=1024) if it doesn't exist
  - [x] 8.2 Deduplication — skip Textract if vectors already exist for the document key
  - [x] 8.3 PDF text extraction — async Textract job with polling loop; concatenate LINE blocks across all pages
  - [x] 8.4 Chunking — sliding window (500 words, 50-word overlap)
  - [x] 8.5 Embedding — Titan embed model per chunk
  - [x] 8.6 Vector storage — batch `put_vectors` (max 100 per call) with metadata: `source`, `text`, `chunk_id`
  - [x] 8.7 S3 event trigger — process all `Records` from S3 event; skip non-PDF keys

---

### Phase 3: CI/CD Pipeline

- [x] 9. GitHub Actions workflow (`.github/workflows/deploy.yaml`)
  - [x] 9.1 Trigger on push to `main`
  - [x] 9.2 AWS auth via `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` secrets
  - [x] 9.3 Build, tag (`chat-<sha>`), and push chat image to ECR
  - [x] 9.4 Build, tag (`ingestion-<sha>`), and push ingestion image to ECR
  - [x] 9.5 Create S3 Vectors bucket (`bedrock-rag-vectors-<AccountId>`) if it doesn't exist
  - [x] 9.6 Deploy Foundation stack
  - [x] 9.7 Deploy App stack with both image URIs and `SystemState=HIBERNATED`
  - [x] 9.8 Deploy Knowledgebase stack (reads `IngestionFunctionArn` from App stack output)
  - [x] 9.9 Deploy Budget stack
  - _Requirements: 6.1–6.7_

- [x] 10. Bootstrap script (`bootstrap.sh`)
  - Deploys Foundation → ECR → GitHub deployer in sequence
  - Uses `CAPABILITY_NAMED_IAM` for IAM stacks
  - _Requirements: 7.1, 7.5, 9.5_

---

### Phase 4: Test Suite

- [x] 11. Set up testing infrastructure
  - Test directory structure: `tests/unit`, `tests/property`, `tests/infrastructure`
  - Dependencies: `pytest`, `hypothesis`, `pytest-mock`, `pyyaml`, `botocore`
  - `pytest.ini` with markers: `unit`, `property`, `infrastructure`

- [x] 12. Unit tests — Chat Lambda (`tests/unit/test_handler.py`)
  - [x] 12.1 Hibernation returns 503
  - [x] 12.2 Presign action returns upload URL
  - [x] 12.3 Normal chat request invokes Bedrock and returns 200 with `response` and `sources`
  - [x] 12.4 Default question used when field is missing
  - [x] 12.5 Conversation history forwarded to Bedrock
  - [x] 12.6 Bedrock failure handled gracefully
  - [x] 12.7 RAG context injected into system prompt when vectors found
  - [x] 12.8 Generic system prompt used when no vectors found
  - _Requirements: 1.1–1.5, 3.1–3.5, 8.1–8.2_

- [x] 13. Unit tests — Configuration (`tests/unit/test_configuration.py`)
  - [x] 13.1 Chat model ID is `anthropic.claude-3-haiku-20240307-v1:0`
  - [x] 13.2 Embedding model ID is `amazon.titan-embed-text-v2:0`
  - [x] 13.3 Max tokens is 1024
  - [x] 13.4 `converse` API used for chat
  - [x] 13.5 `invoke_model` used for embeddings
  - [x] 13.6 S3 Vectors index name is `aws-docs-index`
  - [x] 13.7 TOP_K is 3
  - _Requirements: 2.1–2.5_

- [x] 14. Property tests — Request processing (`tests/property/test_request_properties.py`)
  - [x] 14.1 Property 1: Any valid question string is forwarded to Bedrock unchanged
  - [x] 14.2 Property 3: Question field correctly extracted from any valid JSON body
  - [x] 14.3 Property 7: Invalid JSON handled gracefully without crash

- [x] 15. Property tests — Response handling (`tests/property/test_response_properties.py`)
  - [x] 15.1 Property 2: Successful response always returns status 200 with valid JSON body
  - [x] 15.2 Property 4: All responses have a parseable JSON body
  - [x] 15.3 Property 8: Error conditions return non-200 status codes

- [x] 16. Property tests — Bedrock integration (`tests/property/test_bedrock_properties.py`)
  - [x] 16.1 Property 5: Messages always formatted with role `"user"` and question text in content
  - [x] 16.2 Property 6: Response text correctly extracted from nested Bedrock response structure

- [x] 17. Infrastructure tests — CloudFormation (`tests/infrastructure/test_cloudformation.py`)
  - [x] 17.1 `foundation.yaml`: IAM role exists with Bedrock, CloudWatch, S3, S3 Vectors, and Textract permissions
  - [x] 17.2 `ecr.yaml`: ECR repository resource exists
  - [x] 17.3 `github-user.yaml`: IAM user with ECR, CloudFormation, Lambda, and IAM PassRole permissions
  - [x] 17.4 `app.yaml`: ChatFunction and IngestionFunction defined with container image config
  - [x] 17.5 `app.yaml`: `SYSTEM_STATE`, `DOCUMENTS_BUCKET`, `VECTORS_BUCKET` env vars present on ChatFunction
  - [x] 17.6 `app.yaml`: Function URL resource with CORS defined
  - [x] 17.7 `app.yaml`: `ChatImageUri`, `IngestionImageUri`, `LambdaRoleArn` parameters exist
  - [x] 17.8 `knowledgebase.yaml`: S3 bucket with S3 event notification to IngestionFunction
  - [x] 17.9 All templates include Project, Owner, Environment tag parameters
  - _Requirements: 5.1–5.8, 9.1–9.5_

- [x] 18. Infrastructure tests — Pipeline (`tests/infrastructure/test_pipeline.py`)
  - [x] 18.1 Workflow triggers on push to `main`
  - [x] 18.2 AWS auth uses `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` secrets
  - [x] 18.3 Chat Docker build step present
  - [x] 18.4 Ingestion Docker build step present
  - [x] 18.5 Images tagged with Git commit SHA
  - [x] 18.6 Both images pushed to ECR
  - [x] 18.7 S3 Vectors bucket creation step present
  - [x] 18.8 CloudFormation deploy steps for Foundation, App, Knowledgebase, and Budget stacks
  - [x] 18.9 All required secrets referenced: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, `ECR_REPO_URI`, `LAMBDA_ROLE_ARN`, `STACK_NAME`, `PROJECT`, `OWNER`, `ENV`, `ALERT_EMAIL`
  - _Requirements: 6.1–6.7_

- [x] 19. Checkpoint — Full test suite passes
  - Run `python -m pytest -v`
  - Verify 100% pass rate across unit, property, and infrastructure tests

- [x] 20. Test documentation (`tests/README.md`)
  - How to run tests locally
  - Test categories and coverage expectations
  - Mocking strategies

---

## Notes

- The S3 Vectors bucket (`bedrock-rag-vectors-<AccountId>`) is created imperatively in the pipeline (not via CloudFormation) because S3 Vectors is a newer service with limited CloudFormation support
- The `ecr.yaml` stack uses a single repository (`bedrock-agent`) for both Lambda images, differentiated by tag prefix (`chat-` and `ingestion-`)
- Ingestion Lambda has a 300s timeout to accommodate long Textract jobs on large PDFs
- The `SystemState` parameter defaults to `HIBERNATED` in the pipeline deploy to prevent accidental cost during CI
- All property tests use Hypothesis with a minimum of 100 iterations per property
