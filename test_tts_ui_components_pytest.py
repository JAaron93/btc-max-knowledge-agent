#!/usr/bin/env python3
"""
Pytest version of TTS UI components tests

This provides better test management, reporting, and error handling
compared to the manual test runner.

Usage:
    pytest test_tts_ui_components_pytest.py -v
    pytest test_tts_ui_components_pytest.py::test_waveform_animation -v
"""

import sys
import pytest
from pathlib import Path

# Add project root to path - look for project markers
current_dir = Path(__file__).resolve().parent
project_root = current_dir
while project_root != project_root.parent:
    if (project_root / "pyproject.toml").exists() or (project_root / "setup.py").exists():
        break
    project_root = project_root.parent
sys.path.insert(0, str(project_root))

from src.web.bitcoin_assistant_ui import (
    create_waveform_animation,
    get_tts_status_display,
    TTSState
)


class TestTTSUIComponents:
    """Test class for TTS UI components using pytest framework."""
    
    def test_waveform_animation(self):
        """Test waveform animation generation."""
        animation = create_waveform_animation()
        
        # Verify SVG structure
        assert "<svg" in animation, "Animation should contain SVG element"
        assert "animate" in animation, "Animation should contain animate elements"
        assert "Synthesizing speech..." in animation, "Animation should contain status text"
        
        # Verify it's a non-empty string
        assert isinstance(animation, str), "Animation should be a string"
        assert len(animation) > 0, "Animation should not be empty"

    def test_tts_status_display_ready_state(self):
        """Test TTS status display for ready state."""
        ready_status = get_tts_status_display(False)
        
        assert "Ready for voice synthesis" in ready_status, "Ready state should show ready message"
        assert isinstance(ready_status, str), "Status should be a string"

    def test_tts_status_display_synthesizing_state(self):
        """Test TTS status display for synthesizing state."""
        synth_status = get_tts_status_display(True)
        
        assert "Synthesizing speech..." in synth_status, "Synthesizing state should show synthesis message"
        assert isinstance(synth_status, str), "Status should be a string"

    def test_tts_status_display_error_state(self):
        """Test TTS status display for error state."""
        error_status = get_tts_status_display(False, has_error=True)
        
        assert "TTS Error" in error_status, "Error state should show error message"
        assert isinstance(error_status, str), "Status should be a string"

    def test_tts_state_initialization(self):
        """Test TTS state initial values."""
        state = TTSState()
        
        assert not state.is_synthesizing, "Initial state should not be synthesizing"
        assert state.synthesis_start_time is None, "Initial start time should be None"

    def test_tts_state_start_synthesis(self):
        """Test TTS state when starting synthesis."""
        state = TTSState()
        
        # Start synthesis
        state.start_synthesis()
        
        assert state.is_synthesizing, "State should be synthesizing after start"
        assert state.synthesis_start_time is not None, "Start time should be set"
        assert not state.stop_animation, "Stop animation should be False during synthesis"

    def test_tts_state_stop_synthesis(self):
        """Test TTS state when stopping synthesis."""
        state = TTSState()
        
        # Start then stop synthesis
        state.start_synthesis()
        state.stop_synthesis()
        
        assert not state.is_synthesizing, "State should not be synthesizing after stop"
        assert state.stop_animation, "Stop animation should be True after stop"

    def test_tts_state_lifecycle(self):
        """Test complete TTS state lifecycle."""
        state = TTSState()
        
        # Initial state
        assert not state.is_synthesizing
        assert state.synthesis_start_time is None
        
        # Start synthesis
        state.start_synthesis()
        start_time = state.synthesis_start_time
        assert state.is_synthesizing
        assert start_time is not None
        assert not state.stop_animation
        
        # Stop synthesis
        state.stop_synthesis()
        assert not state.is_synthesizing
        assert state.stop_animation
        # Start time should be preserved
        assert state.synthesis_start_time == start_time


if __name__ == "__main__":
    """
    Run tests using pytest when executed directly.
    This provides better output than running pytest manually.
    """
    import subprocess
    import sys
    
    print("🧪 Running TTS UI component tests with pytest...")
    
    # Run pytest with verbose output and this file
    result = subprocess.run([
        sys.executable, "-m", "pytest", 
        __file__, 
        "-v",  # verbose output
        "--tb=short",  # shorter traceback format
        "--color=yes"  # colored output
    ], capture_output=False)
    
    # Exit with the same code as pytest
    sys.exit(result.returncode)
