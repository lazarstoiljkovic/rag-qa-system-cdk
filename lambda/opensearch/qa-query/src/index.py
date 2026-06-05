import json
import os
import uuid
from datetime import datetime
import boto3
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth

# Initialize AWS clients
bedrock_runtime = boto3.client('bedrock-runtime', region_name=os.environ['REGION'])
dynamodb = boto3.resource('dynamodb')

# Environment variables
OPENSEARCH_ENDPOINT = os.environ['OPENSEARCH_ENDPOINT']
OPENSEARCH_INDEX = os.environ['OPENSEARCH_INDEX']
LOGS_TABLE = os.environ['LOGS_TABLE']
REGION = os.environ['REGION']
BEDROCK_MODEL_ID = os.environ['BEDROCK_MODEL_ID']
EMBEDDING_MODEL_ID = os.environ['EMBEDDING_MODEL_ID']
TOP_K = int(os.environ.get('TOP_K', '5'))

# DynamoDB table
logs_table = dynamodb.Table(LOGS_TABLE)

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
    Lambda handler for Q&A queries using Custom OpenSearch RAG
    """
    try:
        # Parse request
        body = json.loads(event.get('body', '{}'))
        question = body.get('question', '').strip()
        language = body.get('language', 'sr')  # sr or en
        top_k = body.get('top_k', TOP_K)
        
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
        
        # Step 1: Generate embedding for the question
        question_embedding = generate_embedding(question)
        
        # Step 2: Search OpenSearch for relevant chunks
        relevant_chunks = search_vectors(question_embedding, language, top_k)
        
        print(f"Found {len(relevant_chunks)} relevant chunks")
        
        # Step 3: Generate answer using LLM with retrieved context
        answer = generate_answer(question, relevant_chunks, language)
        
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
            chunks=relevant_chunks
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
                'contexts': [chunk['text'] for chunk in relevant_chunks],
                'sources': [
                    {
                        'filename': chunk['original_filename'],
                        'score': chunk['score']
                    }
                    for chunk in relevant_chunks
                ]
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


def generate_embedding(text):
    """Generate embedding vector using Bedrock Titan Embeddings"""
    try:
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


def search_vectors(query_embedding, language, k):
    """Search OpenSearch for similar vectors using k-NN"""
    try:
        # k-NN query
        query = {
            'size': k,
            'query': {
                'bool': {
                    'must': [
                        {
                            'knn': {
                                'embedding': {
                                    'vector': query_embedding,
                                    'k': k
                                }
                            }
                        }
                    ],
                    'filter': [
                        {
                            'term': {
                                'language': language
                            }
                        }
                    ]
                }
            },
            '_source': ['text', 'document_id', 'chunk_index', 'original_filename', 'source_file']
        }
        
        response = opensearch_client.search(
            index=OPENSEARCH_INDEX,
            body=query
        )
        
        # Extract results
        chunks = []
        for hit in response['hits']['hits']:
            source = hit['_source']
            chunks.append({
                'text': source['text'],
                'document_id': source['document_id'],
                'chunk_index': source['chunk_index'],
                'original_filename': source.get('original_filename', 'Unknown'),
                'source_file': source.get('source_file', ''),
                'score': hit['_score']
            })
        
        return chunks
        
    except Exception as e:
        print(f"Error searching vectors: {str(e)}")
        raise


def generate_answer(question, chunks, language):
    """Generate answer using Bedrock LLM with retrieved context"""
    try:
        # Prepare context from chunks
        context_parts = []
        for i, chunk in enumerate(chunks):
            context_parts.append(
                f"[Dokument {i+1}: {chunk['original_filename']}]\n{chunk['text']}"
            )
        
        context_text = "\n\n".join(context_parts)
        
        # Prepare prompt based on language
        if language == 'sr':
            prompt = f"""Ti si pomoćnik za odgovaranje na pitanja na osnovu datih dokumenata.

Kontekst iz dokumenata:
{context_text}

Pitanje: {question}

Molim te da odgovoriš na pitanje koristeći isključivo informacije iz datog konteksta. Ako odgovor nije u kontekstu, reci da ne znaš. Odgovori jasno i koncizno na srpskom jeziku."""
        else:
            prompt = f"""You are a helpful assistant that answers questions based on provided documents.

Context from documents:
{context_text}

Question: {question}

Please answer the question using only the information from the given context. If the answer is not in the context, say you don't know. Answer clearly and concisely in English."""

        # Call Bedrock - Claude 3 Sonnet
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1500,
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


def log_query(query_id, question, answer, language,
              processing_time, chunks):
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
                'retrievedChunks': len(chunks),
                'sources': [chunk['original_filename'] for chunk in chunks],
                'solution': 'custom-opensearch'
            }
        )
        print(f"Query logged: {query_id}")
    except Exception as e:
        print(f"Error logging query: {str(e)}")
