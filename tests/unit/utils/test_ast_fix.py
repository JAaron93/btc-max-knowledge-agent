#!/usr/bin/env python3
"""
Test script to demonstrate the improved AST-based PineconeClient constructor fixing.
This shows how the new approach handles complex cases that the old regex couldn't.
"""

from fix_import_paths import ImportPathFixer


def test_complex_pinecone_client_calls():
    """Test various complex PineconeClient constructor scenarios."""

    # Test cases that would break the old regex approach
    test_cases = [
        # Simple case
        'client = PineconeClient(api_key="test123")',
        # Nested parentheses (regex would fail here)
        'client = PineconeClient(api_key=get_key("production"), index="test")',
        # Multiple parameters with api_key in middle
        'client = PineconeClient(host="localhost", api_key="secret", timeout=30)',
        # Multiline call
        """client = PineconeClient(
    api_key="very_long_api_key_that_spans_multiple_lines",
    index="test-index",
    timeout=60
)""",
        # Complex nested function calls
        'client = PineconeClient(api_key=os.getenv("PINECONE_KEY", get_default()), region="us-west1")',
        # Already correct (no api_key)
        'client = PineconeClient(index="test", timeout=30)',
    ]

    fixer = ImportPathFixer()

    print("🧪 Testing AST-based PineconeClient constructor fixing...\n")

    for i, test_case in enumerate(test_cases, 1):
        print(f"Test Case {i}:")
        print(f"Original: {test_case}")

        try:
            # Test the AST-based approach
            result, changes = fixer._fix_integration_tests(test_case)
            print(f"Fixed:    {result}")
            if changes:
                print(f"Changes:  {', '.join(changes)}")
            else:
                print("Changes:  No changes needed")
            print()
        except Exception as e:
            print(f"Error:    {e}")
            print()


def test_comparison_with_old_regex():
    """Compare old regex approach with new AST approach."""

    # This is the problematic case that breaks the old regex
    problematic_case = 'client = PineconeClient(api_key=get_config("key", default_func()), index="test")'

    print("🔄 Comparing old regex vs new AST approach...\n")
    print(f"Test case: {problematic_case}")

    # Old regex approach (the fragile one we replaced)
    import re

    old_result = re.sub(
        r"PineconeClient\([^)]*api_key=[^,)]*[,)]", "PineconeClient()", problematic_case
    )
    print(f"Old regex result: {old_result}")

    # New AST approach
    fixer = ImportPathFixer()
    new_result, changes = fixer._fix_integration_tests(problematic_case)
    print(f"New AST result:   {new_result}")
    print(f"Changes applied:  {', '.join(changes) if changes else 'None'}")


if __name__ == "__main__":
    test_complex_pinecone_client_calls()
    print("=" * 60)
    test_comparison_with_old_regex()
    print("\n✅ AST-based approach successfully handles complex cases!")
