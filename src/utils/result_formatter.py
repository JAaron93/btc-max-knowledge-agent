#!/usr/bin/env python3
"""
Result formatting utilities for query responses with URL metadata support
"""

from functools import wraps
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urlparse


class ValidationError(Exception):
    """Custom exception for validation errors"""

    pass


class ResultValidator:
    """Validator for result dictionary structures"""

    # Define expected schema for result dictionaries
    RESULT_SCHEMA = {
        "title": {"type": str, "required": False, "default": "Untitled"},
        "content": {"type": str, "required": False, "default": ""},
        "source": {"type": str, "required": False, "default": "Unknown Source"},
        "url": {"type": str, "required": False, "default": ""},
        "score": {"type": (int, float), "required": False, "default": 0.0},
        "published": {"type": str, "required": False, "default": ""},
    }

    SOURCE_SCHEMA = {
        "name": {"type": str, "required": True},
        "url": {"type": str, "required": False, "default": ""},
        "count": {"type": int, "required": False, "default": 1},
    }

    @staticmethod
    def validate_result_dict(
        result: Dict[str, Any], strict: bool = False
    ) -> Dict[str, Any]:
        """Validate and normalize a single result dictionary

        Args:
            result: Dictionary to validate
            strict: If True, raise exception on validation errors. If False, apply defaults.

        Returns:
            Validated and normalized dictionary

        Raises:
            ValidationError: If strict=True and validation fails
        """
        if not isinstance(result, dict):
            if strict:
                raise ValidationError(f"Expected dict, got {type(result).__name__}")
            return {
                "title": "Invalid Result",
                "content": "",
                "source": "Unknown Source",
                "url": "",
                "score": 0.0,
                "published": "",
            }

        validated_result = result.copy()

        for field, schema in ResultValidator.RESULT_SCHEMA.items():
            value = result.get(field)
            expected_type = schema["type"]
            required = schema.get("required", False)
            default = schema.get("default")

            # Check if required field is missing
            if required and (value is None or value == ""):
                if strict:
                    raise ValidationError(
                        f"Required field '{field}' is missing or empty"
                    )
                validated_result[field] = default
                continue

            # Apply default if field is missing
            if value is None:
                validated_result[field] = default
                continue

            # Type validation
            if not isinstance(value, expected_type):
                if strict:
                    raise ValidationError(
                        f"Field '{field}' expected {expected_type}, got {type(value).__name__}"
                    )
                # Try to convert or use default
                try:
                    if expected_type is str:
                        validated_result[field] = str(value)
                    elif expected_type in ((int, float), float, int):
                        validated_result[field] = (
                            float(value) if "." in str(value) else int(value)
                        )
                    else:
                        validated_result[field] = default
                except (ValueError, TypeError):
                    validated_result[field] = default

        return validated_result

    @staticmethod
    def validate_result_list(
        results: List[Dict[str, Any]], strict: bool = False
    ) -> List[Dict[str, Any]]:
        """Validate a list of result dictionaries

        Args:
            results: List of dictionaries to validate
            strict: If True, raise exception on validation errors

        Returns:
            List of validated dictionaries
        """
        if not isinstance(results, list):
            if strict:
                raise ValidationError(f"Expected list, got {type(results).__name__}")
            return []

        validated_results = []
        for i, result in enumerate(results):
            try:
                validated_result = ResultValidator.validate_result_dict(
                    result, strict=strict
                )
                validated_results.append(validated_result)
            except ValidationError as e:
                if strict:
                    raise ValidationError(f"Validation error at index {i}: {str(e)}")
                # Skip invalid results in non-strict mode
                continue

        return validated_results


