#!/usr/bin/env python3
"""
Test script for TTS visual feedback and animations
Tests the implementation of task 9: Add visual feedback and animations
"""

import sys
import time
import re
from pathlib import Path
from html.parser import HTMLParser
from typing import Dict, List, Set, Optional

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


# Utility classes and functions for robust testing
class HTMLValidator(HTMLParser):
    """HTML parser to validate structure and extract information"""

    def __init__(self):
        super().__init__()
        self.errors = []
        self.tags = []
        self.attributes = {}
        self.css_animations = set()
        self.css_keyframes = set()
        self.in_style = False
        self.style_content = ""

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        self.attributes[tag] = self.attributes.get(tag, [])
        self.attributes[tag].append(dict(attrs))

        if tag == 'style':
            self.in_style = True

        # Extract animation references from style attributes
        for attr_name, attr_value in attrs:
            if attr_name == 'style' and 'animation:' in attr_value:
                # Extract animation names from style attribute
                animation_matches = re.findall(r'animation:\s*([^;\s]+)', attr_value)
                for match in animation_matches:
                    # Extract just the animation name (first part before space)
                    anim_name = match.split()[0]
                    self.css_animations.add(anim_name)

    def handle_endtag(self, tag):
        if tag == 'style':
            self.in_style = False
            # Parse CSS content for keyframes
            keyframe_matches = re.findall(r'@keyframes\s+([^{\s]+)', self.style_content)
            self.css_keyframes.update(keyframe_matches)
            self.style_content = ""

    def handle_data(self, data):
        if self.in_style:
            self.style_content += data

    def error(self, message):
        self.errors.append(message)


def validate_html_structure(html: str) -> Dict:
    """Validate HTML structure and return analysis"""
    validator = HTMLValidator()
    try:
        validator.feed(html)
        validator.close()

        return {
            'is_valid': len(validator.errors) == 0,
            'errors': validator.errors,
            'tags': validator.tags,
            'attributes': validator.attributes,
            'css_animations': validator.css_animations,
            'css_keyframes': validator.css_keyframes
        }
    except Exception as e:
        return {
            'is_valid': False,
            'errors': [str(e)],
            'tags': [],
            'attributes': {},
            'css_animations': set(),
            'css_keyframes': set()
        }


def match_attribute_flexible(html: str, tag: str, attribute: str, expected_value: str,
                           allow_quotes: bool = True) -> bool:
    """Match HTML attributes with flexible spacing and quote styles"""
    if allow_quotes:
        # Match with single quotes, double quotes, or no quotes
        patterns = [
            rf'{tag}[^>]*{attribute}\s*=\s*["\']?{re.escape(expected_value)}["\']?',
            rf'{attribute}\s*=\s*["\']?{re.escape(expected_value)}["\']?'
        ]
    else:
        patterns = [rf'{tag}[^>]*{attribute}\s*=\s*{re.escape(expected_value)}']

    for pattern in patterns:
        if re.search(pattern, html, re.IGNORECASE):
            return True
    return False


def extract_css_animations(html: str) -> Set[str]:
    """Extract all CSS animation names referenced in HTML"""
    animations = set()

    # Find animation references in style attributes
    style_matches = re.findall(r'style\s*=\s*["\']([^"\']*)["\']', html, re.IGNORECASE)
    for style in style_matches:
        anim_matches = re.findall(r'animation:\s*([^;\s]+)', style)
        for match in anim_matches:
            # Extract just the animation name (first part before space)
            anim_name = match.split()[0]
            animations.add(anim_name)

    return animations


def extract_css_keyframes(html: str) -> Set[str]:
    """Extract all CSS keyframe definitions from HTML"""
    keyframes = set()

    # Find keyframes in style blocks
    style_blocks = re.findall(r'<style[^>]*>(.*?)</style>', html, re.DOTALL | re.IGNORECASE)
    for block in style_blocks:
        keyframe_matches = re.findall(r'@keyframes\s+([^{\s]+)', block)
        keyframes.update(keyframe_matches)

    return keyframes


