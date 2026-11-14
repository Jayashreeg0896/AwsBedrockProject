# Agentic policy assistant Lambda (container image)
# Build from the REPO ROOT:  docker build -t policy -f lambda/policy/Dockerfile .
FROM public.ecr.aws/lambda/python:3.12

# Layer 1: Python packages - cached, only rebuilt when requirements.txt changes
COPY lambda/policy/requirements.txt ${LAMBDA_TASK_ROOT}/
RUN pip install --no-cache-dir -r ${LAMBDA_TASK_ROOT}/requirements.txt

# Layer 2: application code - rebuilt on every code change (fast)
COPY langchain/policy_cache.py \
     langchain/policy_rag_graph.py \
     langchain/policy_agentic_rag.py \
     langchain/lambda_handler.py \
     langchain/cache_cleanup.py \
     ${LAMBDA_TASK_ROOT}/

# Default entry point = the API. The cache cleanup Lambda uses the same image with
# ImageConfig.Command = cache_cleanup.lambda_handler (see infra/app.yaml)
CMD ["lambda_handler.handler"]