def validate_input(*validation_specs):
    """Decorator for input validation

    Args:
        validation_specs: Tuples of (param_name, validator_function, strict_mode)
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Get function signature to map args to parameter names
            import inspect

            sig = inspect.signature(func)
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()

            # Apply validations
            for param_name, validator, strict in validation_specs:
                if param_name in bound_args.arguments:
                    value = bound_args.arguments[param_name]
                    try:
                        validated_value = validator(value, strict=strict)
                        bound_args.arguments[param_name] = validated_value
                    except ValidationError as e:
                        # Log validation error or handle as needed
                        if strict:
                            raise ValidationError(
                                f"Validation failed for parameter '{param_name}': {str(e)}"
                            )
                        # In non-strict mode, continue with original value

            return func(*bound_args.args, **bound_args.kwargs)

        return wrapper

    return decorator


class QueryResultFormatter:
    """Formats query results with URL metadata support"""

    @staticmethod
    @validate_input(("result", ResultValidator.validate_result_dict, False))
    def format_single_result(
        result: Dict[str, Any], include_score: bool = False
    ) -> str:
        """Format a single query result with URL metadata

        Args:
            result: Dictionary containing result data (validated automatically)
            include_score: Whether to include relevance score in output

        Returns:
            Formatted string representation of the result
        """

        # Extract basic information
        title = result.get("title", "Untitled")
        content = result.get("content", "")
        source = result.get("source", "Unknown Source")
        url = result.get("url", "")
        score = result.get("score", 0.0)
        published = result.get("published", "")

        # Start building the formatted result
        formatted_result = f"**{title}**\n\n"

        # Add content
        if content:
            # Truncate content if too long for display
            display_content = content[:500] + "..." if len(content) > 500 else content
            formatted_result += f"{display_content}\n\n"

        # Add source attribution with URL if available
        source_line = QueryResultFormatter._format_source_attribution(
            source, url, published
        )
        formatted_result += source_line

        # Add relevance score if requested
        if include_score and score > 0:
            formatted_result += f"\n*Relevance: {score:.3f}*"

        return formatted_result

    @staticmethod
    @validate_input(("results", ResultValidator.validate_result_list, False))
    def format_multiple_results(
        results: List[Dict[str, Any]],
        include_scores: bool = False,
        max_results: Optional[int] = None,
    ) -> str:
        """Format multiple query results with clear source separation

        Args:
            results: List of result dictionaries (validated automatically)
            include_scores: Whether to include relevance scores
            max_results: Maximum number of results to format

        Returns:
            Formatted string representation of all results
        """

        if not results:
            return "No relevant information found."

        # Limit results if specified
        if max_results:
            results = results[:max_results]

        formatted_results = []

        for i, result in enumerate(results, 1):
            # Format individual result
            single_result = QueryResultFormatter.format_single_result(
                result, include_score=include_scores
            )

            # Add result number for multiple results or when max_results is applied
            if len(results) > 1 or max_results:
                formatted_results.append(f"## Result {i}\n\n{single_result}")
            else:
                formatted_results.append(single_result)

        return "\n\n---\n\n".join(formatted_results)

    @staticmethod
    @validate_input(("results", ResultValidator.validate_result_list, False))
    def format_structured_response(
        results: List[Dict[str, Any]], query: str = "", include_summary: bool = True
    ) -> Dict[str, Any]:
        """Create a structured response format for API consumption

        Args:
            results: List of result dictionaries (validated automatically)
            query: Query string for context
            include_summary: Whether to include result summary

        Returns:
            Structured response dictionary
        """

        # Separate results with and without URLs
        results_with_urls = [r for r in results if r.get("url")]
        results_without_urls = [r for r in results if not r.get("url")]

        response = {
            "query": query,
            "total_results": len(results),
            "results_with_sources": len(results_with_urls),
            "results_without_sources": len(results_without_urls),
            "formatted_response": QueryResultFormatter.format_multiple_results(results),
            "sources": QueryResultFormatter._extract_unique_sources(results),
            "results": results,
        }

        if include_summary:
            response["summary"] = QueryResultFormatter._generate_result_summary(results)

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
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        try:
            parsed = urlparse(url)
            # Check if URL has valid scheme and netloc
            if parsed.scheme in ("http", "https") and parsed.netloc:
                # Basic domain validation
                if "." in parsed.netloc and len(parsed.netloc) > 3:
                    return url
        except (ValueError, AttributeError):
            # Log the error if logging is available
            pass

        return None

    @staticmethod
    def _extract_unique_sources(results: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """Extract unique sources with their URLs"""

        sources = {}

        for result in results:
            source_name = result.get("source", "Unknown Source")
            url = result.get("url", "")

            if source_name not in sources:
                sources[source_name] = {
                    "name": source_name,
                    "url": QueryResultFormatter._validate_url(url) or "",
                    "count": 1,
                }
            else:
                sources[source_name]["count"] += 1
                # Update URL if current result has one and stored doesn't
                if not sources[source_name]["url"] and url:
                    sources[source_name]["url"] = (
                        QueryResultFormatter._validate_url(url) or ""
                    )

        return list(sources.values())

    @staticmethod
    def _generate_result_summary(results: List[Dict[str, Any]]) -> str:
        """Generate a summary of the results"""

        if not results:
            return "No results found."

        total = len(results)
        with_urls = len([r for r in results if r.get("url")])
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
    @validate_input(("results", ResultValidator.validate_result_list, False))
    def format_for_mcp(
        results: List[Dict[str, Any]],
        query: str = "",
        empty_message: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Format results for MCP tool response

        Args:
            results: List of search results to format (validated automatically)
            query: Optional query string to include in the response
            empty_message: Optional custom message for empty results.
                          Defaults to "No relevant information found in the Bitcoin knowledge base."

        Returns:
            Dict containing formatted MCP response
        """

        if not results:
            default_message = (
                "No relevant information found in the Bitcoin knowledge base."
            )
            message_text = (
                empty_message if empty_message is not None else default_message
            )
            return {"content": [{"type": "text", "text": message_text}]}

        # Create formatted response
        formatted_text = QueryResultFormatter.format_multiple_results(
            results, include_scores=True
        )

        # Add query context if provided
        if query:
            formatted_text = f"**Query:** {query}\n\n---\n\n{formatted_text}"

        # Add source summary
        sources = QueryResultFormatter._extract_unique_sources(results)
        if sources:
            source_summary = "\n\n## Sources Referenced\n\n"
            for source in sources:
                if source["url"]:
                    source_summary += f"- [{source['name']}]({source['url']}) ({source['count']} result{'s' if source['count'] != 1 else ''})\n"
                else:
                    source_summary += f"- {source['name']} ({source['count']} result{'s' if source['count'] != 1 else ''})\n"

            formatted_text += source_summary

        return {
            "content": [{"type": "text", "text": formatted_text}],
            "metadata": {
                "total_results": len(results),
                "sources_with_urls": len([s for s in sources if s["url"]]),
                "query": query,
            },
        }