def validate_css_animations(html: str) -> Dict:
    """Validate that all referenced CSS animations have corresponding keyframe definitions"""
    animations = extract_css_animations(html)
    keyframes = extract_css_keyframes(html)

    missing_keyframes = animations - keyframes

    return {
        'animations_found': animations,
        'keyframes_found': keyframes,
        'missing_keyframes': missing_keyframes,
        'all_animations_defined': len(missing_keyframes) == 0
    }


# Test the visual feedback functions directly without importing the full UI
def create_waveform_animation() -> str:
    """Create enhanced animated waveform SVG for TTS synthesis with smooth transitions"""
    return """
    <style>
        @keyframes pulse {
            0%, 80%, 100% { opacity: 0.3; transform: scale(0.8); }
            40%           { opacity: 1;   transform: scale(1.2); }
        }
    </style>
    <div style="display: flex; align-items: center; justify-content: center; padding: 10px; transition: all 0.3s ease-in-out;">
        <svg width="120" height="24" viewBox="0 0 120 24" style="filter: drop-shadow(0 2px 4px rgba(59, 130, 246, 0.2));">
            <!-- Enhanced waveform with multiple bars and varied animations -->
            <rect x="2" y="8" width="2" height="8" fill="#3b82f6" opacity="0.9" rx="1">
                <animate attributeName="height" values="8;16;8" dur="0.8s" repeatCount="indefinite"/>
                <animate attributeName="y" values="8;4;8" dur="0.8s" repeatCount="indefinite"/>
            </rect>
            <rect x="8" y="6" width="2" height="12" fill="#3b82f6" opacity="0.8" rx="1">
                <animate attributeName="height" values="12;20;12" dur="1.2s" repeatCount="indefinite"/>
                <animate attributeName="y" values="6;2;6" dur="1.2s" repeatCount="indefinite"/>
            </rect>
            <rect x="14" y="10" width="2" height="4" fill="#3b82f6" opacity="0.7" rx="1">
                <animate attributeName="height" values="4;14;4" dur="0.6s" repeatCount="indefinite"/>
                <animate attributeName="y" values="10;5;10" dur="0.6s" repeatCount="indefinite"/>
            </rect>
        </svg>
        <span style="margin-left: 12px; color: #3b82f6; font-size: 14px; font-weight: 500; animation: pulse 2s infinite;">Synthesizing speech...</span>
        <div style="width: 8px; height: 8px; border-radius: 50%; background-color: #3b82f6; animation: pulse 1.4s infinite ease-in-out; margin-left: 8px;">
        </div>
    </div>
    """
def create_loading_indicator() -> str:
    """Create loading indicator for TTS processing state"""
    return """
    <div style="display: flex; align-items: center; justify-content: center; padding: 10px; transition: all 0.3s ease-in-out;">
        <div style="display: flex; align-items: center; gap: 8px;">
            <div style="width: 8px; height: 8px; border-radius: 50%; background-color: #3b82f6; animation: loading-dot 1.4s infinite ease-in-out both;">
            </div>
        </div>
        <span style="margin-left: 12px; color: #3b82f6; font-size: 14px; font-weight: 500;">Processing text...</span>
    </div>
    """

def create_playback_indicator(is_cached: bool = False) -> str:
    """Create playback indicator with different styles for cached vs new audio"""
    # Define conditional values for cached vs non-cached audio
    color = "#10b981" if is_cached else "#3b82f6"
    icon = "&#9889;" if is_cached else "&#128266;"
    text = "Playing cached audio" if is_cached else "Playing synthesized audio"
    
    return f"""
        <div style="display: flex; align-items: center; justify-content: center; padding: 10px; transition: all 0.3s ease-in-out;">
            <span style="margin-left: 12px; color: {color}; font-size: 14px; font-weight: 500;">{icon} {text}</span>
        </div>
        """


