FROM public.ecr.aws/lambda/python:3.11

# Install system dependencies
RUN yum install -y \
    gcc \
    gcc-c++ \
    make \
    && yum clean all

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy all files in ./src
COPY src/ ${LAMBDA_TASK_ROOT}

# Set the CMD to your handler.
CMD [ "index.handler" ]
