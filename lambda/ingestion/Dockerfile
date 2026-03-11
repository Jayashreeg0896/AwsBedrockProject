FROM public.ecr.aws/lambda/python:3.12
COPY ingestion.py ${LAMBDA_TASK_ROOT}
CMD ["ingestion.handler"]