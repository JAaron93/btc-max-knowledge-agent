#!/usr/bin/env python3
"""
Clean and format MCP response text using regex and URL metadata support
"""

import copy
import json
import re

# Import the new result formatter
try:
    from btc_max_knowledge_agent.utils.result_formatter import MCPResponseFormatter
except ImportError:
    # Fallback if import fails or package not installed
    MCPResponseFormatter = None


# Pre-compiled regex patterns for performance optimization
# Line ending normalization
WINDOWS_LINE_ENDINGS = re.compile(r"\r\n")
MAC_LINE_ENDINGS = re.compile(r"\r")

# PDF extraction fixes
CAMEL_CASE_FIX = re.compile(r"([a-z])([A-Z])")
LETTER_NUMBER_SPACING = re.compile(r"([a-z])(\d)")
NUMBER_LETTER_SPACING = re.compile(r"(\d)([A-Z])")

# Word fixes
HYPHENATED_WORDS = re.compile(r"([a-z])-\s*\n\s*([a-z])")
EXCESSIVE_SPACES = re.compile(r" {2,}")
EXCESSIVE_NEWLINES = re.compile(r"\n{3,}")
TRAILING_WHITESPACE = re.compile(r"[ \t]+$", re.MULTILINE)
BROKEN_WORDS = re.compile(r"([a-z])\s*\n\s*([a-z])")

# Punctuation spacing
SPACE_BEFORE_PUNCTUATION = re.compile(r"\s+([,.;:!?])")
PUNCTUATION_LETTER_SPACING = re.compile(r"([,.;:!?])([A-Za-z])")

# Additional PDF text extraction fixes
CAMEL_CASE_DETAILED = re.compile(r"([a-z])([A-Z][a-z])")
WORD_NUMBER_SPACING = re.compile(r"(\w)(\d+)")
NUMBER_WORD_SPACING = re.compile(r"(\d+)([A-Za-z])")

# Encoding fixes
APOSTROPHE_FIX = re.compile(r"â\x80\x99")
OPENING_QUOTE_FIX = re.compile(r"â\x80\x9c")
CLOSING_QUOTE_FIX = re.compile(r"â\x80\x9d")
EN_DASH_FIX = re.compile(r"â\x80\x93")
EM_DASH_FIX = re.compile(r"â\x80\x94")
ELLIPSIS_FIX = re.compile(r"â\x80\xa6")

# Control characters and PDF artifacts
CONTROL_CHARS = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")
FORM_FEED = re.compile(r"\x0c")
ESCAPED_LINE_BREAKS = re.compile(r"\\r\\n")
ESCAPED_NEWLINES = re.compile(r"\\n")
ESCAPED_TABS = re.compile(r"\\t")


def clean_text_content(text):
    """Clean text content using pre-compiled regex patterns"""

    # Remove excessive whitespace and normalize line breaks
    text = WINDOWS_LINE_ENDINGS.sub("\n", text)  # Convert Windows line endings
    text = MAC_LINE_ENDINGS.sub("\n", text)  # Convert old Mac line endings

    # Fix common PDF extraction issues
    text = CAMEL_CASE_FIX.sub(r"\1 \2", text)  # Add space between camelCase
    text = LETTER_NUMBER_SPACING.sub(
        r"\1 \2", text
    )  # Add space between letter and number
    text = NUMBER_LETTER_SPACING.sub(
        r"\1 \2", text
    )  # Add space between number and letter

    # Fix hyphenated words split across lines
    text = HYPHENATED_WORDS.sub(r"\1\2", text)

    # Remove excessive spaces
    text = EXCESSIVE_SPACES.sub(" ", text)

    # Fix paragraph breaks
    text = EXCESSIVE_NEWLINES.sub("\n\n", text)

    # Remove trailing whitespace from lines
    text = TRAILING_WHITESPACE.sub("", text)

    # Fix broken words at line endings (common in PDFs)
    text = BROKEN_WORDS.sub(r"\1\2", text)

    # Fix spacing around punctuation
    text = SPACE_BEFORE_PUNCTUATION.sub(r"\1", text)
    text = PUNCTUATION_LETTER_SPACING.sub(r"\1 \2", text)

    # Fix common PDF text extraction issues
    text = CAMEL_CASE_DETAILED.sub(r"\1 \2", text)  # camelCase fixes
    text = WORD_NUMBER_SPACING.sub(r"\1 \2", text)  # word-number spacing
    text = NUMBER_WORD_SPACING.sub(r"\1 \2", text)  # number-word spacing

    # Fix common encoding issues
    text = APOSTROPHE_FIX.sub("'", text)  # Fix apostrophes
    text = OPENING_QUOTE_FIX.sub('"', text)  # Fix opening quotes
    text = CLOSING_QUOTE_FIX.sub('"', text)  # Fix closing quotes
    text = EN_DASH_FIX.sub("–", text)  # Fix en-dash
    text = EM_DASH_FIX.sub("—", text)  # Fix em-dash
    text = ELLIPSIS_FIX.sub("...", text)  # Fix ellipsis

    # Remove control characters except newlines and tabs
    text = CONTROL_CHARS.sub("", text)

    # Fix common PDF artifacts
    text = FORM_FEED.sub("\n", text)  # Form feed to newline
    text = ESCAPED_LINE_BREAKS.sub("\n", text)  # Escaped line breaks
    text = ESCAPED_NEWLINES.sub("\n", text)  # Escaped newlines
    text = ESCAPED_TABS.sub("\t", text)  # Escaped tabs

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
