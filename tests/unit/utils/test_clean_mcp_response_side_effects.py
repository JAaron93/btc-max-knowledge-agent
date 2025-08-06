#!/usr/bin/env python3
"""
Test script to verify clean_mcp_response no longer mutates input
"""

import copy

# Use absolute import from project root to avoid context-dependent failures
from clean_mcp_response import clean_mcp_response


def test_no_side_effects():
    """Test that clean_mcp_response doesn't mutate the original input and returns cleaned copy"""
    # Create test data
    original_data = {
        "content": [
            {
                "type": "text",
                "text": (
                    "This is some test content\\nwith escaped newlines and    extra spaces."
                ),
            },
            {"type": "text", "text": "Another piece of content\\twith\\ttabs."},
        ],
        "metadata": {"source": "test"},
    }

    # Deep copy to compare against later
    original_backup = copy.deepcopy(original_data)

    # Call the function
    cleaned_result = clean_mcp_response(original_data)

    # Assertions:
    # 1) Original data not mutated
    assert original_data == original_backup, "Original input was mutated"

    # 2) Returns a different object (no same reference)
    assert cleaned_result is not original_data, "Function returned original object reference"

    # 3) Structure preserved (content length)
    assert "content" in cleaned_result and isinstance(cleaned_result["content"], list)
    assert len(cleaned_result["content"]) == len(original_data["content"])

    # 4) Content was actually cleaned (at least first item differs if cleanable)
    original_first_text = original_data["content"][0]["text"]
    cleaned_first_text = cleaned_result["content"][0]["text"]
    assert original_first_text != cleaned_first_text, "Content does not appear to have been cleaned"

    # 5) Metadata preserved
    assert cleaned_result.get("metadata") == original_data.get("metadata"), "Metadata changed unexpectedly"


def test_edge_cases():
    """Test edge cases to ensure robustness"""
    # Test with non-dict input
    non_dict_input = "not a dict"
    result = clean_mcp_response(non_dict_input)
    assert result == non_dict_input, "Should return non-dict inputs unchanged"

    # Test with empty dict
    empty_dict = {}
    original_empty = copy.deepcopy(empty_dict)
    result = clean_mcp_response(empty_dict)
    assert empty_dict == original_empty, "Empty dict should not be mutated"

    # Test with dict without content key
    no_content_dict = {"metadata": {"source": "test"}}
    original_no_content = copy.deepcopy(no_content_dict)
    result = clean_mcp_response(no_content_dict)
    assert no_content_dict == original_no_content, "Dict without content should not be mutated"


# Note: No __main__ block needed; pytest will discover and run the tests automatically.