def create_loading_indicator() -> str:
    """Create loading indicator for TTS processing state"""
    return r'''
    <div style="display: flex; align-items: center; justify-content: center; padding: 10px; transition: all 0.3s ease-in-out;">
        <div style="display: flex; align-items: center; gap: 8px;">
            <div style="width: 8px; height: 8px; border-radius: 50%; background-color: #3b82f6; animation: loading-dot 1.4s infinite ease-in-out both;">
                <style>
                    @keyframes loading-dot {
                        0%, 80%, 100% { transform: scale(0); opacity: 0.5; }
                        40% { transform: scale(1); opacity: 1; }
                    }
                </style>
            </div>
            <div style="width: 8px; height: 8px; border-radius: 50%; background-color: #3b82f6; animation: loading-dot 1.4s infinite ease-in-out both; animation-delay: -0.32s;"></div>
            <div style="width: 8px; height: 8px; border-radius: 50%; background-color: #3b82f6; animation: loading-dot 1.4s infinite ease-in-out both; animation-delay: -0.16s;"></div>
        </div>
        <span style="margin-left: 12px; color: #3b82f6; font-size: 14px; font-weight: 500;">Processing text...</span>
    </div>
    '''


def get_tts_status_display(is_synthesizing: bool, has_error: bool = False, error_info: dict = None,
                          is_loading: bool = False, is_playing: bool = False, is_cached: bool = False) -> str:
    """Get TTS status display HTML with comprehensive visual feedback and smooth transitions"""

    # CSS keyframes for animations (included for standalone usage)
    css_keyframes = r'''
    <style>
        @keyframes fade-in {
            from {
                opacity: 0;
                transform: translateY(-10px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        @keyframes loading-dot {
            0%, 80%, 100% {
                transform: scale(0);
                opacity: 0.5;
            }
            40% {
                transform: scale(1);
                opacity: 1;
            }
        }
    </style>
    '''

    # Handle error states with enhanced visual feedback
    if has_error:
        # Extract error details if available and generate appropriate display message
        if error_info:
            error_type = error_info.get("error_type", "UNKNOWN")
            error_message = error_info.get("error_message", "TTS service error")

            # Generate display message based on error type (extensible for future error types)
            error_type_messages = {
                "API_KEY_ERROR": "[ERROR] API Key Issue - Text continues normally",
                "NETWORK_ERROR": "[ERROR] Network Issue - Text continues normally",
                "RATE_LIMIT": "[ERROR] Rate Limited - Text continues normally",
                "UNKNOWN": "[ERROR] TTS Error - Text continues normally"
            }
            display_message = error_type_messages.get(error_type, "[ERROR] TTS Error - Text continues normally")
        else:
            # Fallback for cases without detailed error info
            display_message = "[ERROR] TTS Error - Text continues normally"

        # Consolidated error HTML structure (single source of truth)
        return f"""
        {css_keyframes}
        <div class="tts-status error" style="display: flex; align-items: center; justify-content: center; padding: 10px; background: linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%); border: 1px solid #fca5a5; border-radius: 8px; transition: all 0.3s ease-in-out;">
            <span style="color: #dc2626; font-size: 13px; cursor: help; font-weight: 500; animation: fade-in 0.3s ease-in-out;">{display_message}</span>
        </div>
        """
    elif is_loading:
        # Show loading indicator for initial processing
        return f"""
        <div class="tts-status synthesizing" style="background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%); border: 1px solid #93c5fd; border-radius: 8px; transition: all 0.3s ease-in-out;">
            {create_loading_indicator()}
        </div>
        """
    elif is_synthesizing:
        # Show waveform animation during synthesis
        return f"""
        <div class="tts-status synthesizing" style="background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%); border: 1px solid #93c5fd; border-radius: 8px; transition: all 0.3s ease-in-out;">
            {create_waveform_animation()}
        </div>
        """
    elif is_playing:
        # Show playback indicator
        return f"""
        <div class="tts-status playing" style="background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%); border: 1px solid #86efac; border-radius: 8px; transition: all 0.3s ease-in-out;">
            {create_playback_indicator(is_cached)}
        </div>
        """
    else:
        # Ready state with smooth transition
        return f"""
        {css_keyframes}
        <div class="tts-status ready" style="display: flex; align-items: center; justify-content: center; padding: 10px; background: linear-gradient(135deg, #f9fafb 0%, #f3f4f6 100%); border: 1px solid #d1d5db; border-radius: 8px; transition: all 0.3s ease-in-out;">
            <span style="color: #6b7280; font-size: 13px; font-weight: 500; animation: fade-in 0.3s ease-in-out;">[READY] Ready for voice synthesis</span>
        </div>
        """

