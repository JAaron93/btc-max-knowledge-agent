#!/usr/bin/env python3
"""
Step 5: Verify consistency of the correlation-ID

This example demonstrates the implementation of Step 5, which scans all mock logger 
calls and ensures **every** occurrence of `'correlation_id'` matches the found_id, 
proving that the same ID permeates the entire upload operation.
"""

import uuid
from unittest.mock import MagicMock, call


def demo_step5_correlation_id_verification():
    """
    Demonstrate Step 5: Verify consistency of the correlation-ID
    """
    # Setup mock logger with various calls containing correlation_id
    mock_logger = MagicMock()
    
    # Generate a test correlation ID
    test_correlation_id = str(uuid.uuid4())
    
    # Simulate various logger method calls with correlation_id in different structures
    mock_logger.method_calls = [
        # Call 1: Info log with correlation_id in extra_fields
        call.info(
            "Starting upload operation",
            extra={
                'extra_fields': {
                    'correlation_id': test_correlation_id,
                    'operation': 'upload_start'
                }
            }
        ),
        # Call 2: Debug log with correlation_id
        call.debug(
            "Processing chunk 1",
            extra={
                'extra_fields': {
                    'correlation_id': test_correlation_id,
                    'chunk_index': 1
                }
            }
        ),
        # Call 3: Info log with correlation_id
        call.info(
            "Upload completed successfully",
            extra={
                'extra_fields': {
                    'correlation_id': test_correlation_id,
                    'status': 'success'
                }
            }
        ),
        # Call 4: Warning log without correlation_id (should be skipped)
        call.warning(
            "Some warning message",
            extra={
                'extra_fields': {
                    'operation': 'some_other_op'
                }
            }
        ),
        # Call 5: Error log with correlation_id
        call.error(
            "Retry attempt failed",
            extra={
                'extra_fields': {
                    'correlation_id': test_correlation_id,
                    'retry_attempt': 2
                }
            }
        )
    ]
    
    print("Step 5: Verify consistency of the correlation-ID")
    print("=" * 50)
    
    # Step 4: Extract correlation-ID from logged records (prerequisite for Step 5)
    print("\n📋 Step 4: Extract correlation-ID from logged records...")
    found_id = None
    for c in mock_logger.method_calls:
        extra = c.kwargs.get('extra', {})
        fields = extra.get('extra_fields', {})
        if 'correlation_id' in fields:
            found_id = fields['correlation_id']
            break
    
    assert found_id is not None, "No correlation_id found in any log call"
    assert isinstance(found_id, str), "correlation_id should be a string"
    assert found_id, "correlation_id should not be empty"
    
    print(f"✓ Found correlation_id: {found_id}")
    
    # Step 5: Verify consistency of the correlation-ID
    print("\n🔍 Step 5: Verify consistency of the correlation-ID...")
    print("Scanning all method calls to ensure EVERY occurrence matches found_id...")
    
    correlation_id_calls = []
    inconsistent_calls = []
    
    for i, c in enumerate(mock_logger.method_calls):
        extra = c.kwargs.get('extra', {})
        fields = extra.get('extra_fields', {})
        if 'correlation_id' in fields:
            correlation_id_calls.append((i, c, fields['correlation_id']))
            # This is the key assertion from Step 5
            try:
                assert fields['correlation_id'] == found_id
                print(f"  ✓ Call {i+1}: correlation_id matches ({fields['correlation_id']})")
            except AssertionError:
                inconsistent_calls.append((i, fields['correlation_id']))
                print(f"  ✗ Call {i+1}: correlation_id MISMATCH! Expected {found_id}, got {fields['correlation_id']}")
    
    # Final verification
    if inconsistent_calls:
        raise AssertionError(
            f"Step 5 FAILED: Found {len(inconsistent_calls)} calls with inconsistent correlation_id values: {inconsistent_calls}"
        )
    
    print(f"\n✅ Step 5 PASSED: All {len(correlation_id_calls)} calls with correlation_id have consistent values")
    print(f"   Correlation ID: {found_id}")
    print("   This proves that the same ID permeates the entire upload operation.")
    
    return True


def demo_step5_with_inconsistent_data():
    """
    Demonstrate Step 5 failure case with inconsistent correlation IDs
    """
    print("\n" + "=" * 70)
    print("Demo: Step 5 with INCONSISTENT correlation IDs (should fail)")
    print("=" * 70)
    
    # Setup mock logger with INCONSISTENT correlation IDs
    mock_logger = MagicMock()
    
    correlation_id_1 = str(uuid.uuid4())
    correlation_id_2 = str(uuid.uuid4())  # Different ID - this will cause failure
    
    mock_logger.method_calls = [
        call.info(
            "Starting upload",
            extra={'extra_fields': {'correlation_id': correlation_id_1}}
        ),
        call.debug(
            "Processing chunk",
            extra={'extra_fields': {'correlation_id': correlation_id_2}}  # INCONSISTENT!
        ),
    ]
    
    # Step 4: Extract first correlation_id
    found_id = None
    for c in mock_logger.method_calls:
        extra = c.kwargs.get('extra', {})
        fields = extra.get('extra_fields', {})
        if 'correlation_id' in fields:
            found_id = fields['correlation_id']
            break
    
    print(f"Found correlation_id: {found_id}")
    
    # Step 5: Try to verify consistency (this should fail)
    try:
        for i, c in enumerate(mock_logger.method_calls):
            extra = c.kwargs.get('extra', {})
            fields = extra.get('extra_fields', {})
            if 'correlation_id' in fields:
                assert fields['correlation_id'] == found_id
                print(f"  ✓ Call {i+1}: correlation_id matches")
        
        print("❌ Unexpected: No inconsistency detected!")
        return False
        
    except AssertionError:
        print("  ✗ Step 5 correctly FAILED due to inconsistent correlation_id values")
        print("  This demonstrates that Step 5 properly detects correlation_id inconsistencies")
        return True


if __name__ == "__main__":
    print("🧪 Testing Step 5: Correlation-ID Consistency Verification")
    print("=" * 60)
    
    # Test with consistent data (should pass)
    demo_step5_correlation_id_verification()
    
    # Test with inconsistent data (should fail as expected)
    demo_step5_with_inconsistent_data()
    
    print("\n" + "=" * 60)
    print("✅ Step 5 implementation verification complete!")
    print("\nStep 5 ensures that:")
    print("• Every logged correlation_id matches the initially found ID")
    print("• The same correlation ID permeates the entire upload operation") 
    print("• Any inconsistencies are immediately detected and reported")
