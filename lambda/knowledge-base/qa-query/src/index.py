import json
import os
import uuid
from datetime import datetime
import boto3

# Initialize AWS clients
bedrock_runtime = boto3.client('bedrock-runtime', region_name=os.environ['REGION'])
s3_client = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')

DOCUMENTS_BUCKET = os.environ['DOCUMENTS_BUCKET']
LOGS_TABLE = os.environ['LOGS_TABLE']
REGION = os.environ['REGION']
BEDROCK_MODEL_ID = os.environ['BEDROCK_MODEL_ID']
EMBEDDING_MODEL_ID = os.environ['EMBEDDING_MODEL_ID']

# DynamoDB table
logs_table = dynamodb.Table(LOGS_TABLE)


def handler(event, context):
    """
    Lambda handler for Q&A queries using Bedrock Knowledge Base
    This is a simplified version that uses Bedrock directly
    In production, this would use the Knowledge Base API
    """
    try:
        # Parse request
        body = json.loads(event.get('body', '{}'))
        question = body.get('question', '').strip()
        language = body.get('language', 'sr')  # sr or en
        
        if not question:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'Question is required'})
            }
        
        # Generate query ID
        query_id = str(uuid.uuid4())
        start_time = datetime.utcnow()
        
        print(f"Processing query {query_id}: {question}")
        
        # For Knowledge Base solution, we'll use a simplified approach
        # In production, you would use bedrock-agent-runtime RetrieveAndGenerate
        
        # Step 1: Retrieve relevant documents (simplified - in production use KB API)
        relevant_context = retrieve_context(question, language)
        
        # Step 2: Generate answer using LLM
        answer = generate_answer(question, relevant_context, language)
        
        # Calculate processing time
        end_time = datetime.utcnow()
        processing_time = (end_time - start_time).total_seconds()
        
        # Log the query
        log_query(
            query_id=query_id,
            question=question,
            answer=answer,
            language=language,
            processing_time=processing_time,
            context=relevant_context
        )
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'queryId': query_id,
                'question': question,
                'answer': answer,
                'language': language,
                'processingTime': processing_time,
                'contexts': [ctx['text'] for ctx in relevant_context],
                'sources': [ctx['source'] for ctx in relevant_context]
            }, ensure_ascii=False)
        }
        
    except Exception as e:
        print(f"Error processing query: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': str(e)})
        }


def retrieve_context(question, language):
    """
    Retrieve relevant context from documents
    In production, this would use Bedrock Knowledge Base RetrieveAndGenerate API
    This is a simplified version for demonstration
    """
    try:
        # List documents from S3
        response = s3_client.list_objects_v2(
            Bucket=DOCUMENTS_BUCKET,
            Prefix=f'uploads/{language}/',
            MaxKeys=5
        )
        
        contexts = []
        
        if 'Contents' in response:
            for obj in response['Contents'][:3]:  # Limit to 3 documents
                # Get metadata
                metadata_response = s3_client.head_object(
                    Bucket=DOCUMENTS_BUCKET,
                    Key=obj['Key']
                )
                
                metadata = metadata_response.get('Metadata', {})
                
                contexts.append({
                    'text': f"Dokument: {metadata.get('original-filename', 'Unknown')}",
                    'source': obj['Key'],
                    'score': 0.85  # Mock relevance score
                })
        
        return contexts
        
    except Exception as e:
        print(f"Error retrieving context: {str(e)}")
        return []


def generate_answer(question, context, language):
    """Generate answer using Bedrock LLM"""
    try:
        # Prepare context text
        context_text = "\n\n".join([
            f"Izvor {i+1}: {ctx['text']}" 
            for i, ctx in enumerate(context)
        ])
        
        # Prepare prompt based on language
        if language == 'sr':
            prompt = f"""Ti si pomoćnik za odgovaranje na pitanja na osnovu datih dokumenata.

Kontekst iz dokumenata:
{context_text}

Pitanje: {question}

Molim te da odgovoriš na pitanje koristeći isključivo informacije iz datog konteksta. Ako odgovor nije u kontekstu, reci da ne znaš. Odgovori na srpskom jeziku."""
        else:
            prompt = f"""You are a helpful assistant that answers questions based on provided documents.

Context from documents:
{context_text}

Question: {question}

Please answer the question using only the information from the given context. If the answer is not in the context, say you don't know. Answer in English."""

        # Call Bedrock - Claude 3 Haiku
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1000,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.3,
            "top_p": 0.9
        }
        
        response = bedrock_runtime.invoke_model(
            modelId=BEDROCK_MODEL_ID,
            body=json.dumps(request_body)
        )
        
        response_body = json.loads(response['body'].read())
        answer = response_body['content'][0]['text']
        
        return answer
        
    except Exception as e:
        print(f"Error generating answer: {str(e)}")
        if language == 'sr':
            return f"Greška pri generisanju odgovora: {str(e)}"
        else:
            return f"Error generating answer: {str(e)}"


def log_query(query_id, question, answer, language, processing_time, context):
    """Log query to DynamoDB"""
    try:
        logs_table.put_item(
            Item={
                'queryId': query_id,
                'timestamp': datetime.utcnow().isoformat(),
                'question': question,
                'answer': answer,
                'language': language,
                'processingTime': str(processing_time),
                'contextSources': [ctx['source'] for ctx in context],
                'solution': 'knowledge-base'
            }
        )
        print(f"Query logged: {query_id}")
    except Exception as e:
        print(f"Error logging query: {str(e)}")