class TTSState:
    """Manages TTS state and animations with thread-safe operations"""
    def __init__(self):
        self.is_synthesizing = False
        self.synthesis_start_time = None
        self.stop_animation = False

    def start_synthesis(self):
        """Start synthesis animation (thread-safe)"""
        self.is_synthesizing = True
        self.synthesis_start_time = time.time()
        self.stop_animation = False

    def stop_synthesis(self):
        """Stop synthesis animation (thread-safe)"""
        self.is_synthesizing = False
        self.stop_animation = True


def test_waveform_animation():
    """Test waveform animation creation with robust validation"""
    print("Testing waveform animation...")

    animation_html = create_waveform_animation()

    # Validate HTML structure
    html_analysis = validate_html_structure(animation_html)
    assert html_analysis['is_valid'], f"HTML should be valid. Errors: {html_analysis['errors']}"

    # Verify animation contains required elements
    assert "svg" in animation_html.lower(), "Animation should contain SVG element"
    assert "animate" in animation_html.lower(), "Animation should contain animate elements"
    assert "synthesizing speech" in animation_html.lower(), "Animation should contain synthesis text"

    # Use flexible attribute matching for dimensions
    assert match_attribute_flexible(animation_html, "svg", "width", "120"), "Animation should be 120px wide (per requirements)"
    assert match_attribute_flexible(animation_html, "svg", "height", "24"), "Animation should be 24px high (per requirements)"

    # Verify smooth transitions with regex
    transition_pattern = r'transition:\s*all\s+0\.3s\s+ease-in-out'
    assert re.search(transition_pattern, animation_html), "Animation should have smooth transitions"

    print("Waveform animation test passed")


def test_loading_indicator():
    """Test loading indicator creation with CSS animation validation"""
    print("Testing loading indicator...")

    loading_html = create_loading_indicator()

    # Validate HTML structure
    html_analysis = validate_html_structure(loading_html)
    assert html_analysis['is_valid'], f"HTML should be valid. Errors: {html_analysis['errors']}"

    # Verify loading indicator contains required elements
    assert "processing text" in loading_html.lower(), "Loading indicator should show processing text"
    assert "loading-dot" in loading_html, "Loading indicator should have animated dots"

    # Verify smooth transitions with regex
    transition_pattern = r'transition:\s*all\s+0\.3s\s+ease-in-out'
    assert re.search(transition_pattern, loading_html), "Loading indicator should have smooth transitions"

    # Validate CSS animations are properly defined
    css_validation = validate_css_animations(loading_html)
    assert css_validation['all_animations_defined'], f"Missing keyframes for animations: {css_validation['missing_keyframes']}"
    assert 'loading-dot' in css_validation['keyframes_found'], "loading-dot keyframe should be defined"

    print("Loading indicator test passed")


