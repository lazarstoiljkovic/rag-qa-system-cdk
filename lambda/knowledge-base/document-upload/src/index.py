import json
import os
import base64
import uuid
from datetime import datetime
import boto3
import io

# Initialize AWS clients
s3_client = boto3.client('s3')

DOCUMENTS_BUCKET = os.environ['DOCUMENTS_BUCKET']
REGION = os.environ['REGION']


def handler(event, context):
    """
    Lambda handler for document upload to S3
    Supports base64 encoded document upload via API Gateway
    """
    try:
        http_method = event.get('httpMethod', '')
        
        if http_method == 'POST':
            return upload_document(event)
        elif http_method == 'GET':
            return list_documents()
        else:
            return {
                'statusCode': 405,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'Method not allowed'})
            }
            
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': str(e)})
        }


def upload_document(event):
    """Upload a document to S3"""
    try:
        # Parse request body
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
        
        # Create S3 key
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
        
        # Upload to S3
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
                'message': 'Document uploaded successfully',
                'documentId': doc_id,
                's3Key': s3_key,
                'bucket': DOCUMENTS_BUCKET,
                'language': language,
                'timestamp': timestamp
            })
        }
        
    except Exception as e:
        print(f"Error uploading document: {str(e)}")
        raise


def list_documents():
    """List all documents in the S3 bucket"""
    try:
        response = s3_client.list_objects_v2(
            Bucket=DOCUMENTS_BUCKET,
            Prefix='uploads/'
        )
        
        documents = []
        
        if 'Contents' in response:
            for obj in response['Contents']:
                # Get object metadata
                metadata_response = s3_client.head_object(
                    Bucket=DOCUMENTS_BUCKET,
                    Key=obj['Key']
                )
                
                metadata = metadata_response.get('Metadata', {})
                
                documents.append({
                    'key': obj['Key'],
                    'size': obj['Size'],
                    'lastModified': obj['LastModified'].isoformat(),
                    'documentId': metadata.get('document-id'),
                    'language': metadata.get('language'),
                    'originalFilename': metadata.get('original-filename')
                })
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'documents': documents,
                'count': len(documents)
            })
        }
        
    except Exception as e:
        print(f"Error listing documents: {str(e)}")
        raise


def get_content_type(file_extension):
    """Get content type based on file extension"""
    content_types = {
        '.pdf': 'application/pdf',
        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        '.txt': 'text/plain'
    }
    return content_types.get(file_extension, 'application/octet-stream')
