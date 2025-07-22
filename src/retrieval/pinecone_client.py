from pinecone import Pinecone, ServerlessSpec
import time
import re
from urllib.parse import urlparse
from typing import List, Dict, Any, Optional
from src.utils.config import Config
from src.utils.result_formatter import QueryResultFormatter
from src.utils.url_error_handler import (
    URLValidationError,
    URLRetrievalError,
    FallbackURLStrategy,
    GracefulDegradation,
    retry_url_validation,
    exponential_backoff_retry
)
import logging

logger = logging.getLogger(__name__)

class PineconeClient:
    def __init__(self):
        Config.validate()
        
        # Initialize Pinecone
        self.pc = Pinecone(api_key=Config.PINECONE_API_KEY)
        
        self.index_name = Config.PINECONE_INDEX_NAME
        self.dimension = Config.EMBEDDING_DIMENSION
        
    def create_index(self):
        """Create Pinecone index if it doesn't exist"""
        if self.index_name not in self.pc.list_indexes().names():
            print(f"Creating index: {self.index_name}")
            self.pc.create_index(
                name=self.index_name,
                dimension=self.dimension,
                metric="cosine",
                spec=ServerlessSpec(
                    cloud="aws",
                    region="us-east-1"
                )
            )
            
            # Wait for index to be ready
            while not self.pc.describe_index(self.index_name).status['ready']:
                time.sleep(1)
            print(f"Index {self.index_name} is ready!")
        else:
            print(f"Index {self.index_name} already exists")
    
    def get_index(self):
        """Get the Pinecone index"""
        return self.pc.Index(self.index_name)
    
    @retry_url_validation
    def validate_and_sanitize_url(self, url: Optional[str]) -> Optional[str]:
        """Validate and sanitize URL with retry logic"""
        if not url or not isinstance(url, str):
            return None
        
        # Strip whitespace
        url = url.strip()
        if not url:
            return None
        
        try:
            # Add protocol if missing
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            
            # Parse URL to validate structure
            parsed = urlparse(url)
            
            # Check if URL has valid scheme and netloc
            if not parsed.scheme or not parsed.netloc:
                raise URLValidationError(
                    "Invalid URL structure", url=url
                )
            
            # Basic domain validation
            if not re.match(r'^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', parsed.netloc):
                raise URLValidationError(
                    "Invalid domain format", url=url
                )
            
            return url
        except URLValidationError:
            raise
        except Exception as e:
            raise URLValidationError(
                "URL validation failed", url=url, original_error=e
            )
    
    def safe_validate_url(self, url: Optional[str]) -> Optional[str]:
        """Validate URL with fallback strategies"""
        try:
            return self.validate_and_sanitize_url(url)
        except (URLValidationError, Exception) as e:
            logger.warning(f"URL validation failed for '{url}': {e}")
            
            # Try fallback strategies
            if url:
                # Try domain-only URL
                domain_url = FallbackURLStrategy.domain_only_url(url)
                if domain_url:
                    logger.info(f"Using domain-only fallback: {domain_url}")
                    return domain_url
            
            # Return None to indicate failure
            return None
    
    @exponential_backoff_retry(
        max_retries=3,
        initial_delay=1.0,
        max_delay=30.0,
        exceptions=(Exception,),
        raise_on_exhaust=True
    )
    def upsert_documents(self, documents: List[Dict[str, Any]]):
        """Upsert documents with graceful URL handling and error recovery"""
        index = self.get_index()
        
        vectors = []
        failed_urls = []
        
        for i, doc in enumerate(documents):
            try:
                # Safely validate URL without blocking document indexing
                url = self.safe_validate_url(doc.get('url'))
                
                if not url and doc.get('url'):
                    # URL was provided but validation failed
                    failed_urls.append({
                        'doc_id': doc.get('id', f"doc_{i}"),
                        'original_url': doc.get('url', '')
                    })
                    # Use placeholder URL
                    url = FallbackURLStrategy.placeholder_url(
                        doc.get('id', f"doc_{i}")
                    )
                    logger.warning(
                        f"Using placeholder URL for doc {doc.get('id', f'doc_{i}')}"
                    )
                
                # Ensure metadata is null-safe
                metadata = GracefulDegradation.null_safe_metadata({
                    'title': doc.get('title', ''),
                    'source': doc.get('source', ''),
                    'category': doc.get('category', ''),
                    'content': doc.get('content', '')[:1000],  # First 1000 chars
                    'url': url or ''  # Ensure URL field exists
                })
                
                # Add published date if available
                if doc.get('published'):
                    metadata['published'] = doc['published']
                
                # Prepare vector for upsert
                vector = {
                    'id': doc.get('id', f"doc_{i}"),
                    'values': doc.get('embedding', []),
                    'metadata': metadata
                }
                vectors.append(vector)
                
            except Exception as e:
                logger.error(
                    f"Error preparing document {doc.get('id', f'doc_{i}')}: {e}"
                )
                # Continue with other documents
                continue
        
        if not vectors:
            logger.error("No documents could be prepared for upsert")
            return
        
        # Report URL failures if any
        if failed_urls:
            logger.warning(
                f"⚠️  {len(failed_urls)} documents had invalid URLs and used "
                f"placeholders"
            )
        
        # Upsert in batches with error handling
        batch_size = 100
        successful_batches = 0
        failed_batches = []
        
        for i in range(0, len(vectors), batch_size):
            batch = vectors[i:i + batch_size]
            try:
                index.upsert(vectors=batch)
                successful_batches += 1
                logger.info(
                    f"✅ Upserted batch {i//batch_size + 1}/"
                    f"{(len(vectors)-1)//batch_size + 1}"
                )
            except Exception as e:
                batch_num = i//batch_size + 1
                logger.error(
                    f"❌ Failed to upsert batch {batch_num}: {e}"
                )
                failed_batches.append({
                    'batch_num': batch_num,
                    'size': len(batch),
                    'error': str(e)
                })
                # Continue with other batches
        
        # Log final results
        if failed_batches:
            logger.warning(
                f"⚠️  {len(failed_batches)} batches failed to upsert"
            )
        
        logger.info(
            f"✅ Successfully upserted {successful_batches} batches "
            f"({successful_batches * batch_size} documents)"
        )
    
    @exponential_backoff_retry(
        max_retries=3,
        initial_delay=0.5,
        max_delay=10.0,
        exceptions=(Exception,),
        raise_on_exhaust=False,
        fallback_result=[]
    )
    def query_similar(self, query_embedding: List[float],
                     top_k: int = 5) -> List[Dict]:
        """Query with graceful handling of missing URL metadata"""
        index = self.get_index()
        
        try:
            # Query Pinecone
            results = index.query(
                vector=query_embedding,
                top_k=top_k,
                include_metadata=True
            )
            
            formatted_results = []
            for match in results.get('matches', []):
                try:
                    # Ensure metadata is null-safe
                    metadata = GracefulDegradation.null_safe_metadata(
                        match.get('metadata', {})
                    )
                    
                    result = {
                        'id': match.get('id', ''),
                        'score': match.get('score', 0.0),
                        'title': metadata.get('title', ''),
                        'source': metadata.get('source', ''),
                        'category': metadata.get('category', ''),
                        'content': metadata.get('content', ''),
                        'url': metadata.get('url', ''),  # Safe default from null_safe
                        'published': metadata.get('published', '')
                    }
                    
                    # Validate URL if present
                    if result['url']:
                        validated_url = self.safe_validate_url(result['url'])
                        result['url'] = validated_url or ''
                    
                    formatted_results.append(result)
                    
                except Exception as e:
                    logger.error(
                        f"Error formatting match {match.get('id', 'unknown')}: {e}"
                    )
                    # Add result with safe defaults
                    formatted_results.append({
                        'id': match.get('id', ''),
                        'score': match.get('score', 0.0),
                        'title': 'Error retrieving metadata',
                        'source': 'Unknown',
                        'category': '',
                        'content': '',
                        'url': '',
                        'published': ''
                    })
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"Error querying Pinecone: {e}")
            raise URLRetrievalError(
                "Failed to query similar documents", original_error=e
            )
    
    def get_index_stats(self):
        """Get index statistics"""
        index = self.get_index()
        return index.describe_index_stats()
    
    def query_similar_formatted(self, query_embedding: List[float],
                               top_k: int = 5,
                               query_text: str = "",
                               include_scores: bool = False) -> Dict[str, Any]:
        """Query and format results with graceful error handling"""
        
        try:
            # Get raw results with error handling
            results = self.query_similar(query_embedding, top_k)
            
            # Handle empty or error results
            if not results:
                logger.warning("No results returned from query")
                return {
                    'summary': 'No results found.',
                    'structured_results': [],
                    'formatted_results': 'No matching documents found.',
                    'metadata': {
                        'total_results': 0,
                        'query': query_text,
                        'error': True
                    }
                }
            
            # Format using the result formatter with error handling
            try:
                return QueryResultFormatter.format_structured_response(
                    results=results,
                    query=query_text,
                    include_summary=True
                )
            except Exception as e:
                logger.error(f"Error formatting query results: {e}")
                # Return basic formatting as fallback
                return {
                    'summary': f'Found {len(results)} results.',
                    'structured_results': results,
                    'formatted_results': 'Error formatting results.',
                    'metadata': {
                        'total_results': len(results),
                        'query': query_text,
                        'formatting_error': True
                    }
                }
                
        except Exception as e:
            logger.error(f"Error in query_similar_formatted: {e}")
            return {
                'summary': 'An error occurred during search.',
                'structured_results': [],
                'formatted_results': f'Search error: {str(e)}',
                'metadata': {
                    'total_results': 0,
                    'query': query_text,
                    'error': True,
                    'error_message': str(e)
                }
            }