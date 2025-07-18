import requests
import json
from typing import List, Dict, Any, Optional
from src.utils.config import Config
import os
import re
from urllib.parse import urlparse

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
    
    def _validate_and_sanitize_url(self, url: str) -> Optional[str]:
        """Validate and sanitize URL, return None if invalid"""
        if not url or not isinstance(url, str):
            return None
        
        url = url.strip()
        if not url:
            return None
        
        # Add protocol if missing
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        try:
            parsed = urlparse(url)
            # Check if URL has valid scheme and netloc
            if parsed.scheme in ('http', 'https') and parsed.netloc:
                # Basic domain validation
                if '.' in parsed.netloc and len(parsed.netloc) > 3:
                    return url
        except Exception:
            pass
        
        return None
    
    def _format_sources_with_urls(self, citations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format citations to include URL information in a structured way"""
        formatted_sources = []
        
        for citation in citations:
            # Extract metadata from citation
            metadata = citation.get('metadata', {})
            
            formatted_source = {
                'id': citation.get('id', ''),
                'title': metadata.get('title', ''),
                'source': metadata.get('source', ''),
                'category': metadata.get('category', ''),
                'content': citation.get('text', ''),
                'url': metadata.get('url', ''),
                'published': metadata.get('published', ''),
                'score': citation.get('score', 0.0)
            }
            
            formatted_sources.append(formatted_source)
        
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
    
    def upload_documents(self, assistant_id: str, documents: List[Dict[str, Any]]) -> bool:
        """Upload documents to the assistant's knowledge base"""
        
        # Convert our document format to Pinecone Assistant format
        formatted_docs = []
        for doc in documents:
            # Validate and sanitize URL
            url = self._validate_and_sanitize_url(doc.get('url', ''))
            
            formatted_doc = {
                "id": doc.get('id', ''),
                "text": doc.get('content', ''),
                "metadata": {
                    "title": doc.get('title', ''),
                    "source": doc.get('source', ''),
                    "category": doc.get('category', ''),
                    "url": url or '',
                    "published": doc.get('published', '')
                }
            }
            formatted_docs.append(formatted_doc)
        
        try:
            # Upload in batches
            batch_size = 50
            total_uploaded = 0
            
            for i in range(0, len(formatted_docs), batch_size):
                batch = formatted_docs[i:i + batch_size]
                
                response = requests.post(
                    f"{self.host}/assistants/{assistant_id}/files",
                    headers=self.headers,
                    json={"documents": batch}
                )
                
                if response.status_code in [200, 201]:
                    total_uploaded += len(batch)
                    print(f"✅ Uploaded batch {i//batch_size + 1}: {len(batch)} documents")
                else:
                    print(f"❌ Failed to upload batch {i//batch_size + 1}: {response.status_code} - {response.text}")
                    return False
            
            print(f"✅ Successfully uploaded {total_uploaded} documents to assistant {assistant_id}")
            return True
            
        except Exception as e:
            print(f"❌ Error uploading documents: {e}")
            return False
    
    def query_assistant(self, assistant_id: str, question: str, 
                       include_metadata: bool = True) -> Dict[str, Any]:
        """Query the assistant with a question"""
        
        query_data = {
            "message": question,
            "include_metadata": include_metadata,
            "stream": False
        }
        
        try:
            response = requests.post(
                f"{self.host}/assistants/{assistant_id}/chat",
                headers=self.headers,
                json=query_data
            )
            
            if response.status_code == 200:
                result = response.json()
                
                # Extract and format sources with URL information
                formatted_sources = self._format_sources_with_urls(result.get('citations', []))
                
                return {
                    'answer': result.get('message', ''),
                    'sources': formatted_sources,
                    'metadata': result.get('metadata', {})
                }
            else:
                print(f"❌ Query failed: {response.status_code} - {response.text}")
                return {'answer': 'Sorry, I encountered an error processing your question.', 'sources': []}
                
        except Exception as e:
            print(f"❌ Error querying assistant: {e}")
            return {'answer': 'Sorry, I encountered an error processing your question.', 'sources': []}
    
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