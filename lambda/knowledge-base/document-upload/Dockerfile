FROM public.ecr.aws/lambda/python:3.11

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --timeout 120 --retries 5 -r requirements.txt

# Copy all files in ./src
COPY src/ ${LAMBDA_TASK_ROOT}

# Set the CMD to your handler.
CMD [ "index.handler" ]