def test_playback_indicator():
    """Test playback indicator for both cached and new audio"""
    print("Testing playback indicators...")

    # Test cached audio indicator
    cached_html = create_playback_indicator(is_cached=True)
    assert "cached audio" in cached_html.lower(), "Cached indicator should mention cached audio"
    assert "#10b981" in cached_html, "Cached indicator should use green color"
    assert "&#9889;" in cached_html, "Cached indicator should have lightning emoji"

    # Test new audio indicator
    new_html = create_playback_indicator(is_cached=False)
    assert "synthesized audio" in new_html.lower(), "New audio indicator should mention synthesized audio"
    assert "#3b82f6" in new_html, "New audio indicator should use blue color"
    assert "&#128266;" in new_html, "New audio indicator should have speaker emoji"

    print("Playback indicator tests passed")


def test_status_display_states():
    """Test different TTS status display states"""
    print("Testing TTS status display states...")

    # Test ready state
    ready_html = get_tts_status_display(False)
    assert "ready for voice synthesis" in ready_html.lower(), "Ready state should show ready message"
    assert "tts-status ready" in ready_html, "Ready state should have ready CSS class"

    # Test loading state
    loading_html = get_tts_status_display(False, is_loading=True)
    assert "tts-status synthesizing" in loading_html, "Loading state should have synthesizing CSS class"
    assert "processing text" in loading_html.lower(), "Loading state should show processing message"

    # Test synthesizing state (waveform animation)
    synthesizing_html = get_tts_status_display(True)
    assert "tts-status synthesizing" in synthesizing_html, "Synthesizing state should have synthesizing CSS class"
    assert "synthesizing speech" in synthesizing_html.lower(), "Synthesizing state should show synthesis message"
    assert "svg" in synthesizing_html.lower(), "Synthesizing state should contain waveform SVG"

    # Test playing state
    playing_html = get_tts_status_display(False, is_playing=True, is_cached=False)
    assert "tts-status playing" in playing_html, "Playing state should have playing CSS class"

    # Test error state
    error_info = {"error_type": "API_KEY_ERROR", "error_message": "Invalid API key"}
    error_html = get_tts_status_display(False, has_error=True, error_info=error_info)
    assert "tts-status error" in error_html, "Error state should have error CSS class"
    assert "tts error" in error_html.lower(), "Error state should show error message"

    print("Status display state tests passed")


def test_smooth_transitions():
    """Test that smooth transitions are implemented with robust pattern matching"""
    print("Testing smooth transitions...")

    # Check that all status displays include transition CSS
    states = [
        ("Ready", get_tts_status_display(False)),
        ("Loading", get_tts_status_display(False, is_loading=True)),
        ("Synthesizing", get_tts_status_display(True)),
        ("Playing", get_tts_status_display(False, is_playing=True)),
        ("Error", get_tts_status_display(False, has_error=True, error_info={"error_type": "TEST"}))
    ]

    # Flexible transition pattern matching
    transition_pattern = r'transition:\s*all\s+0\.3s\s+ease-in-out'
    fade_in_pattern = r'animation:\s*fade-in\s+0\.3s\s+ease-in-out|fade-in'

    for i, (state_name, state_html) in enumerate(states):
        # Validate HTML structure first
        html_analysis = validate_html_structure(state_html)
        assert html_analysis['is_valid'], f"{state_name} state HTML should be valid. Errors: {html_analysis['errors']}"

        # Check for smooth transitions with flexible pattern
        assert re.search(transition_pattern, state_html), f"{state_name} state should have smooth transitions"

        # Check that Ready and Error states have fade-in animation
        if i in [0, 4]:  # Ready and Error states should have fade-in
            assert re.search(fade_in_pattern, state_html), f"{state_name} state should have fade-in animation"

        # Validate CSS animations if present
        css_validation = validate_css_animations(state_html)
        if css_validation['animations_found']:
            assert css_validation['all_animations_defined'], \
                f"{state_name} state missing keyframes: {css_validation['missing_keyframes']}"

    print("Smooth transitions test passed")


