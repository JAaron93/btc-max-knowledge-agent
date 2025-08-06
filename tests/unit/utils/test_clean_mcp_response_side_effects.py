#!/usr/bin/env python3
"""
Test script to verify clean_mcp_response no longer mutates input
"""

import copy

from clean_mcp_response import clean_mcp_response


def test_no_side_effects():
    """Test that clean_mcp_response doesn't mutate the original input"""

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

    # Create a deep copy to compare against later
    original_backup = copy.deepcopy(original_data)

    print("🧪 Testing clean_mcp_response for side effects")
    print("=" * 60)

    print("\n📋 Original data before cleaning:")
    print(f"Content items: {len(original_data['content'])}")
    print(f"First item text: {repr(original_data['content'][0]['text'])}")
    print(f"Second item text: {repr(original_data['content'][1]['text'])}")
    print(f"Metadata: {original_data['metadata']}")

    # Call the function
    cleaned_result = clean_mcp_response(original_data)

    print("\n✨ After calling clean_mcp_response:")
    print(f"Cleaned content items: {len(cleaned_result['content'])}")
    print(f"Cleaned first item text: {repr(cleaned_result['content'][0]['text'])}")
    print(f"Cleaned second item text: {repr(cleaned_result['content'][1]['text'])}")

    # Verify original data wasn't mutated
    if original_data == original_backup:
        print("\n✅ SUCCESS: Original data was NOT mutated!")
        print("The function correctly works on a copy.")
    else:
        print("\n❌ FAILURE: Original data was mutated!")
        print("This indicates a side effect bug.")
        return False

    # Verify the function actually cleaned the content
    original_first_text = original_data["content"][0]["text"]
    cleaned_first_text = cleaned_result["content"][0]["text"]

    if original_first_text != cleaned_first_text:
        print("\n✅ SUCCESS: Content was actually cleaned!")
        print(f"Original: {repr(original_first_text)}")
        print(f"Cleaned:  {repr(cleaned_first_text)}")
    else:
        print("\n⚠️  WARNING: Content doesn't appear to have been cleaned.")

    # Verify it returns a different object (not the same reference)
    if cleaned_result is not original_data:
        print("\n✅ SUCCESS: Function returns a new object, not the original!")
    else:
        print("\n❌ FAILURE: Function returned the same object reference!")
        return False

    return True


def test_edge_cases():
    """Test edge cases to ensure robustness"""

    print("\n🔍 Testing edge cases...")

    # Test with non-dict input
    non_dict_input = "not a dict"
    result = clean_mcp_response(non_dict_input)
    assert result == non_dict_input, "Should return non-dict inputs unchanged"
    print("✅ Non-dict input handled correctly")

    # Test with empty dict
    empty_dict = {}
    original_empty = copy.deepcopy(empty_dict)
    result = clean_mcp_response(empty_dict)
    assert empty_dict == original_empty, "Empty dict should not be mutated"
    print("✅ Empty dict handled correctly")

    # Test with dict without content key
    no_content_dict = {"metadata": {"source": "test"}}
    original_no_content = copy.deepcopy(no_content_dict)
    result = clean_mcp_response(no_content_dict)
    assert (
        no_content_dict == original_no_content
    ), "Dict without content should not be mutated"
    print("✅ Dict without content handled correctly")


if __name__ == "__main__":
    print("🚀 Running side effects test for clean_mcp_response")

    try:
        success = test_no_side_effects()
        test_edge_cases()

        if success:
            print("\n🎉 All tests passed! The function is now side-effect free.")
        else:
            print("\n💥 Some tests failed. Please check the implementation.")
    except Exception as e:
        print(f"\n💥 Test execution failed with error: {e}")
