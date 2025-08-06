#!/usr/bin/env python3
"""
Test script to demonstrate the improved AST-based PineconeClient constructor fixing.
This shows how the new approach handles complex cases that the old regex couldn't.
"""

from fix_import_paths import ImportPathFixer


def test_complex_pinecone_client_calls():
    """Test various complex PineconeClient constructor scenarios using assertions."""
    test_matrix = [
        # (input, expected_output, changes_expected)
        ('client = PineconeClient(api_key="test123")', 'client = PineconeClient()', True),
        ('client = PineconeClient(api_key=get_key("production"), index="test")', 'client = PineconeClient(index="test")', True),
        ('client = PineconeClient(host="localhost", api_key="secret", timeout=30)', 'client = PineconeClient(host="localhost", timeout=30)', True),
        ("""client = PineconeClient(
    api_key="very_long_api_key_that_spans_multiple_lines",
    index="test-index",
    timeout=60
)""", """client = PineconeClient(
    index="test-index",
    timeout=60
)""", True),
        ('client = PineconeClient(api_key=os.getenv("PINECONE_KEY", get_default()), region="us-west1")', 'client = PineconeClient(region="us-west1")', True),
        ('client = PineconeClient(index="test", timeout=30)', 'client = PineconeClient(index="test", timeout=30)', False),
    ]

    fixer = ImportPathFixer()

    for original, expected, changes_expected in test_matrix:
        result, changes = fixer._fix_integration_tests(original)

        # Assert code matches expectation
        assert result == expected, f"Fixed code mismatch.\nOriginal:\n{original}\nExpected:\n{expected}\nGot:\n{result}"

        # Assert change detection correctness
        if changes_expected:
            assert changes and any("PineconeClient" in c or "api_key" in c for c in changes), (
                f"Expected changes for input but none or unrelated changes were reported.\nOriginal:\n{original}\nChanges:{changes}"
            )
        else:
            assert not changes, f"Did not expect changes but got: {changes}"


def test_comparison_with_old_regex():
    """Compare old regex approach with new AST approach using assertions."""
    import re

    problematic_case = 'client = PineconeClient(api_key=get_config("key", default_func()), index="test")'

    # Old regex approach (expected to be brittle and possibly wrong)
    old_result = re.sub(
        r"PineconeClient\([^)]*api_key=[^,)]*[,)]", "PineconeClient()", problematic_case
    )

    # New AST approach
    fixer = ImportPathFixer()
    new_result, changes = fixer._fix_integration_tests(problematic_case)

    # Validate that AST approach preserves non-api_key args and removes api_key
    assert new_result == 'client = PineconeClient(index="test")', (
        f"AST approach did not produce expected output. Got: {new_result}"
    )
    assert changes and any("PineconeClient" in c or "api_key" in c for c in changes), (
        "AST approach should report that api_key was removed"
    )

    # Optional: ensure the old regex result differs from expected to demonstrate brittleness
    assert old_result != new_result, "Old regex unexpectedly matched AST result; review test case or pattern"


# No __main__ block; tests are discovered and run by pytest.