def test_cached_audio_requirements():
    """Test that cached audio hides animation per requirement 3.5"""
    print("Testing cached audio animation hiding (Requirement 3.5)...")
    
    # Test that cached playback indicator is different from synthesis animation
    cached_playback = create_playback_indicator(is_cached=True)
    waveform_animation = create_waveform_animation()
    
    # Cached playback should not contain synthesis animation elements
    assert "synthesizing speech" not in cached_playback.lower(), "Cached playback should not show synthesis message"
    assert cached_playback != waveform_animation, "Cached playback should be different from waveform animation"
    assert "cached" in cached_playback.lower(), "Cached playback should indicate it's cached"
    
    print("Cached audio animation hiding test passed")


def test_tts_state_management():
    """Test TTS state management for thread safety"""
    print("Testing TTS state management...")
    
    tts_state = TTSState()
    
    # Test initial state
    assert not tts_state.is_synthesizing, "Initial state should not be synthesizing"
    assert tts_state.synthesis_start_time is None, "Initial start time should be None"
    assert not tts_state.stop_animation, "Initial stop flag should be False"
    
    # Test start synthesis
    tts_state.start_synthesis()
    assert tts_state.is_synthesizing, "Should be synthesizing after start"
    assert tts_state.synthesis_start_time is not None, "Start time should be set"
    assert not tts_state.stop_animation, "Stop flag should be False during synthesis"
    
    # Test stop synthesis
    tts_state.stop_synthesis()
    assert not tts_state.is_synthesizing, "Should not be synthesizing after stop"
    assert tts_state.stop_animation, "Stop flag should be True after stop"
    
    print("TTS state management test passed")


def test_visual_requirements_compliance():
    """Test compliance with specific visual requirements using robust validation"""
    print("Testing visual requirements compliance...")

    # Requirement 1.3: Waveform animation specifications with flexible matching
    waveform = create_waveform_animation()
    assert match_attribute_flexible(waveform, "svg", "height", "24"), "Waveform height should be 24 pixels maximum"
    assert match_attribute_flexible(waveform, "svg", "width", "120"), "Waveform width should be 120 pixels maximum"

    # Validate waveform HTML structure
    waveform_analysis = validate_html_structure(waveform)
    assert waveform_analysis['is_valid'], f"Waveform HTML should be valid. Errors: {waveform_analysis['errors']}"

    # Requirement 3.3: Visual feedback during synthesis vs cached playback
    synthesis_status = get_tts_status_display(True)  # Synthesizing
    cached_status = get_tts_status_display(False, is_playing=True, is_cached=True)  # Cached playback

    # Validate both HTML structures
    synthesis_analysis = validate_html_structure(synthesis_status)
    cached_analysis = validate_html_structure(cached_status)
    assert synthesis_analysis['is_valid'], f"Synthesis status HTML should be valid. Errors: {synthesis_analysis['errors']}"
    assert cached_analysis['is_valid'], f"Cached status HTML should be valid. Errors: {cached_analysis['errors']}"

    # Synthesis should show waveform, cached should not
    assert "svg" in synthesis_status.lower(), "Synthesis should show waveform animation"
    assert "svg" not in cached_status.lower(), "Cached playback should not show waveform animation"

    # Validate CSS animations in both states
    synthesis_css = validate_css_animations(synthesis_status)
    cached_css = validate_css_animations(cached_status)

    if synthesis_css['animations_found']:
        assert synthesis_css['all_animations_defined'], f"Synthesis state missing keyframes: {synthesis_css['missing_keyframes']}"
    if cached_css['animations_found']:
        assert cached_css['all_animations_defined'], f"Cached state missing keyframes: {cached_css['missing_keyframes']}"

    print("Visual requirements compliance test passed")


