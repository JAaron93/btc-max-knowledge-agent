import requests
import json
from typing import List, Dict, Any, Optional
from src.utils.config import Config
import os
import re
from urllib.parse import urlparse
from src.utils.result_formatter import AssistantResponseFormatter
from src.utils.url_error_handler import (
    URLValidationError,
    URLMetadataUploadError,
    FallbackURLStrategy,
    GracefulDegradation,
    retry_url_validation,
    retry_url_upload,
    exponential_backoff_retry
)
import logging
import time

# Import our logging infrastructure
from src.utils.url_metadata_logger import (
    log_upload, log_retrieval, correlation_context, generate_correlation_id
)
from src.monitoring.url_metadata_monitor import (
    record_upload, record_retrieval
)

logger = logging.getLogger(__name__)

class PineconeAssistantAgent:
    def __init__(self):
        self.api_key = Config.PINECONE_API_KEY
        self.host = os.getenv('PINECONE_ASSISTANT_HOST')
        
        if not self.host or self.host == "YOUR_PINECONE_ASSISTANT_HOST_HERE":
            raise ValueError("PINECONE_ASSISTANT_HOST not configured. Run setup_pinecone_assistant.py first.")
        
        self.headers = {
            'Api-Key': self.api_key,
            'Content-Type': 'application/json'
        }
        
        # Remove trailing slash if present
        self.host = self.host.rstrip('/')
    
    @retry_url_validation
    def _validate_and_sanitize_url(self, url: str) -> Optional[str]:
        """Validate and sanitize URL with retry logic and fallback strategies"""
        if not url or not isinstance(url, str):
            return None
        
        url = url.strip()
        if not url:
            return None
        
        try:
            # Add protocol if missing
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            
            parsed = urlparse(url)
            # Check if URL has valid scheme and netloc
            if parsed.scheme in ('http', 'https') and parsed.netloc:
                # Basic domain validation
                if '.' in parsed.netloc and len(parsed.netloc) > 3:
                    return url
                else:
                    raise URLValidationError(f"Invalid domain format", url=url)
            else:
                raise URLValidationError(f"Invalid URL scheme or netloc", url=url)
                
        except URLValidationError:
            # Re-raise our custom exceptions
            raise
        except Exception as e:
            # Wrap other exceptions
            raise URLValidationError(f"URL validation failed", url=url, original_error=e)
    
    def _safe_validate_url(self, url: str) -> Optional[str]:
        """Validate URL with fallback strategies"""
        try:
            return self._validate_and_sanitize_url(url)
        except (URLValidationError, Exception) as e:
            logger.warning(f"URL validation failed for '{url}': {e}")
            
            # Try fallback strategies
            if url:
                # Try domain-only URL
                domain_url = FallbackURLStrategy.domain_only_url(url)
                if domain_url:
                    logger.info(f"Using domain-only fallback: {domain_url}")
                    return domain_url
            
            # Return None to indicate failure, but don't block the operation
            return None
    
    def _format_sources_with_urls(self, citations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format citations with graceful handling of missing URL metadata"""
        formatted_sources = []
        
        for citation in citations:
            try:
                # Extract metadata with null-safe approach
                metadata = GracefulDegradation.null_safe_metadata(
                    citation.get('metadata', {})
                )
                
                formatted_source = {
                    'id': citation.get('id', ''),
                    'title': metadata.get('title', ''),
                    'source': metadata.get('source', ''),
                    'category': metadata.get('category', ''),
                    'content': citation.get('text', ''),
                    'url': metadata.get('url', ''),  # Safe default from null_safe_metadata
                    'published': metadata.get('published', ''),
                    'score': citation.get('score', 0.0)
                }
                
                # Validate URL if present
                if formatted_source['url']:
                    validated_url = self._safe_validate_url(formatted_source['url'])
                    formatted_source['url'] = validated_url or ''
                
                formatted_sources.append(formatted_source)
                
            except Exception as e:
                logger.error(f"Error formatting citation {citation.get('id', 'unknown')}: {e}")
                # Add citation with safe defaults even if formatting fails
                formatted_sources.append({
                    'id': citation.get('id', ''),
                    'title': 'Error retrieving title',
                    'source': 'Unknown',
                    'category': '',
                    'content': citation.get('text', ''),
                    'url': '',
                    'published': '',
                    'score': 0.0
                })
        
        return formatted_sources
    
    def create_assistant(self, name: str = "Bitcoin Knowledge Assistant") -> Dict[str, Any]:
        """Create a new Pinecone Assistant for Bitcoin knowledge"""
        
        assistant_config = {
            "name": name,
            "instructions": """You are a Bitcoin and blockchain technology expert assistant. 
            Your role is to educate users about:
            - Bitcoin fundamentals and technology
            - Blockchain concepts and mechanics  
            - Lightning Network and Layer-2 solutions
            - Decentralized applications (dApps)
            - Cryptocurrency regulations like the GENIUS Act
            - Bitcoin news and market developments
            
            Always provide accurate, educational responses based on the knowledge base.
            Cite sources when possible and explain complex concepts clearly.""",
            "model": "gpt-4",
            "metadata": {
                "purpose": "bitcoin-education",
                "domain": "cryptocurrency",
                "created_by": "btc-max-knowledge-agent"
            }
        }
        
        try:
            response = requests.post(
                f"{self.host}/assistants",
                headers=self.headers,
                json=assistant_config
            )
            
            if response.status_code == 201:
                assistant = response.json()
                print(f"✅ Created assistant: {assistant.get('name')} (ID: {assistant.get('id')})")
                return assistant
            else:
                print(f"❌ Failed to create assistant: {response.status_code} - {response.text}")
                return {}
                
        except Exception as e:
            print(f"❌ Error creating assistant: {e}")
            return {}
    
    def list_assistants(self) -> List[Dict[str, Any]]:
        """List all available assistants"""
        try:
            response = requests.get(
                f"{self.host}/assistants",
                headers=self.headers
            )
            
            if response.status_code == 200:
                assistants = response.json().get('assistants', [])
                print(f"📋 Found {len(assistants)} assistants")
                for assistant in assistants:
                    print(f"  - {assistant.get('name')} (ID: {assistant.get('id')})")
                return assistants
            else:
                print(f"❌ Failed to list assistants: {response.status_code} - {response.text}")
                return []
                
        except Exception as e:
            print(f"❌ Error listing assistants: {e}")
            return []
    
    def upload_documents(self, assistant_id: str,
                        documents: List[Dict[str, Any]]) -> bool:
        """Upload documents with null-safe operations and graceful URL handling"""
        
        # Track successful and failed operations
        successful_docs = []
        failed_urls = []
        
        # Convert our document format to Pinecone Assistant format
        for doc in documents:
            try:
                # Safely validate URL without blocking document upload
                url = self._safe_validate_url(doc.get('url', ''))
                
                if not url and doc.get('url'):
                    # URL was provided but validation failed
                    failed_urls.append({
                        'doc_id': doc.get('id', 'unknown'),
                        'original_url': doc.get('url', '')
                    })
                    # Use placeholder URL to continue indexing
                    url = FallbackURLStrategy.placeholder_url(
                        doc.get('id', '')
                    )
                    logger.warning(
                        f"Using placeholder URL for doc {doc.get('id')}: {url}"
                    )
                
                # Ensure metadata is null-safe
                metadata = GracefulDegradation.null_safe_metadata({
                    "title": doc.get('title', ''),
                    "source": doc.get('source', ''),
                    "category": doc.get('category', ''),
                    "url": url or '',
                    "published": doc.get('published', '')
                })
                
                formatted_doc = {
                    "id": doc.get('id', ''),
                    "text": doc.get('content', ''),
                    "metadata": metadata
                }
                successful_docs.append(formatted_doc)
                
            except Exception as e:
                logger.error(
                    f"Error formatting document {doc.get('id', 'unknown')}: {e}"
                )
                # Continue with other documents
                continue
        
        if not successful_docs:
            logger.error("No documents could be formatted for upload")
            return False
        
        # Upload with retry logic
        return self._upload_documents_with_retry(
            assistant_id, successful_docs, failed_urls
        )
    
    @retry_url_upload
    def _upload_documents_with_retry(
        self,
        assistant_id: str,
        formatted_docs: List[Dict[str, Any]],
        failed_urls: List[Dict[str, str]]
    ) -> bool:
        """Upload documents in batches with retry logic"""
        # Create a correlation ID for this upload operation
        correlation_id = generate_correlation_id()
        
        with correlation_context(correlation_id):
            try:
                # Upload in batches
                batch_size = 50
                total_uploaded = 0
                failed_batches = []
                
                for i in range(0, len(formatted_docs), batch_size):
                    batch = formatted_docs[i:i + batch_size]
                    start_time = time.time()
                    
                    try:
                        # Calculate metadata size for batch
                        batch_metadata_size = sum(
                            len(str(doc.get('metadata', {})))
                            for doc in batch
                        )
                        
                        response = requests.post(
                            f"{self.host}/assistants/{assistant_id}/files",
                            headers=self.headers,
                            json={"documents": batch}
                        )
                        
                        duration_ms = (time.time() - start_time) * 1000
                        
                        if response.status_code in [200, 201]:
                            total_uploaded += len(batch)
                            
                            # Log successful upload for each document
                            for doc in batch:
                                log_upload(
                                    url=doc.get('metadata', {}).get('url', ''),
                                    success=True,
                                    metadata_size=len(str(doc.get('metadata', {}))),
                                    duration_ms=duration_ms / len(batch)
                                )
                                record_upload(
                                    url=doc.get('metadata', {}).get('url', ''),
                                    success=True,
                                    duration_ms=duration_ms / len(batch),
                                    metadata_size=len(str(doc.get('metadata', {}))),
                                    correlation_id=correlation_id
                                )
                            
                            logger.info(
                                f"✅ Uploaded batch {i//batch_size + 1}: "
                                f"{len(batch)} documents"
                            )
                        else:
                            error_msg = (f"Batch {i//batch_size + 1} upload "
                                       f"failed: {response.status_code}")
                            logger.error(f"❌ {error_msg} - {response.text}")
                            
                            # Log failed upload for each document
                            for doc in batch:
                                log_upload(
                                    url=doc.get('metadata', {}).get('url', ''),
                                    success=False,
                                    metadata_size=len(str(doc.get('metadata', {}))),
                                    error=f"HTTP {response.status_code}",
                                    duration_ms=duration_ms / len(batch)
                                )
                                record_upload(
                                    url=doc.get('metadata', {}).get('url', ''),
                                    success=False,
                                    duration_ms=duration_ms / len(batch),
                                    metadata_size=len(str(doc.get('metadata', {}))),
                                    error_type=f"http_{response.status_code}",
                                    correlation_id=correlation_id
                                )
                            
                            failed_batches.append({
                                'batch_num': i//batch_size + 1,
                                'size': len(batch),
                                'error': error_msg
                            })
                            # Continue with other batches
                            
                    except requests.exceptions.RequestException as e:
                        duration_ms = (time.time() - start_time) * 1000
                        error_msg = (f"Network error uploading batch "
                                   f"{i//batch_size + 1}")
                        logger.error(f"❌ {error_msg}: {e}")
                        
                        # Log failed upload for each document in batch
                        for doc in batch:
                            log_upload(
                                url=doc.get('metadata', {}).get('url', ''),
                                success=False,
                                metadata_size=len(str(doc.get('metadata', {}))),
                                error=str(e),
                                duration_ms=duration_ms / len(batch)
                            )
                            record_upload(
                                url=doc.get('metadata', {}).get('url', ''),
                                success=False,
                                duration_ms=duration_ms / len(batch),
                                metadata_size=len(str(doc.get('metadata', {}))),
                                error_type='network_error',
                                correlation_id=correlation_id
                            )
                        
                        failed_batches.append({
                            'batch_num': i//batch_size + 1,
                            'size': len(batch),
                            'error': str(e)
                        })
                        # Continue with other batches
                
                # Report results
                if failed_urls:
                    logger.warning(
                        f"⚠️  {len(failed_urls)} documents had invalid URLs "
                        f"and used placeholders"
                    )
                
                if failed_batches:
                    logger.warning(
                        f"⚠️  {len(failed_batches)} batches failed to upload"
                    )
                    
                if total_uploaded > 0:
                    logger.info(
                        f"✅ Successfully uploaded {total_uploaded} documents "
                        f"to assistant {assistant_id}"
                    )
                    # Return True even with partial success
                    return True
                else:
                    raise URLMetadataUploadError(
                        f"Failed to upload any documents to assistant "
                        f"{assistant_id}"
                    )
                
            except Exception as e:
                # Re-raise for retry decorator to handle
                raise URLMetadataUploadError(
                    f"Error uploading documents to assistant {assistant_id}",
                    original_error=e
                )
    
    @exponential_backoff_retry(
        max_retries=3,
        initial_delay=1.0,
        max_delay=10.0,
        exceptions=(requests.exceptions.RequestException, ConnectionError),
        raise_on_exhaust=False,
        fallback_result=None
    )
    def query_assistant(self, assistant_id: str, question: str,
                       include_metadata: bool = True) -> Dict[str, Any]:
        """Query assistant with graceful error handling and URL metadata safety"""
        
        query_data = {
            "message": question,
            "include_metadata": include_metadata,
            "stream": False
        }
        
        try:
            response = requests.post(
                f"{self.host}/assistants/{assistant_id}/chat",
                headers=self.headers,
                json=query_data,
                timeout=30  # Add timeout for reliability
            )
            
            if response.status_code == 200:
                result = response.json()
                
                # Extract and format sources with graceful URL handling
                try:
                    formatted_sources = self._format_sources_with_urls(
                        result.get('citations', [])
                    )
                except Exception as e:
                    logger.error(f"Error formatting sources: {e}")
                    formatted_sources = []
                
                # Use the AssistantResponseFormatter with error handling
                try:
                    formatted_response = (
                        AssistantResponseFormatter.format_assistant_response(
                            answer=result.get('message', ''),
                            sources=formatted_sources
                        )
                    )
                except Exception as e:
                    logger.error(f"Error in response formatter: {e}")
                    # Provide minimal formatting as fallback
                    formatted_response = {
                        'formatted_sources': 'Error formatting sources.',
                        'source_summary': f'Found {len(formatted_sources)} sources.',
                        'structured_sources': formatted_sources
                    }
                
                # Return response with all safety measures
                return {
                    'answer': result.get('message', ''),
                    'sources': formatted_sources,
                    'formatted_sources': formatted_response['formatted_sources'],
                    'source_summary': formatted_response['source_summary'],
                    'structured_sources': formatted_response['structured_sources'],
                    'metadata': result.get('metadata', {})
                }
            else:
                logger.error(
                    f"Query failed: {response.status_code} - {response.text}"
                )
                return self._create_error_response(
                    f"Query failed with status {response.status_code}"
                )
                
        except requests.exceptions.Timeout:
            logger.error("Query timed out")
            return self._create_error_response(
                "Request timed out. Please try again."
            )
        except Exception as e:
            logger.error(f"Error querying assistant: {e}")
            return self._create_error_response(
                "An error occurred while processing your question."
            )
    
    def _create_error_response(self, error_message: str) -> Dict[str, Any]:
        """Create a consistent error response structure"""
        return {
            'answer': f'Sorry, {error_message}',
            'sources': [],
            'formatted_sources': 'No sources available due to error.',
            'source_summary': 'Error occurred during query.',
            'structured_sources': [],
            'metadata': {'error': True, 'message': error_message}
        }
    
    def get_assistant_info(self, assistant_id: str) -> Dict[str, Any]:
        """Get information about a specific assistant"""
        try:
            response = requests.get(
                f"{self.host}/assistants/{assistant_id}",
                headers=self.headers
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"❌ Failed to get assistant info: {response.status_code} - {response.text}")
                return {}
                
        except Exception as e:
            print(f"❌ Error getting assistant info: {e}")
            return {}