#!/usr/bin/env python3
"""
Result formatting utilities for query responses with URL metadata support
"""

from typing import List, Dict, Any, Optional
from urllib.parse import urlparse
import re


class QueryResultFormatter:
    """Formats query results with URL metadata support"""
    
    @staticmethod
    def format_single_result(result: Dict[str, Any], include_score: bool = False) -> str:
        """Format a single query result with URL metadata"""
        
        # Extract basic information
        title = result.get('title', 'Untitled')
        content = result.get('content', '')
        source = result.get('source', 'Unknown Source')
        url = result.get('url', '')
        score = result.get('score', 0.0)
        published = result.get('published', '')
        
        # Start building the formatted result
        formatted_result = f"**{title}**\n\n"
        
        # Add content
        if content:
            # Truncate content if too long for display
            display_content = content[:500] + "..." if len(content) > 500 else content
            formatted_result += f"{display_content}\n\n"
        
        # Add source attribution with URL if available
        source_line = QueryResultFormatter._format_source_attribution(source, url, published)
        formatted_result += source_line
        
        # Add relevance score if requested
        if include_score and score > 0:
            formatted_result += f"\n*Relevance: {score:.3f}*"
        
        return formatted_result
    
    @staticmethod
    def format_multiple_results(results: List[Dict[str, Any]], 
                              include_scores: bool = False,
                              max_results: Optional[int] = None) -> str:
        """Format multiple query results with clear source separation"""
        
        if not results:
            return "No relevant information found."
        
        # Limit results if specified
        if max_results:
            results = results[:max_results]
        
        formatted_results = []
        
        for i, result in enumerate(results, 1):
            # Format individual result
            single_result = QueryResultFormatter.format_single_result(result, include_scores)
            
            # Add result number for multiple results or when max_results is applied
            if len(results) > 1 or max_results:
                formatted_results.append(f"## Result {i}\n\n{single_result}")
            else:
                formatted_results.append(single_result)
        
        return "\n\n---\n\n".join(formatted_results)
    
    @staticmethod
    def format_structured_response(results: List[Dict[str, Any]], 
                                 query: str = "",
                                 include_summary: bool = True) -> Dict[str, Any]:
        """Create a structured response format for API consumption"""
        
        # Separate results with and without URLs
        results_with_urls = [r for r in results if r.get('url')]
        results_without_urls = [r for r in results if not r.get('url')]
        
        response = {
            'query': query,
            'total_results': len(results),
            'results_with_sources': len(results_with_urls),
            'results_without_sources': len(results_without_urls),
            'formatted_response': QueryResultFormatter.format_multiple_results(results),
            'sources': QueryResultFormatter._extract_unique_sources(results),
            'results': results
        }
        
        if include_summary:
            response['summary'] = QueryResultFormatter._generate_result_summary(results)
        
        return response
    
    @staticmethod
    def _format_source_attribution(source: str, url: str, published: str = "") -> str:
        """Format source attribution with URL if available"""
        
        # Validate URL
        valid_url = QueryResultFormatter._validate_url(url)
        
        if valid_url:
            # Create clickable link
            source_line = f"*Source: [{source}]({valid_url})*"
        else:
            # Fallback to source name only
            source_line = f"*Source: {source}*"
        
        # Add publication date if available
        if published:
            source_line += f" | *Published: {published}*"
        
        return source_line
    
    @staticmethod
    def _validate_url(url: str) -> Optional[str]:
        """Validate URL format and return cleaned URL or None"""
        
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
    
    @staticmethod
    def _extract_unique_sources(results: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """Extract unique sources with their URLs"""
        
        sources = {}
        
        for result in results:
            source_name = result.get('source', 'Unknown Source')
            url = result.get('url', '')
            
            if source_name not in sources:
                sources[source_name] = {
                    'name': source_name,
                    'url': QueryResultFormatter._validate_url(url) or '',
                    'count': 1
                }
            else:
                sources[source_name]['count'] += 1
                # Update URL if current result has one and stored doesn't
                if not sources[source_name]['url'] and url:
                    sources[source_name]['url'] = QueryResultFormatter._validate_url(url) or ''
        
        return list(sources.values())
    
    @staticmethod
    def _generate_result_summary(results: List[Dict[str, Any]]) -> str:
        """Generate a summary of the results"""
        
        if not results:
            return "No results found."
        
        total = len(results)
        with_urls = len([r for r in results if r.get('url')])
        without_urls = total - with_urls
        
        summary = f"Found {total} relevant result{'s' if total != 1 else ''}."
        
        if with_urls > 0:
            summary += f" {with_urls} result{'s' if with_urls != 1 else ''} include{'s' if with_urls == 1 else ''} source links."
        
        if without_urls > 0:
            summary += f" {without_urls} result{'s' if without_urls != 1 else ''} from internal sources."
        
        return summary


class MCPResponseFormatter:
    """Specialized formatter for MCP tool responses"""
    
    @staticmethod
    def format_for_mcp(results: List[Dict[str, Any]], query: str = "") -> Dict[str, Any]:
        """Format results for MCP tool response"""
        
        if not results:
            return {
                'content': [{
                    'type': 'text',
                    'text': 'No relevant information found in the Bitcoin knowledge base.'
                }]
            }
        
        # Create formatted response
        formatted_text = QueryResultFormatter.format_multiple_results(results, include_scores=True)
        
        # Add query context if provided
        if query:
            formatted_text = f"**Query:** {query}\n\n---\n\n{formatted_text}"
        
        # Add source summary
        sources = QueryResultFormatter._extract_unique_sources(results)
        if sources:
            source_summary = "\n\n## Sources Referenced\n\n"
            for source in sources:
                if source['url']:
                    source_summary += f"- [{source['name']}]({source['url']}) ({source['count']} result{'s' if source['count'] != 1 else ''})\n"
                else:
                    source_summary += f"- {source['name']} ({source['count']} result{'s' if source['count'] != 1 else ''})\n"
            
            formatted_text += source_summary
        
        return {
            'content': [{
                'type': 'text',
                'text': formatted_text
            }],
            'metadata': {
                'total_results': len(results),
                'sources_with_urls': len([s for s in sources if s['url']]),
                'query': query
            }
        }


class AssistantResponseFormatter:
    """Specialized formatter for Pinecone Assistant responses"""
    
    @staticmethod
    def format_assistant_response(answer: str, sources: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Format Pinecone Assistant response with enhanced source display"""
        
        if not sources:
            return {
                'answer': answer,
                'sources': [],
                'formatted_sources': "No sources available."
            }
        
        # Format sources with URLs
        formatted_sources = []
        source_text = "## Sources\n\n"
        
        for i, source in enumerate(sources, 1):
            title = source.get('title', 'Untitled')
            source_name = source.get('source', 'Unknown Source')
            url = source.get('url', '')
            content = source.get('content', '')
            
            # Create source entry
            source_entry = f"{i}. **{title}**"
            
            # Add source attribution with URL
            if QueryResultFormatter._validate_url(url):
                source_entry += f"\n   *Source: [{source_name}]({url})*"
            else:
                source_entry += f"\n   *Source: {source_name}*"
            
            # Add content preview if available
            if content:
                preview = content[:200] + "..." if len(content) > 200 else content
                source_entry += f"\n   {preview}"
            
            formatted_sources.append({
                'index': i,
                'title': title,
                'source': source_name,
                'url': QueryResultFormatter._validate_url(url),
                'content_preview': content[:200] if content else ''
            })
            
            source_text += source_entry + "\n\n"
        
        return {
            'answer': answer,
            'sources': sources,
            'formatted_sources': source_text.strip(),
            'source_summary': QueryResultFormatter._generate_result_summary(sources),
            'structured_sources': formatted_sources
        }