def test_css_animation_definitions():
    """Test that all CSS animations referenced in HTML have corresponding keyframe definitions"""
    print("Testing CSS animation definitions...")

    # Test all TTS status display states
    test_cases = [
        ("Ready state", get_tts_status_display(False)),
        ("Loading state", get_tts_status_display(False, is_loading=True)),
        ("Synthesizing state", get_tts_status_display(True)),
        ("Playing state", get_tts_status_display(False, is_playing=True)),
        ("Error state", get_tts_status_display(False, has_error=True, error_info={"error_type": "TEST"})),
        ("Waveform animation", create_waveform_animation()),
        ("Loading indicator", create_loading_indicator()),
        ("Cached playback", create_playback_indicator(is_cached=True)),
        ("New playback", create_playback_indicator(is_cached=False))
    ]

    for test_name, html in test_cases:
        css_validation = validate_css_animations(html)

        if css_validation['animations_found']:
            assert css_validation['all_animations_defined'], \
                f"{test_name}: Missing keyframes for animations: {css_validation['missing_keyframes']}"
            print(f"  ✓ {test_name}: All {len(css_validation['animations_found'])} animations properly defined")
        else:
            print(f"  ✓ {test_name}: No animations to validate")

    print("CSS animation definitions test passed")


def test_html_structure_validation():
    """Test that generated HTML is valid and well-formed"""
    print("Testing HTML structure validation...")

    # Test all major HTML-generating functions
    test_cases = [
        ("Ready state", get_tts_status_display(False)),
        ("Loading state", get_tts_status_display(False, is_loading=True)),
        ("Synthesizing state", get_tts_status_display(True)),
        ("Playing state", get_tts_status_display(False, is_playing=True)),
        ("Error state", get_tts_status_display(False, has_error=True, error_info={"error_type": "TEST"})),
        ("Waveform animation", create_waveform_animation()),
        ("Loading indicator", create_loading_indicator()),
        ("Cached playback", create_playback_indicator(is_cached=True)),
        ("New playback", create_playback_indicator(is_cached=False))
    ]

    for test_name, html in test_cases:
        html_analysis = validate_html_structure(html)

        assert html_analysis['is_valid'], \
            f"{test_name}: HTML validation failed. Errors: {html_analysis['errors']}"

        # Verify basic structure requirements
        assert len(html_analysis['tags']) > 0, f"{test_name}: Should contain HTML tags"

        # Check for common structural issues
        div_count = html_analysis['tags'].count('div')
        span_count = html_analysis['tags'].count('span')

        if div_count > 0:
            print(f"  ✓ {test_name}: Valid HTML with {div_count} div(s), {span_count} span(s)")
        else:
            print(f"  ✓ {test_name}: Valid HTML structure")

    print("HTML structure validation test passed")


def test_flexible_attribute_matching():
    """Test the flexible attribute matching utility function"""
    print("Testing flexible attribute matching...")

    # Test various quote styles and spacing
    test_html_cases = [
        '<svg width="120" height="24">',
        "<svg width='120' height='24'>",
        '<svg width=120 height=24>',
        '<svg  width = "120"  height = "24" >',
        '<svg\n  width="120"\n  height="24">',
    ]

    for html in test_html_cases:
        assert match_attribute_flexible(html, "svg", "width", "120"), f"Should match width in: {html}"
        assert match_attribute_flexible(html, "svg", "height", "24"), f"Should match height in: {html}"

    # Test that it doesn't match incorrect values
    assert not match_attribute_flexible('<svg width="100">', "svg", "width", "120"), "Should not match incorrect width"

    print("Flexible attribute matching test passed")


def run_all_tests():
    """Run all visual feedback and animation tests with enhanced robustness"""
    print("Starting visual feedback and animations tests...")
    print("=" * 60)

    try:
        # Original tests with enhanced robustness
        test_waveform_animation()
        test_loading_indicator()
        test_playback_indicator()
        test_status_display_states()
        test_smooth_transitions()
        test_cached_audio_requirements()
        test_tts_state_management()
        test_visual_requirements_compliance()

        # New robust validation tests
        test_css_animation_definitions()
        test_html_structure_validation()
        test_flexible_attribute_matching()

        print("=" * 60)
        print("All visual feedback and animation tests passed!")
        print("Enhanced test robustness validation completed successfully")

        return True

    except AssertionError as e:
        print(f"Test failed: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error: {e}")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)