class AssistantResponseFormatter:
    """Specialized formatter for Pinecone Assistant responses"""

    @staticmethod
    @validate_input(("sources", ResultValidator.validate_result_list, False))
    def format_assistant_response(
        answer: str, sources: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Format Pinecone Assistant response with enhanced source display

        Args:
            answer: The main response text
            sources: List of source dictionaries (validated automatically)

        Returns:
            Dict containing formatted assistant response with source metadata
        """

        if not sources:
            return {
                "answer": answer,
                "sources": [],
                "formatted_sources": "No sources available.",
            }

        # Format sources with URLs
        formatted_sources = []
        source_text = "## Sources\n\n"

        for i, source in enumerate(sources, 1):
            title = source.get("title", "Untitled")
            source_name = source.get("source", "Unknown Source")
            url = source.get("url", "")
            content = source.get("content", "")

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

            formatted_sources.append(
                {
                    "index": i,
                    "title": title,
                    "source": source_name,
                    "url": QueryResultFormatter._validate_url(url),
                    "content_preview": content[:200] if content else "",
                }
            )

            source_text += source_entry + "\n\n"

        return {
            "answer": answer,
            "sources": sources,
            "formatted_sources": source_text.strip(),
            "source_summary": QueryResultFormatter._generate_result_summary(sources),
            "structured_sources": formatted_sources,
        }
