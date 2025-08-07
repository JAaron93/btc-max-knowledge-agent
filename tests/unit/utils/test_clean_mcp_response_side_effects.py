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

    # 4) Content cleaning is effective when needed:
    #    - Ensure structure/type preserved per item
    #    - Allow already-clean items to remain unchanged
    #    - Require that at least one item was modified by cleaning
    original_contents = original_data["content"]
    cleaned_contents = cleaned_result["content"]

    assert len(original_contents) == len(cleaned_contents), "Content length changed unexpectedly"

    any_item_changed = False
    for orig_item, clean_item in zip(original_contents, cleaned_contents):
        # Structure preserved
        assert isinstance(clean_item, dict) and "type" in clean_item and "text" in clean_item, "Content item structure changed unexpectedly"
        assert clean_item["type"] == orig_item["type"], "Content item 'type' changed unexpectedly"

        # Track if any text changed due to cleaning
        if clean_item["text"] != orig_item["text"]:
            any_item_changed = True

    assert any_item_changed, "Cleaner did not modify any content items; expected at least one item to be cleaned"

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
