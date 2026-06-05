import json
import os
import base64
import uuid
from datetime import datetime
import boto3

# Initialize AWS clients
s3_client = boto3.client('s3')
lambda_client = boto3.client('lambda')

DOCUMENTS_BUCKET = os.environ['DOCUMENTS_BUCKET']
PROCESSOR_FUNCTION = os.environ['PROCESSOR_FUNCTION']
REGION = os.environ['REGION']


def handler(event, context):
    """
    Lambda handler for document upload
    Accepts base64 encoded document and triggers processing
    """
    try:
        # Parse request
        body = json.loads(event.get('body', '{}'))
        
        # Extract document info
        file_content = body.get('file')  # Base64 encoded
        filename = body.get('filename')
        language = body.get('language', 'sr')  # Default to Serbian
        metadata = body.get('metadata', {})
        
        if not file_content or not filename:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'Missing file content or filename'})
            }
        
        # Validate file type
        allowed_extensions = ['.pdf', '.docx', '.txt']
        file_extension = os.path.splitext(filename)[1].lower()
        
        if file_extension not in allowed_extensions:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'error': f'Unsupported file type. Allowed: {", ".join(allowed_extensions)}'
                })
            }
        
        # Decode base64 content
        file_bytes = base64.b64decode(file_content)
        
        # Generate unique document ID
        doc_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().isoformat()
        
        # Create S3 key - files in uploads/ trigger processing Lambda
        s3_key = f"uploads/{language}/{doc_id}/{filename}"
        
        # Prepare metadata
        s3_metadata = {
            'document-id': doc_id,
            'upload-timestamp': timestamp,
            'language': language,
            'original-filename': filename
        }
        
        # Add custom metadata
        for key, value in metadata.items():
            s3_metadata[f'custom-{key}'] = str(value)
        
        # Upload to S3 (this triggers the document processor Lambda)
        s3_client.put_object(
            Bucket=DOCUMENTS_BUCKET,
            Key=s3_key,
            Body=file_bytes,
            Metadata=s3_metadata,
            ContentType=get_content_type(file_extension)
        )
        
        print(f"Document uploaded: {s3_key}")
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'message': 'Document uploaded successfully and queued for processing',
                'documentId': doc_id,
                's3Key': s3_key,
                'bucket': DOCUMENTS_BUCKET,
                'language': language,
                'timestamp': timestamp
            })
        }
        
    except Exception as e:
        print(f"Error uploading document: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': str(e)})
        }


def get_content_type(file_extension):
    """Get content type based on file extension"""
    content_types = {
        '.pdf': 'application/pdf',
        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        '.txt': 'text/plain'
    }
    return content_types.get(file_extension, 'application/octet-stream')
