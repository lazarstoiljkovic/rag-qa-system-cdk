import json
import os
import uuid
from datetime import datetime
import boto3
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth
import PyPDF2
import docx
import io

# Initialize AWS clients
s3_client = boto3.client('s3')
bedrock_runtime = boto3.client('bedrock-runtime', region_name=os.environ['REGION'])
dynamodb = boto3.resource('dynamodb')

# Environment variables
DOCUMENTS_BUCKET = os.environ['DOCUMENTS_BUCKET']
OPENSEARCH_ENDPOINT = os.environ['OPENSEARCH_ENDPOINT']
OPENSEARCH_INDEX = os.environ['OPENSEARCH_INDEX']
METADATA_TABLE = os.environ['METADATA_TABLE']
REGION = os.environ['REGION']
EMBEDDING_MODEL_ID = os.environ['EMBEDDING_MODEL_ID']
CHUNK_SIZE = int(os.environ.get('CHUNK_SIZE', '512'))
CHUNK_OVERLAP = int(os.environ.get('CHUNK_OVERLAP', '50'))

# DynamoDB table
metadata_table = dynamodb.Table(METADATA_TABLE)

# OpenSearch client
credentials = boto3.Session().get_credentials()
awsauth = AWS4Auth(
    credentials.access_key,
    credentials.secret_key,
    REGION,
    'es',
    session_token=credentials.token
)

opensearch_client = OpenSearch(
    hosts=[{'host': OPENSEARCH_ENDPOINT, 'port': 443}],
    http_auth=awsauth,
    use_ssl=True,
    verify_certs=True,
    connection_class=RequestsHttpConnection
)


def handler(event, context):
    """
    Lambda handler for processing documents
    Triggered by S3 events when documents are uploaded
    """
    try:
        print(f"Event: {json.dumps(event)}")
        
        # Handle S3 event
        for record in event.get('Records', []):
            if 's3' in record:
                bucket = record['s3']['bucket']['name']
                key = record['s3']['object']['key']
                
                print(f"Processing document: {key}")
                
                # Process the document
                process_document(bucket, key)
        
        return {
            'statusCode': 200,
            'body': json.dumps({'message': 'Documents processed successfully'})
        }
        
    except Exception as e:
        print(f"Error processing documents: {str(e)}")
        raise


