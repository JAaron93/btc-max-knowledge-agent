import logging
import os
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests

from btc_max_knowledge_agent.monitoring.url_metadata_monitor import record_upload
from btc_max_knowledge_agent.utils.config import Config
from btc_max_knowledge_agent.utils.result_formatter import AssistantResponseFormatter
from btc_max_knowledge_agent.utils.url_error_handler import (
    FallbackURLStrategy,
    GracefulDegradation,
    URLMetadataUploadError,
    URLValidationError,
    exponential_backoff_retry,
    retry_url_upload,
)

# Import our logging infrastructure
from btc_max_knowledge_agent.utils.url_metadata_logger import (
    correlation_context,
    generate_correlation_id,
    log_upload,
)

logger = logging.getLogger(__name__)


class PineconeAssistantAgent:
    def __init__(self):
        self.api_key = Config.PINECONE_API_KEY
        self.host = os.getenv("PINECONE_ASSISTANT_HOST")

        if not self.host or self.host == "YOUR_PINECONE_ASSISTANT_HOST_HERE":
            raise ValueError(
                "PINECONE_ASSISTANT_HOST not configured. Run setup_pinecone_assistant.py first."
            )

        self.headers = {"Api-Key": self.api_key, "Content-Type": "application/json"}

        # Remove trailing slash if present
        self.host = self.host.rstrip("/")

    def _validate_and_sanitize_url(self, url: str) -> Optional[str]:
        """Validate and sanitize URL with deterministic validation

        Args:
            url: The URL to validate and sanitize

        Returns:
            str: The sanitized URL if valid
            None: If the URL is invalid or cannot be sanitized
        """
        if not url or not isinstance(url, str):
            return None

        url = url.strip()
        if not url:
            return None

        # Add protocol if missing
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        try:
            parsed = urlparse(url)
            # Check if URL has valid scheme and netloc
            if parsed.scheme in ("http", "https") and parsed.netloc:
                # Basic domain validation - require at least one dot in the domain
                # but exclude trailing dots
                domain = parsed.netloc.rstrip(".")
                if "." in domain:
                    return url

        except ValueError as e:
            # Handle specific URL parsing errors
            logger.debug(f"URL parsing failed for '{url}': {e}")
            return None
        except Exception as e:
            # Log unexpected errors but don't fail the entire operation
            logger.warning(
                f"Unexpected error validating URL '{url}': {e}", exc_info=True
            )
            return None

        return None

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

    def build_upload_payload(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        """
        Centralised builder for Pinecone upload payloads.

        1. Validates & sanitises the doc['url'] via self._safe_validate_url.
        2. Wraps/normalises metadata with GracefulDegradation.null_safe_metadata.
        3. Returns the payload dict identical to what inline code built previously.

        Args:
            doc: Document dictionary containing id, content, url, title, source, category, published

        Returns:
            Dict[str, Any]: Formatted document payload ready for Pinecone upload
            
        Raises:
            ValueError: If doc is None or missing required fields
            Exception: Re-raises any unexpected errors during payload construction
        """
        if doc is None:
            raise ValueError("Document cannot be None")
        
        if not isinstance(doc, dict):
            raise ValueError("Document must be a dictionary")
        
        # Check for required fields
        required_fields = ["id", "content"]
        for field in required_fields:
            if field not in doc:
                raise ValueError(f"Document missing required field '{field}'")
        
        try:
            # Safely validate URL without blocking document upload
            url = self._safe_validate_url(doc.get("url", ""))
            
            if not url and doc.get("url"):
                # URL was provided but validation failed - log warning but continue
                logger.warning(
                    f"URL validation failed for doc {doc.get('id')}, using empty string"
                )
                url = ""
            
            # Ensure metadata is null-safe by converting None values to empty strings
            raw_metadata = {
                "title": doc.get("title", ""),
                "source": doc.get("source", ""),
                "category": doc.get("category", ""),
                "url": url or "",
                "published": doc.get("published", ""),
            }
            
            # Convert None values to empty strings for all fields
            for key, value in raw_metadata.items():
                if value is None:
                    raw_metadata[key] = ""
            
            # Apply null-safe metadata processing (handles URL-related fields)
            metadata = GracefulDegradation.null_safe_metadata(raw_metadata)
            
            # Build the formatted document payload
            formatted_doc = {
                "id": doc.get("id", ""),
                "text": doc.get("content", ""),
                "metadata": metadata,
            }
            
            return formatted_doc
            
        except Exception as e:
            logger.error(
                f"Error formatting document {doc.get('id', 'unknown')}: {e}"
            )
            # Re-raise to maintain existing error handling semantics
            raise

    def _format_sources_with_urls(
        self, citations: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Format citations with graceful handling of missing URL metadata"""
        formatted_sources = []

        for citation in citations:
            try:
                # Extract metadata with null-safe approach
                metadata = GracefulDegradation.null_safe_metadata(
                    citation.get("metadata", {})
                )

                formatted_source = {
                    "id": citation.get("id", ""),
                    "title": metadata.get("title", ""),
                    "source": metadata.get("source", ""),
                    "category": metadata.get("category", ""),
                    "content": citation.get("text", ""),
                    "url": metadata.get(
                        "url", ""
                    ),  # Safe default from null_safe_metadata
                    "published": metadata.get("published", ""),
                    "score": citation.get("score", 0.0),
                }

                # Validate URL if present
                if formatted_source["url"]:
                    validated_url = self._safe_validate_url(formatted_source["url"])
                    formatted_source["url"] = validated_url or ""

                formatted_sources.append(formatted_source)

            except Exception as e:
                logger.error(
                    f"Error formatting citation {citation.get('id', 'unknown')}: {e}"
                )
                # Add citation with safe defaults even if formatting fails
                formatted_sources.append(
                    {
                        "id": citation.get("id", ""),
                        "title": "Error retrieving title",
                        "source": "Unknown",
                        "category": "",
                        "content": citation.get("text", ""),
                        "url": "",
                        "published": "",
                        "score": 0.0,
                    }
                )

        return formatted_sources

    def create_assistant(
        self, name: str = "Bitcoin Knowledge Assistant"
    ) -> Dict[str, Any]:
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
                "created_by": "btc-max-knowledge-agent",
            },
        }

        try:
            response = requests.post(
                f"{self.host}/assistants", headers=self.headers, json=assistant_config
            )

            if response.status_code == 201:
                assistant = response.json()
                print(
                    f"✅ Created assistant: {assistant.get('name')} (ID: {assistant.get('id')})"
                )
                return assistant
            else:
                print(
                    f"❌ Failed to create assistant: {response.status_code} - {response.text}"
                )
                return {}

        except Exception as e:
            print(f"❌ Error creating assistant: {e}")
            return {}

    def list_assistants(self) -> List[Dict[str, Any]]:
        """List all available assistants"""
        try:
            response = requests.get(f"{self.host}/assistants", headers=self.headers)

            if response.status_code == 200:
                assistants = response.json().get("assistants", [])
                print(f"📋 Found {len(assistants)} assistants")
                for assistant in assistants:
                    print(f"  - {assistant.get('name')} (ID: {assistant.get('id')})")
                return assistants
            else:
                print(
                    f"❌ Failed to list assistants: {response.status_code} - {response.text}"
                )
                return []

        except Exception as e:
            print(f"❌ Error listing assistants: {e}")
            return []

    def upload_documents(
        self, assistant_id: str, documents: List[Dict[str, Any]]
    ) -> bool:
        """Upload documents with null-safe operations and graceful URL handling"""
        
        # Validate input parameters
        if documents is None:
            raise ValueError("Documents parameter cannot be None")
        
        if not isinstance(documents, list):
            raise ValueError("Documents must be a list")
        
        if not documents:
            raise ValueError("Documents list cannot be empty")
        
        # Validate document format
        for i, doc in enumerate(documents):
            if not isinstance(doc, dict):
                raise ValueError(f"Document at index {i} must be a dictionary")
            
            # Check for required fields
            required_fields = ["id", "content"]
            for field in required_fields:
                if field not in doc:
                    raise ValueError(f"Document at index {i} missing required field '{field}'")

        # Track successful and failed operations
        successful_docs = []
        failed_urls = []

        # Convert our document format to Pinecone Assistant format
        for doc in documents:
            try:
                payload = self.build_upload_payload(doc)
                
                # Track URL validation failures for reporting
                if not payload["metadata"].get("url") and doc.get("url"):
                    failed_urls.append(
                        {
                            "doc_id": doc.get("id", "unknown"),
                            "original_url": doc.get("url", ""),
                        }
                    )
                
                successful_docs.append(payload)

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
        try:
            return self._upload_documents_with_retry(
                assistant_id, successful_docs, failed_urls
            )
        except URLMetadataUploadError as e:
            logger.error(f"Failed to upload documents: {e}")
            return False

    @retry_url_upload
    def _upload_documents_with_retry(
        self,
        assistant_id: str,
        formatted_docs: List[Dict[str, Any]],
        failed_urls: List[Dict[str, str]],
    ) -> bool:
        """Upload documents in batches with retry logic"""
        # Create a correlation ID for this upload operation
        correlation_id = generate_correlation_id()

        with correlation_context(correlation_id):
            try:
                # Upload in batches
                batch_size = int(os.getenv("PINECONE_UPLOAD_BATCH_SIZE", "50"))
                total_uploaded = 0
                failed_batches = []

                for i in range(0, len(formatted_docs), batch_size):
                    batch = formatted_docs[i : i + batch_size]
                    start_time = time.time()

                    try:
                        response = requests.post(
                            f"{self.host}/assistants/{assistant_id}/files",
                            headers=self.headers,
                            json={"documents": batch},
                        )

                        duration_ms = (time.time() - start_time) * 1000

                        if response.status_code in [200, 201]:
                            total_uploaded += len(batch)

                            # Log successful upload for each document
                            for doc in batch:
                                log_upload(
                                    url=doc.get("metadata", {}).get("url", ""),
                                    success=True,
                                    metadata_size=len(str(doc.get("metadata", {}))),
                                    duration_ms=duration_ms,
                                )
                                record_upload(
                                    url=doc.get("metadata", {}).get("url", ""),
                                    success=True,
                                    duration_ms=duration_ms,
                                    metadata_size=len(str(doc.get("metadata", {}))),
                                    correlation_id=correlation_id,
                                )

                            logger.info(
                                f"✅ Uploaded batch {i//batch_size + 1}: "
                                f"{len(batch)} documents"
                            )
                        else:
                            error_msg = (
                                f"Batch {i//batch_size + 1} upload "
                                f"failed: {response.status_code}"
                            )
                            logger.error(f"❌ {error_msg} - {response.text}")

                            # Log failed upload for each document
                            for doc in batch:
                                log_upload(
                                    url=doc.get("metadata", {}).get("url", ""),
                                    success=False,
                                    metadata_size=len(str(doc.get("metadata", {}))),
                                    error=f"HTTP {response.status_code}",
                                    duration_ms=duration_ms,
                                )
                                record_upload(
                                    url=doc.get("metadata", {}).get("url", ""),
                                    success=False,
                                    duration_ms=duration_ms,
                                    metadata_size=len(str(doc.get("metadata", {}))),
                                    error_type=f"http_{response.status_code}",
                                    correlation_id=correlation_id,
                                )

                            failed_batches.append(
                                {
                                    "batch_num": i // batch_size + 1,
                                    "size": len(batch),
                                    "error": error_msg,
                                }
                            )
                            # Continue with other batches

                    except requests.exceptions.RequestException as e:
                        duration_ms = (time.time() - start_time) * 1000
                        error_msg = (
                            f"Network error uploading batch " f"{i//batch_size + 1}"
                        )
                        logger.error(f"❌ {error_msg}: {e}")

                        # Log failed upload for each document in batch
                        for doc in batch:
                            log_upload(
                                url=doc.get("metadata", {}).get("url", ""),
                                success=False,
                                metadata_size=len(str(doc.get("metadata", {}))),
                                error=str(e),
                                duration_ms=duration_ms / len(batch),
                            )
                            record_upload(
                                url=doc.get("metadata", {}).get("url", ""),
                                success=False,
                                duration_ms=duration_ms / len(batch),
                                metadata_size=len(str(doc.get("metadata", {}))),
                                error_type="network_error",
                                correlation_id=correlation_id,
                            )

                        failed_batches.append(
                            {
                                "batch_num": i // batch_size + 1,
                                "size": len(batch),
                                "error": str(e),
                            }
                        )
                        # Continue with other batches

                # Report results
                if failed_urls:
                    logger.warning(
                        f"⚠️  {len(failed_urls)} documents had invalid URLs "
                        f"and used placeholders"
                    )

                if failed_batches:
                    logger.warning(f"⚠️  {len(failed_batches)} batches failed to upload")

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
                    original_error=e,
                )

    @exponential_backoff_retry(
        max_retries=3,
        initial_delay=1.0,
        max_delay=10.0,
        exceptions=(requests.exceptions.RequestException, ConnectionError),
        raise_on_exhaust=False,
        fallback_result=None,
    )
    def query_assistant(
        self,
        assistant_id: str,
        question: str,
        include_metadata: bool = True,
        timeout: float | int | None = None,
        **_ignored: Any,
    ) -> Dict[str, Any]:
        """Query assistant with graceful error handling and URL metadata safety"""

        query_data = {
            "message": question,
            "include_metadata": include_metadata,
            "stream": False,
        }

        try:
            response = requests.post(
                f"{self.host}/assistants/{assistant_id}/chat",
                headers=self.headers,
                json=query_data,
                timeout=timeout or 30,
            )

            if response.status_code == 200:
                result = response.json()

                # Extract and format sources with graceful URL handling
                try:
                    formatted_sources = self._format_sources_with_urls(
                        result.get("citations", [])
                    )
                except Exception as e:
                    logger.error(f"Error formatting sources: {e}")
                    formatted_sources = []

                # Use the AssistantResponseFormatter with error handling
                try:
                    formatted_response = (
                        AssistantResponseFormatter.format_assistant_response(
                            answer=result.get("message", ""), sources=formatted_sources
                        )
                    )
                except Exception as e:
                    logger.error(f"Error in response formatter: {e}")
                    # Provide minimal formatting as fallback
                    formatted_response = {
                        "formatted_sources": "Error formatting sources.",
                        "source_summary": f"Found {len(formatted_sources)} sources.",
                        "structured_sources": formatted_sources,
                    }

                # Return response with all safety measures
                return {
                    "answer": result.get("message", ""),
                    "sources": formatted_sources,
                    "formatted_sources": formatted_response.get(
                        "formatted_sources", "No sources available."
                    ),
                    "source_summary": formatted_response.get(
                        "source_summary", "No sources found."
                    ),
                    "structured_sources": formatted_response.get(
                        "structured_sources", []
                    ),
                    "metadata": result.get("metadata", {}),
                }
            else:
                logger.error(f"Query failed: {response.status_code} - {response.text}")
                return self._create_error_response(
                    "I encountered an error while processing your request"
                )

        except Exception as e:
            logger.error(f"Error querying assistant: {e}")
            return self._create_error_response(
                "I encountered an error while processing your question."
            )

    def _create_error_response(self, error_message: str) -> Dict[str, Any]:
        """Create a consistent error response structure"""
        # Only prepend 'Sorry, ' if the error message doesn't already start with it
        if not error_message.strip().startswith("Sorry"):
            answer = f"Sorry, {error_message}"
        else:
            answer = error_message

        return {
            "answer": answer,
            "sources": [],
            "formatted_sources": "No sources available.",
            "source_summary": "No sources found.",
            "structured_sources": [],
            "metadata": {},
        }

    def get_assistant_info(self, assistant_id: str) -> Dict[str, Any]:
        """Get information about a specific assistant"""
        try:
            response = requests.get(
                f"{self.host}/assistants/{assistant_id}", headers=self.headers
            )

            if response.status_code == 200:
                return response.json()
            else:
                print(
                    f"❌ Failed to get assistant info: {response.status_code} - {response.text}"
                )
                return {}

        except Exception as e:
            print(f"❌ Error getting assistant info: {e}")
            return {}
