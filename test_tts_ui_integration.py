#!/usr/bin/env python3
"""
Integration test for TTS UI components
"""

import sys
from pathlib import Path
import gradio as gr

# Add project root to path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

def test_ui_creation():
    """Test that the UI can be created without errors"""
    try:
        from src.web.bitcoin_assistant_ui import create_bitcoin_assistant_ui
        
        # Create the interface
        interface = create_bitcoin_assistant_ui()
        
        # Verify it's a Gradio Blocks object
        assert isinstance(interface, gr.Blocks)
        
        print("✅ UI creation test passed")
        return True
        
    except Exception as e:
        print(f"❌ UI creation test failed: {e}")
        return False

def test_tts_components_exist():
    """Test that TTS components are properly defined"""
    try:
        from src.web.bitcoin_assistant_ui import (
            create_waveform_animation,
            get_tts_status_display,
            TTSState
        )
        
        # Test waveform animation
        animation = create_waveform_animation()
        assert isinstance(animation, str)
        assert len(animation) > 0
        
        # Validate waveform animation content
        assert '<svg' in animation, "Animation should contain SVG element"
        assert 'width="100"' in animation, "SVG should have correct width"
        assert 'height="30"' in animation, "SVG should have correct height"
        assert '<rect' in animation, "Animation should contain rectangle elements"
        assert 'animate' in animation, "Animation should contain animate elements"
        assert 'Synthesizing speech...' in animation, "Animation should contain synthesis text"
        assert '#3b82f6' in animation, "Animation should use correct blue color"
        
        # Test status display for different states
        status_ready = get_tts_status_display(False)
        assert isinstance(status_ready, str)
        assert len(status_ready) > 0
        assert 'Ready for voice synthesis' in status_ready, "Ready status should contain expected text"
        assert '🔊' in status_ready, "Ready status should contain speaker emoji"
        assert '#6b7280' in status_ready, "Ready status should use correct gray color"
        
        status_synthesizing = get_tts_status_display(True)
        assert isinstance(status_synthesizing, str)
        assert len(status_synthesizing) > 0
        assert 'Synthesizing speech...' in status_synthesizing, "Synthesizing status should contain expected text"
        assert '<svg' in status_synthesizing, "Synthesizing status should contain SVG animation"
        
        status_error = get_tts_status_display(False, has_error=True)
        assert isinstance(status_error, str)
        assert len(status_error) > 0
        assert 'TTS Error' in status_error, "Error status should contain error message"
        assert '🔴' in status_error, "Error status should contain red circle emoji"
        assert '#ef4444' in status_error, "Error status should use correct red color"
        
        # Test TTS state
        state = TTSState()
        assert hasattr(state, 'is_synthesizing')
        assert hasattr(state, 'start_synthesis')
        assert hasattr(state, 'stop_synthesis')
        
        print("✅ TTS components existence test passed")
        return True
        
    except Exception as e:
        print(f"❌ TTS components test failed: {e}")
        return False

def test_query_function_signature():
    """Test that the query function has the correct signature for TTS"""
    try:
        from src.web.bitcoin_assistant_ui import query_bitcoin_assistant
        import inspect
        
        # Get function signature
        sig = inspect.signature(query_bitcoin_assistant)
        params = list(sig.parameters.keys())
        
        # Should have question and tts_enabled parameters
        assert 'question' in params
        assert 'tts_enabled' in params
        
        print("✅ Query function signature test passed")
        return True
        
    except Exception as e:
        print(f"❌ Query function signature test failed: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Running TTS UI integration tests...")
    
    tests = [
        test_ui_creation,
        test_tts_components_exist,
        test_query_function_signature
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
    
    print(f"\n📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All integration tests passed!")
        sys.exit(0)
    else:
        print("❌ Some tests failed!")
        sys.exit(1)