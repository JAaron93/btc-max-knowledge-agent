#!/usr/bin/env python3
"""
Clean and format MCP response text using regex and URL metadata support
"""

import copy
import json
import re

# Import the new result formatter
try:
    from src.utils.result_formatter import MCPResponseFormatter
except ImportError:
    # Fallback if import fails
    MCPResponseFormatter = None


def clean_text_content(text):
    """Clean text content using regex patterns"""

    # Remove excessive whitespace and normalize line breaks
    text = re.sub(r"\r\n", "\n", text)  # Convert Windows line endings
    text = re.sub(r"\r", "\n", text)  # Convert old Mac line endings

    # Fix common PDF extraction issues
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)  # Add space between camelCase
    text = re.sub(r"([a-z])(\d)", r"\1 \2", text)  # Add space between letter and number
    text = re.sub(r"(\d)([A-Z])", r"\1 \2", text)  # Add space between number and letter

    # Fix hyphenated words split across lines
    text = re.sub(r"([a-z])-\s*\n\s*([a-z])", r"\1\2", text)

    # Remove excessive spaces
    text = re.sub(r" {2,}", " ", text)

    # Fix paragraph breaks
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Remove trailing whitespace from lines
    text = re.sub(r"[ \t]+$", "", text, flags=re.MULTILINE)

    # Fix broken words at line endings (common in PDFs)
    text = re.sub(r"([a-z])\s*\n\s*([a-z])", r"\1\2", text)

    # Fix spacing around punctuation
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = re.sub(r"([,.;:!?])([A-Za-z])", r"\1 \2", text)

    # Fix common PDF text extraction issues
    text = re.sub(r"([a-z])([A-Z][a-z])", r"\1 \2", text)  # camelCase fixes
    text = re.sub(r"(\w)(\d+)", r"\1 \2", text)  # word-number spacing
    text = re.sub(r"(\d+)([A-Za-z])", r"\1 \2", text)  # number-word spacing

    # Fix common encoding issues
    text = re.sub(r"â\x80\x99", "'", text)  # Fix apostrophes
    text = re.sub(r"â\x80\x9c", '"', text)  # Fix opening quotes
    text = re.sub(r"â\x80\x9d", '"', text)  # Fix closing quotes
    text = re.sub(r"â\x80\x93", "–", text)  # Fix en-dash
    text = re.sub(r"â\x80\x94", "—", text)  # Fix em-dash
    text = re.sub(r"â\x80\xa6", "...", text)  # Fix ellipsis

    # Remove control characters except newlines and tabs
    text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", text)

    # Fix common PDF artifacts
    text = re.sub(r"\x0c", "\n", text)  # Form feed to newline
    text = re.sub(r"\\r\\n", "\n", text)  # Escaped line breaks
    text = re.sub(r"\\n", "\n", text)  # Escaped newlines
    text = re.sub(r"\\t", "\t", text)  # Escaped tabs

    return text.strip()


def format_bitcoin_content(content_item):
    """Format a single content item from MCP response"""

    if content_item.get("type") != "text":
        return content_item

    text = content_item.get("text", "")

    try:
        # Try to parse as JSON first (for structured responses)
        data = json.loads(text)

        if isinstance(data, dict) and "content" in data:
            # Clean the content
            cleaned_content = clean_text_content(data["content"])

            # Format the response nicely
            formatted = f"📄 **{data.get('file_name', 'Unknown File')}**"

            if "pages" in data:
                pages = data["pages"]
                if isinstance(pages, list) and len(pages) > 1:
                    formatted += f" (Pages {pages[0]}-{pages[-1]})"
                elif isinstance(pages, list) and len(pages) == 1:
                    formatted += f" (Page {pages[0]})"

            formatted += f"\n\n{cleaned_content}\n"

            return {"type": "text", "text": formatted}

    except (json.JSONDecodeError, TypeError):
        # If not JSON, just clean the raw text
        cleaned_text = clean_text_content(text)
        return {"type": "text", "text": cleaned_text}
    return content_item


def format_query_results_for_mcp(results, query=""):
    """Format query results with URL metadata for MCP response"""

    if MCPResponseFormatter:
        # Use the new formatter if available
        return MCPResponseFormatter.format_for_mcp(results, query)
    else:
        # Fallback to basic formatting
        if not results:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "No relevant information found in the Bitcoin knowledge base."
                        ),
                    }
                ]
            }

        # Basic formatting without URL support
        formatted_text = ""
        if query:
            formatted_text += f"**Query:** {query}\n\n---\n\n"

        for i, result in enumerate(results, 1):
            title = result.get("title", "Untitled")
            content = result.get("content", "")
            source = result.get("source", "Unknown Source")
            url = result.get("url", "")

            formatted_text += f"## Result {i}\n\n**{title}**\n\n"

            if content:
                display_content = (
                    content[:500] + "..." if len(content) > 500 else content
                )
                formatted_text += f"{display_content}\n\n"

            # Add source with URL if available
            if url and url.strip():
                formatted_text += f"*Source: [{source}]({url})*\n\n"
            else:
                formatted_text += f"*Source: {source}*\n\n"

            if i < len(results):
                formatted_text += "---\n\n"

        return {"content": [{"type": "text", "text": formatted_text.strip()}]}


def clean_mcp_response(response_data):
    """Clean an entire MCP response"""

    if not isinstance(response_data, dict):
        return response_data

    # Create a deep copy to avoid mutating the original input
    response_copy = copy.deepcopy(response_data)

    # Handle the content array
    if "content" in response_copy and isinstance(response_copy["content"], list):
        cleaned_content = []

        for item in response_copy["content"]:
            cleaned_item = format_bitcoin_content(item)
            cleaned_content.append(cleaned_item)

        response_copy["content"] = cleaned_content

    return response_copy


def test_cleaning():
    """Test the cleaning functions with sample data"""

    # Sample messy text from PDF
    sample_text = """Bitcoin is a peer-to-peer electronic cash system that allows online\\npayments to be sent directly from one party to another without going through a\\nfinancial institution. Digital signatures provide part of the solution, but the main\\nbenefits are lost if a trusted third party is still required to prevent double-spending.\\nWe propose a solution to the double-spending problem using a peer-to-peer network.\\nThe network timestamps transactions by hashing them into an ongoing chain of\\nhash-based proof-of-work, forming a record that cannot be changed without redoing\\nthe proof-of-work. The longest chain not only serves as proof of the sequence of\\nevents witnessed, but proof that it came from the largest pool of CPU power."""

    print("🧪 Testing Text Cleaning")
    print("=" * 50)
    print("Original:")
    print(sample_text)
    print("\nCleaned:")
    print(clean_text_content(sample_text))


if __name__ == "__main__":
    test_cleaning()