def process_document(bucket, key):
    """Process a single document: extract text, chunk, embed, and index"""
    try:
        # Download document from S3
        response = s3_client.get_object(Bucket=bucket, Key=key)
        file_content = response['Body'].read()
        metadata = response.get('Metadata', {})
        
        # Extract document info
        doc_id = metadata.get('document-id', str(uuid.uuid4()))
        language = metadata.get('language', 'sr')
        original_filename = metadata.get('original-filename', key.split('/')[-1])
        
        # Determine file type and extract text
        file_extension = os.path.splitext(key)[1].lower()
        
        if file_extension == '.pdf':
            text = extract_text_from_pdf(file_content)
        elif file_extension == '.docx':
            text = extract_text_from_docx(file_content)
        elif file_extension == '.txt':
            text = file_content.decode('utf-8')
        else:
            raise ValueError(f"Unsupported file type: {file_extension}")
        
        print(f"Extracted {len(text)} characters from document")
        
        # Create chunks
        chunks = create_chunks(text, CHUNK_SIZE, CHUNK_OVERLAP)
        print(f"Created {len(chunks)} chunks")
        
        # Ensure OpenSearch index exists
        ensure_index_exists()
        
        # Process each chunk
        indexed_chunks = []
        for i, chunk_text in enumerate(chunks):
            # Generate embedding
            embedding = generate_embedding(chunk_text)
            
            # Create chunk document
            chunk_id = f"{doc_id}_chunk_{i}"
            chunk_doc = {
                'chunk_id': chunk_id,
                'document_id': doc_id,
                'chunk_index': i,
                'text': chunk_text,
                'embedding': embedding,
                'language': language,
                'source_file': key,
                'original_filename': original_filename,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            # Index in OpenSearch
            opensearch_client.index(
                index=OPENSEARCH_INDEX,
                id=chunk_id,
                body=chunk_doc
            )
            
            indexed_chunks.append(chunk_id)
        
        # Save metadata to DynamoDB
        metadata_table.put_item(
            Item={
                'documentId': doc_id,
                'sourceFile': key,
                'originalFilename': original_filename,
                'language': language,
                'totalChunks': len(chunks),
                'chunkIds': indexed_chunks,
                'processedAt': datetime.utcnow().isoformat(),
                'textLength': len(text),
                'status': 'indexed'
            }
        )
        
        print(f"Document {doc_id} processed and indexed successfully")
        
    except Exception as e:
        print(f"Error processing document {key}: {str(e)}")
        raise


def extract_text_from_pdf(file_content):
    """Extract text from PDF file"""
    try:
        pdf_file = io.BytesIO(file_content)
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
        
        return text.strip()
    except Exception as e:
        print(f"Error extracting text from PDF: {str(e)}")
        raise


def extract_text_from_docx(file_content):
    """Extract text from DOCX file"""
    try:
        docx_file = io.BytesIO(file_content)
        doc = docx.Document(docx_file)
        
        text = ""
        for paragraph in doc.paragraphs:
            text += paragraph.text + "\n"
        
        return text.strip()
    except Exception as e:
        print(f"Error extracting text from DOCX: {str(e)}")
        raise


def create_chunks(text, chunk_size, overlap):
    """
    Split text into overlapping chunks
    This is a simple character-based chunking strategy
    """
    chunks = []
    start = 0
    text_length = len(text)
    
    while start < text_length:
        # Define chunk end
        end = min(start + chunk_size, text_length)
        
        # Extract chunk
        chunk = text[start:end].strip()
        
        if chunk:
            chunks.append(chunk)
        
        # Move to next chunk with overlap
        start += chunk_size - overlap
    
    return chunks


def generate_embedding(text):
    """Generate embedding vector using Bedrock Titan Embeddings"""
    try:
        # Prepare request for Titan Embeddings v2
        request_body = {
            "inputText": text
        }
        
        response = bedrock_runtime.invoke_model(
            modelId=EMBEDDING_MODEL_ID,
            body=json.dumps(request_body)
        )
        
        response_body = json.loads(response['body'].read())
        embedding = response_body['embedding']
        
        return embedding
        
    except Exception as e:
        print(f"Error generating embedding: {str(e)}")
        raise


def ensure_index_exists():
    """Create OpenSearch index if it doesn't exist"""
    try:
        if not opensearch_client.indices.exists(index=OPENSEARCH_INDEX):
            # Index mapping with k-NN for vector search
            index_body = {
                'settings': {
                    'index': {
                        'knn': True,
                        'knn.algo_param.ef_search': 512
                    }
                },
                'mappings': {
                    'properties': {
                        'chunk_id': {'type': 'keyword'},
                        'document_id': {'type': 'keyword'},
                        'chunk_index': {'type': 'integer'},
                        'text': {
                            'type': 'text',
                            'analyzer': 'standard'
                        },
                        'embedding': {
                            'type': 'knn_vector',
                            'dimension': 1024,  # Titan Embeddings v2 dimension
                            'method': {
                                'name': 'hnsw',
                                'space_type': 'cosinesimil',
                                'engine': 'nmslib',
                                'parameters': {
                                    'ef_construction': 512,
                                    'm': 16
                                }
                            }
                        },
                        'language': {'type': 'keyword'},
                        'source_file': {'type': 'keyword'},
                        'original_filename': {'type': 'keyword'},
                        'timestamp': {'type': 'date'}
                    }
                }
            }
            
            opensearch_client.indices.create(
                index=OPENSEARCH_INDEX,
                body=index_body
            )
            
            print(f"Created index: {OPENSEARCH_INDEX}")
        else:
            print(f"Index already exists: {OPENSEARCH_INDEX}")
            
    except Exception as e:
        print(f"Error creating index: {str(e)}")
        raise
