#!/usr/bin/env python3
"""
Bitcoin Knowledge Assistant Web UI using Gradio
"""

import os
import sys
from pathlib import Path
from typing import Tuple, Optional, Dict, Any
import time
import threading

import gradio as gr
import requests

# Import validation function
try:
    from test_user_controls_simple import validate_volume
except ImportError:
    # Fallback validation function if import fails
    def validate_volume(volume):
        """Validate volume is between 0.0 and 1.0"""
        return 0.0 <= volume <= 1.0


# Add project root to path with guard against duplicates
def _add_project_root_to_path():
    """Add project root directory to sys.path if not already present."""
    current_file = Path(__file__).resolve()
    project_root = current_file.parent.parent.parent
    project_root_str = str(project_root)
    
    if project_root_str not in sys.path:
        sys.path.insert(0, project_root_str)


_add_project_root_to_path()


# Configuration
API_BASE_URL = "http://localhost:8000"


def query_bitcoin_assistant(question: str, tts_enabled: bool = False) -> Tuple[str, str, Optional[str]]:
    """Query the Bitcoin Assistant API with optional TTS (legacy function)"""

    if not question.strip():
        return "Please enter a question about Bitcoin or blockchain technology.", "", None

    try:
        # Prepare request payload
        payload = {"question": question}
        if tts_enabled:
            payload["enable_tts"] = True

        response = requests.post(
            f"{API_BASE_URL}/query",
            json=payload,
            timeout=30,
        )
        response.raise_for_status()

        try:
            data = response.json()
        except ValueError:
            return "❌ API returned non-JSON payload.", "", None

        answer = data.get("answer", "No answer received")

        # Format sources
        sources = data.get("sources", [])
        sources_text = ""
        if sources:
            sources_text = "**Sources:**\n"
            for i, source in enumerate(sources[:5], 1):
                sources_text += f"{i}. {source.get('name', 'Unknown')}\n"

        # Get audio data if available
        audio_data = data.get("audio_data")

        return answer, sources_text, audio_data

    except requests.exceptions.ConnectionError:
        return (
            "❌ Cannot connect to Bitcoin Assistant API. Make sure the FastAPI server is running on port 8000.",
            "",
            None,
        )
    except requests.exceptions.RequestException as e:
        if hasattr(e, 'response') and e.response is not None:
            error_msg = f"API Error ({e.response.status_code}): {e.response.text}"
            return error_msg, "", None
        else:
            return f"❌ Request Error: {str(e)}", "", None
    except requests.exceptions.ConnectionError:
        return (
            "❌ Cannot connect to Bitcoin Assistant API. Make sure the FastAPI server is running on port 8000.",
            "",
            None,
        )
    except Exception as e:
        return f"❌ Error: {str(e)}", "", None


def query_bitcoin_assistant_with_streaming(question: str, tts_enabled: bool = False, volume: float = 0.7) -> Tuple[str, str, Optional[str], Optional[Dict]]:
    """Query the Bitcoin Assistant API with streaming TTS support"""

    if not question.strip():
        return "Please enter a question about Bitcoin or blockchain technology.", "", None, None

    try:
        # Validate volume parameter
        if not validate_volume(volume):
            # Clamp volume to valid range
            volume = max(0.0, min(1.0, volume))
            print(f"Warning: Volume clamped to valid range: {volume}")

        # Prepare request payload
        payload = {"question": question}
        if tts_enabled:
            payload["enable_tts"] = True
            payload["volume"] = volume

        response = requests.post(
            f"{API_BASE_URL}/query",
            json=payload,
            timeout=30,
        )
        response.raise_for_status()

        try:
            data = response.json()
        except ValueError:
            return "❌ API returned non-JSON payload.", "", None, None

        answer = data.get("answer", "No answer received")

        # Format sources
        sources = data.get("sources", [])
        sources_text = ""
        if sources:
            sources_text = "**Sources:**\n"
            for i, source in enumerate(sources[:5], 1):
                sources_text += f"{i}. {source.get('name', 'Unknown')}\n"

        # Get audio data and streaming info
        audio_data = data.get("audio_data")
        streaming_data = data.get("audio_streaming_data")
        
        # Create streaming info for UI
        streaming_info = None
        if streaming_data:
            streaming_info = {
                "instant_replay": streaming_data.get("instant_replay", False),
                "is_cached": streaming_data.get("is_cached", False),
                "synthesis_time": streaming_data.get("synthesis_time", 0.0),
                "duration": streaming_data.get("duration"),
                "size_bytes": streaming_data.get("size_bytes")
            }
        elif data.get("tts_cached"):
            # Fallback for legacy cached responses
            streaming_info = {
                "instant_replay": True,
                "is_cached": True,
                "synthesis_time": 0.0
            }

        # Process audio for streaming playback
        processed_audio = None
        if audio_data and tts_enabled:
            # For Gradio, we can use the audio_data directly
            # The streaming manager has already prepared it in the right format
            processed_audio = audio_data

        return answer, sources_text, processed_audio, streaming_info

    except requests.exceptions.ConnectionError:
        return (
            "❌ Cannot connect to Bitcoin Assistant API. Make sure the FastAPI server is running on port 8000.",
            "",
            None,
            None,
        )
    except requests.exceptions.RequestException as e:
        if hasattr(e, 'response') and e.response is not None:
            error_msg = f"API Error ({e.response.status_code}): {e.response.text}"
            return error_msg, "", None, None
        else:
            return f"❌ Request Error: {str(e)}", "", None, None
    except Exception as e:
        return f"❌ Error: {str(e)}", "", None, None


def get_available_sources() -> str:
    """Get list of available sources"""
    try:
        response = requests.get(f"{API_BASE_URL}/sources", timeout=10)

        if response.status_code == 200:
            data = response.json()
            sources = data.get("available_sources", [])
            total = data.get("total_sources", 0)

            if sources:
                sources_list = "\n".join([f"• {source}" for source in sources])
                return f"**Available Sources ({total} total):**\n\n{sources_list}"
            else:
                return "No sources found in the knowledge base."
        else:
            return f"Error fetching sources: {response.text}"

    except Exception as e:
        return f"Error: {str(e)}"


def check_api_health() -> str:
    """Check API health status"""
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=10)

        if response.status_code == 200:
            data = response.json()
            status = data.get("status", "unknown")
            pinecone_status = data.get("pinecone_assistant", "unknown")
            server_info = data.get("server_info", {})

            return f"✅ **API Status:** {status}\n✅ **Pinecone Assistant:** {pinecone_status}\n📊 **Server:** {server_info.get('name', 'Unknown')} v{server_info.get('version', 'Unknown')}"
        else:
            return f"❌ **API Health Check Failed:** {response.text}"

    except Exception as e:
        return f"❌ **Connection Error:** {str(e)}"


# Sample questions for quick testing
# Sample questions for quick testing
SAMPLE_QUESTIONS = [
    "What is Bitcoin and how does it work?",
    "Explain the Lightning Network",
    "What are the key features of blockchain technology?",
    "Tell me about the GENIUS Act",
    "What are decentralized applications (dApps)?",
    "How does Bitcoin mining work?",
    "What is the difference between Bitcoin and traditional currency?",
    "Explain Bitcoin's proof-of-work consensus mechanism",
]


# TTS State Management
class TTSState:
    """Manages TTS state and animations with thread-safe operations"""
    def __init__(self):
        self.is_synthesizing = False
        self.synthesis_start_time = None
        self.stop_animation = False
        self._lock = threading.Lock()

    def start_synthesis(self):
        """Start synthesis animation (thread-safe)"""
        with self._lock:
            self.is_synthesizing = True
            self.synthesis_start_time = time.time()
            self.stop_animation = False

    def stop_synthesis(self):
        """Stop synthesis animation (thread-safe)"""
        with self._lock:
            self.is_synthesizing = False
            self.stop_animation = True


# Global TTS state
tts_state = TTSState()


def create_loading_indicator() -> str:
    """Create loading indicator for TTS processing state"""
    return """
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
    """


def create_playback_indicator(is_cached: bool = False) -> str:
    """Create playback indicator with different styles for cached vs new audio"""
    if is_cached:
        return """
        <div style="display: flex; align-items: center; justify-content: center; padding: 10px; transition: all 0.3s ease-in-out;">
            <div style="display: flex; align-items: center; gap: 4px;">
                <div style="width: 0; height: 0; border-left: 8px solid #10b981; border-top: 6px solid transparent; border-bottom: 6px solid transparent; animation: pulse 1.5s infinite;"></div>
                <div style="width: 2px; height: 12px; background-color: #10b981; margin-left: 2px; animation: pulse 1.5s infinite;"></div>
                <div style="width: 2px; height: 16px; background-color: #10b981; animation: pulse 1.5s infinite; animation-delay: 0.1s;"></div>
                <div style="width: 2px; height: 10px; background-color: #10b981; animation: pulse 1.5s infinite; animation-delay: 0.2s;"></div>
                <div style="width: 2px; height: 14px; background-color: #10b981; animation: pulse 1.5s infinite; animation-delay: 0.3s;"></div>
            </div>
            <span style="margin-left: 12px; color: #10b981; font-size: 14px; font-weight: 500;">⚡ Playing cached audio</span>
        </div>
        """
    else:
        return """
        <div style="display: flex; align-items: center; justify-content: center; padding: 10px; transition: all 0.3s ease-in-out;">
            <div style="display: flex; align-items: center; gap: 4px;">
                <div style="width: 0; height: 0; border-left: 8px solid #3b82f6; border-top: 6px solid transparent; border-bottom: 6px solid transparent; animation: pulse 1.5s infinite;"></div>
                <div style="width: 2px; height: 12px; background-color: #3b82f6; margin-left: 2px; animation: pulse 1.5s infinite;"></div>
                <div style="width: 2px; height: 16px; background-color: #3b82f6; animation: pulse 1.5s infinite; animation-delay: 0.1s;"></div>
                <div style="width: 2px; height: 10px; background-color: #3b82f6; animation: pulse 1.5s infinite; animation-delay: 0.2s;"></div>
                <div style="width: 2px; height: 14px; background-color: #3b82f6; animation: pulse 1.5s infinite; animation-delay: 0.3s;"></div>
            </div>
            <span style="margin-left: 12px; color: #3b82f6; font-size: 14px; font-weight: 500;">🔊 Playing synthesized audio</span>
        </div>
        """


def create_waveform_animation() -> str:
    """Create enhanced animated waveform SVG for TTS synthesis with smooth transitions"""
    
    # Define bar configurations: (x, y, height, opacity, duration)
    bar_configs = [
        (2, 8, 8, 0.9, 0.8), (6, 6, 12, 0.8, 1.1), (10, 10, 4, 0.7, 0.6), (14, 7, 10, 0.9, 0.9),
        (18, 9, 6, 0.6, 1.3), (22, 5, 14, 0.8, 1.0), (26, 8, 8, 0.9, 0.7), (30, 11, 2, 0.7, 1.2),
        (34, 7, 10, 0.8, 0.8), (38, 9, 6, 0.6, 1.1), (42, 6, 12, 0.9, 0.9), (46, 10, 4, 0.7, 0.6),
        (50, 8, 8, 0.8, 1.0), (54, 7, 10, 0.9, 0.7), (58, 9, 6, 0.6, 1.3), (62, 5, 14, 0.8, 1.1),
        (66, 8, 8, 0.9, 0.8), (70, 11, 2, 0.7, 0.9), (74, 7, 10, 0.8, 1.2), (78, 9, 6, 0.6, 0.7),
        (82, 6, 12, 0.9, 1.0), (86, 10, 4, 0.7, 0.8), (90, 8, 8, 0.8, 1.1), (94, 7, 10, 0.9, 0.6),
        (98, 9, 6, 0.6, 1.3), (102, 5, 14, 0.8, 0.9), (106, 8, 8, 0.9, 0.7), (110, 11, 2, 0.7, 1.0),
        (114, 7, 10, 0.8, 0.8)
    ]
    
    # Generate rect elements programmatically
    rect_elements = []
    for x, y, height, opacity, duration in bar_configs:
        # Calculate animated values
        max_height = height + 8  # Add 8 for animation range
        min_y = y - 4  # Adjust y position for animation
        
        rect_element = f'''            <rect x="{x}" y="{y}" width="2" height="{height}" fill="#3b82f6" opacity="{opacity}" rx="1">
                <animate attributeName="height" values="{height};{max_height};{height}" dur="{duration}s" repeatCount="indefinite"/>
                <animate attributeName="y" values="{y};{min_y};{y}" dur="{duration}s" repeatCount="indefinite"/>
                <animate attributeName="opacity" values="{opacity};1;{opacity}" dur="{duration}s" repeatCount="indefinite"/>
            </rect>'''
        rect_elements.append(rect_element)
    
    # Join all rect elements
    rects_html = '\n'.join(rect_elements)
    
    return f"""
    <div style="display: flex; align-items: center; justify-content: center; padding: 10px; transition: all 0.3s ease-in-out;">
        <svg width="120" height="24" viewBox="0 0 120 24" style="filter: drop-shadow(0 2px 4px rgba(59, 130, 246, 0.2));">
            <!-- Enhanced waveform with programmatically generated bars -->
{rects_html}
        </svg>
        <span style="margin-left: 12px; color: #3b82f6; font-size: 14px; font-weight: 500; animation: pulse 2s infinite;">Synthesizing speech...</span>
    </div>
    """


def check_tts_status() -> Tuple[bool, Optional[Dict]]:
    """Check TTS service status and return error information"""
    try:
        response = requests.get(f"{API_BASE_URL}/tts/status", timeout=5)
        if response.status_code == 200:
            data = response.json()
            error_state = data.get("error_state", {})
            has_error = error_state.get("has_error", False)
            return has_error, error_state if has_error else None
        else:
            return True, {"error_type": "API_ERROR", "error_message": "Failed to check TTS status"}
    except Exception as e:
        return True, {"error_type": "CONNECTION_ERROR", "error_message": str(e)}


def get_tts_status_display(is_synthesizing: bool, has_error: bool = False, error_info: Optional[Dict] = None,
                          is_loading: bool = False, is_playing: bool = False, is_cached: bool = False,
                          is_disabled: bool = False, synthesis_time: Optional[float] = None) -> str:
    """Get TTS status display HTML with comprehensive visual feedback and smooth transitions"""

    # Handle voice disabled state
    if is_disabled:
        return f"""
        <div class="tts-status ready" style="display: flex; align-items: center; justify-content: center; padding: 10px; background: linear-gradient(135deg, #f3f4f6 0%, #e5e7eb 100%); border: 1px solid #d1d5db; border-radius: 8px; transition: all 0.3s ease-in-out;">
            <span style="color: #6b7280; font-size: 13px; font-weight: 500;">🔇 Voice disabled</span>
        </div>
        """

    # CSS keyframes for animations (included for standalone usage)
    css_keyframes = """
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
    """

    # Handle error states with enhanced visual feedback
    if has_error and error_info:
        error_type = error_info.get("error_type", "UNKNOWN")
        error_message = error_info.get("error_message", "TTS service error")
        consecutive_failures = error_info.get("consecutive_failures", 0)
        is_muted = error_info.get("is_muted", False)
        
        # Create user-friendly error messages with appropriate visual indicators
        if error_type == "API_KEY_ERROR":
            display_message = "🔴 Invalid API key - Voice disabled"
            tooltip = "The ElevenLabs API key is missing or invalid. Text display continues normally. Please check your ELEVEN_LABS_API_KEY environment variable."
            color = "#dc2626"  # Red for critical errors
        elif error_type == "RATE_LIMIT":
            display_message = "🟡 Rate limited - Retrying automatically"
            tooltip = f"ElevenLabs API rate limit exceeded. The service will automatically retry with exponential backoff. Text display continues normally. Failures: {consecutive_failures}"
            color = "#f59e0b"  # Amber for temporary issues
        elif error_type.startswith("SERVER_ERROR"):
            display_message = "🟠 Server error - Retrying automatically"
            tooltip = f"ElevenLabs server is experiencing issues. The service will automatically retry. Text display continues normally. Failures: {consecutive_failures}"
            color = "#ea580c"  # Orange for server issues
        elif error_type == "NETWORK_ERROR":
            display_message = "🔴 Network error - Check connection"
            tooltip = f"Network connectivity issues detected. Please check your internet connection. Text display continues normally. Failures: {consecutive_failures}"
            color = "#dc2626"  # Red for network issues
        elif error_type == "RETRY_EXHAUSTED":
            display_message = "🔴 Voice synthesis failed - Text continues"
            tooltip = f"All retry attempts exhausted. Voice synthesis is temporarily disabled but text display continues normally. The service will attempt recovery automatically."
            color = "#dc2626"  # Red for exhausted retries
        elif error_type == "SYNTHESIS_FAILED":
            display_message = "🔴 Synthesis failed - Text continues"
            tooltip = "Audio synthesis failed for this response. Text display continues normally. The service will attempt recovery on the next request."
            color = "#dc2626"  # Red for synthesis failures
        else:
            display_message = "🔴 TTS service error - Text continues"
            tooltip = f"TTS service error: {error_message}. Text display continues normally. Failures: {consecutive_failures}"
            color = "#dc2626"  # Red for unknown errors
        
        # Add muted state indicator if applicable
        muted_indicator = " (Muted)" if is_muted else ""
        
        return f"""
        {css_keyframes}
        <div class="tts-status error" style="display: flex; align-items: center; justify-content: center; padding: 10px; background: linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%); border: 1px solid #fca5a5; border-radius: 8px; transition: all 0.3s ease-in-out;" title="{tooltip}">
            <span style="color: {color}; font-size: 13px; cursor: help; font-weight: 500; animation: fade-in 0.3s ease-in-out;">{display_message}{muted_indicator}</span>
        </div>
        """
    elif has_error:
        # Fallback error display for cases without detailed error info
        return f"""
        {css_keyframes}
        <div class="tts-status error" style="display: flex; align-items: center; justify-content: center; padding: 10px; background: linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%); border: 1px solid #fca5a5; border-radius: 8px; transition: all 0.3s ease-in-out;" title="Text-to-speech service temporarily unavailable - text will continue to display normally">
            <span style="color: #dc2626; font-size: 13px; cursor: help; font-weight: 500; animation: fade-in 0.3s ease-in-out;">🔴 TTS Error - Text continues normally</span>
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
        # Show waveform animation during synthesis (hide for cached audio per requirement 3.5)
        return f"""
        <div class="tts-status synthesizing" style="background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%); border: 1px solid #93c5fd; border-radius: 8px; transition: all 0.3s ease-in-out;">
            {create_waveform_animation()}
        </div>
        """
    elif is_playing:
        # Show playback indicator with different styles for cached vs new audio
        if is_cached:
            # Instant replay status with enhanced styling
            return f"""
            <div class="tts-status playing" style="display: flex; align-items: center; justify-content: center; padding: 10px; background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%); border: 1px solid #86efac; border-radius: 8px; transition: all 0.3s ease-in-out;">
                <div style="display: flex; align-items: center; gap: 8px;">
                    <div style="width: 0; height: 0; border-left: 8px solid #10b981; border-top: 6px solid transparent; border-bottom: 6px solid transparent;"></div>
                    <span style="color: #10b981; font-size: 13px; font-weight: 500; animation: fade-in 0.3s ease-in-out;">⚡ Instant replay (cached)</span>
                </div>
            </div>
            """
        elif synthesis_time is not None:
            # Synthesis completion status with timing
            return f"""
            <div class="tts-status playing" style="display: flex; align-items: center; justify-content: center; padding: 10px; background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%); border: 1px solid #93c5fd; border-radius: 8px; transition: all 0.3s ease-in-out;">
                <div style="display: flex; align-items: center; gap: 8px;">
                    <div style="width: 0; height: 0; border-left: 8px solid #3b82f6; border-top: 6px solid transparent; border-bottom: 6px solid transparent;"></div>
                    <span style="color: #3b82f6; font-size: 13px; font-weight: 500; animation: fade-in 0.3s ease-in-out;">🔊 Synthesized in {synthesis_time:.1f}s</span>
                </div>
            </div>
            """
        else:
            # Default playback indicator
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
            <span style="color: #6b7280; font-size: 13px; font-weight: 500; animation: fade-in 0.3s ease-in-out;">🔊 Ready for voice synthesis</span>
        </div>
        """


# Create Gradio interface
def create_bitcoin_assistant_ui():
    """Create the Gradio web interface"""

    with gr.Blocks(
        title="Bitcoin Knowledge Assistant",
        theme=gr.themes.Soft(),
        css="""
        .gradio-container {
            max-width: 1200px !important;
        }
        .question-box {
            min-height: 100px;
        }
        .answer-box {
            min-height: 200px;
        }
        .tts-controls {
            background-color: #f8fafc;
            border-radius: 8px;
            padding: 15px;
            margin-top: 10px;
            transition: all 0.3s ease-in-out;
        }
        .tts-status {
            text-align: center;
            padding: 10px;
            border-radius: 6px;
            background-color: #ffffff;
            border: 1px solid #e5e7eb;
            transition: all 0.3s ease-in-out;
            min-height: 50px;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .audio-component {
            margin-top: 10px;
            transition: opacity 0.3s ease-in-out;
        }
        
        /* Enhanced animations for visual feedback */
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
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
        
        @keyframes fade-out {
            from { 
                opacity: 1; 
                transform: translateY(0); 
            }
            to { 
                opacity: 0; 
                transform: translateY(-10px); 
            }
        }
        
        @keyframes slide-in {
            from { 
                opacity: 0; 
                transform: translateX(-20px); 
            }
            to { 
                opacity: 1; 
                transform: translateX(0); 
            }
        }
        
        /* State-specific styling */
        .tts-status.synthesizing {
            background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
            border-color: #93c5fd;
            animation: fade-in 0.3s ease-in-out;
        }
        
        .tts-status.playing {
            background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%);
            border-color: #86efac;
            animation: fade-in 0.3s ease-in-out;
        }
        
        .tts-status.error {
            background: linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%);
            border-color: #fca5a5;
            animation: fade-in 0.3s ease-in-out;
        }
        
        .tts-status.ready {
            background: linear-gradient(135deg, #f9fafb 0%, #f3f4f6 100%);
            border-color: #d1d5db;
            animation: fade-in 0.3s ease-in-out;
        }
        
        /* Smooth transitions for all interactive elements */
        .tts-controls input, .tts-controls button {
            transition: all 0.2s ease-in-out;
        }
        
        .tts-controls input:hover, .tts-controls button:hover {
            transform: translateY(-1px);
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
        }
        """,
        js="""
        function() {
            // TTS Settings persistence in localStorage
            const TTS_SETTINGS_KEY = 'btc_assistant_tts_settings';

            // Default settings per requirements 2.8
            const DEFAULT_SETTINGS = {
                tts_enabled: true,
                volume: 0.7
            };

            // Debounce timer for volume slider
            let volumeDebounceTimer = null;
            const VOLUME_DEBOUNCE_DELAY = 300; // 300ms delay

            // Retry configuration
            const RETRY_CONFIG = {
                maxAttempts: 10,
                baseDelay: 50,
                maxDelay: 2000,
                backoffFactor: 1.5
            };

            // Load settings from localStorage or use defaults
            function loadTTSSettings() {
                try {
                    const stored = localStorage.getItem(TTS_SETTINGS_KEY);
                    if (stored) {
                        const settings = JSON.parse(stored);
                        return {
                            tts_enabled: settings.tts_enabled !== undefined ? settings.tts_enabled : DEFAULT_SETTINGS.tts_enabled,
                            volume: settings.volume !== undefined ? settings.volume : DEFAULT_SETTINGS.volume
                        };
                    }
                } catch (e) {
                    console.warn('Failed to load TTS settings from localStorage:', e);
                }
                return DEFAULT_SETTINGS;
            }

            // Save settings to localStorage
            function saveTTSSettings(settings) {
                try {
                    localStorage.setItem(TTS_SETTINGS_KEY, JSON.stringify(settings));
                } catch (e) {
                    console.warn('Failed to save TTS settings to localStorage:', e);
                }
            }

            // Debounced save function for volume settings
            function debouncedSaveVolume(volume) {
                if (volumeDebounceTimer) {
                    clearTimeout(volumeDebounceTimer);
                }
                volumeDebounceTimer = setTimeout(() => {
                    const currentSettings = loadTTSSettings();
                    currentSettings.volume = volume;
                    saveTTSSettings(currentSettings);
                }, VOLUME_DEBOUNCE_DELAY);
            }

            // Retry function with exponential backoff
            async function retryWithBackoff(fn, description) {
                for (let attempt = 1; attempt <= RETRY_CONFIG.maxAttempts; attempt++) {
                    try {
                        const result = await fn();
                        if (result) {
                            return result;
                        }
                    } catch (e) {
                        console.warn(`${description} attempt ${attempt} failed:`, e);
                    }

                    if (attempt < RETRY_CONFIG.maxAttempts) {
                        const delay = Math.min(
                            RETRY_CONFIG.baseDelay * Math.pow(RETRY_CONFIG.backoffFactor, attempt - 1),
                            RETRY_CONFIG.maxDelay
                        );
                        await new Promise(resolve => setTimeout(resolve, delay));
                    }
                }
                console.error(`${description} failed after ${RETRY_CONFIG.maxAttempts} attempts`);
                return null;
            }

            // Find TTS elements with stable selectors and fallbacks
            async function findTTSElements() {
                return new Promise((resolve) => {
                    // Primary selectors using elem_id
                    const ttsCheckbox = document.querySelector('#tts-enable-checkbox input[type="checkbox"]') ||
                                       document.querySelector('[data-testid="tts-enable-checkbox"] input[type="checkbox"]');

                    const volumeSlider = document.querySelector('#tts-volume-slider input[type="range"]') ||
                                        document.querySelector('[data-testid="tts-volume-slider"] input[type="range"]');

                    // Fallback selectors (less reliable but better than text-based)
                    const fallbackCheckbox = !ttsCheckbox ? document.querySelector('input[type="checkbox"]') : null;
                    const fallbackSlider = !volumeSlider ? document.querySelector('input[type="range"]') : null;

                    // Validate fallback elements by checking nearby text content
                    let validatedCheckbox = ttsCheckbox;
                    let validatedSlider = volumeSlider;

                    if (!validatedCheckbox && fallbackCheckbox) {
                        const checkboxContainer = fallbackCheckbox.closest('.gr-form, .gradio-container, [class*="checkbox"]');
                        if (checkboxContainer && checkboxContainer.textContent.includes('Enable Voice')) {
                            validatedCheckbox = fallbackCheckbox;
                        }
                    }

                    if (!validatedSlider && fallbackSlider) {
                        const sliderContainer = fallbackSlider.closest('.gr-form, .gradio-container, [class*="slider"]');
                        if (sliderContainer && sliderContainer.textContent.includes('Voice Volume')) {
                            validatedSlider = fallbackSlider;
                        }
                    }

                    resolve({
                        checkbox: validatedCheckbox,
                        slider: validatedSlider,
                        found: !!(validatedCheckbox && validatedSlider)
                    });
                });
            }
            
            // Initialize settings on page load with retry logic
            async function initializeTTSSettings() {
                const settings = loadTTSSettings();

                const elements = await retryWithBackoff(findTTSElements, 'Finding TTS elements for initialization');
                if (!elements || !elements.found) {
                    console.warn('Could not find TTS elements for initialization');
                    return;
                }

                // Set checkbox value
                if (elements.checkbox) {
                    elements.checkbox.checked = settings.tts_enabled;
                    elements.checkbox.dispatchEvent(new Event('change', { bubbles: true }));
                }

                // Set slider value
                if (elements.slider) {
                    elements.slider.value = settings.volume;
                    elements.slider.dispatchEvent(new Event('input', { bubbles: true }));
                }
            }

            // Set up event listeners for settings persistence with retry logic
            async function setupTTSPersistence() {
                const elements = await retryWithBackoff(findTTSElements, 'Finding TTS elements for persistence setup');
                if (!elements || !elements.found) {
                    console.warn('Could not find TTS elements for persistence setup');
                    return;
                }

                // Set up checkbox change listener
                if (elements.checkbox) {
                    elements.checkbox.addEventListener('change', function() {
                        const currentSettings = loadTTSSettings();
                        currentSettings.tts_enabled = this.checked;
                        saveTTSSettings(currentSettings);
                    });
                }

                // Set up volume slider input listener with debouncing
                if (elements.slider) {
                    elements.slider.addEventListener('input', function() {
                        const volume = parseFloat(this.value);
                        debouncedSaveVolume(volume);
                    });
                }
            }
            
            // Initialize on page load
            (async function() {
                await initializeTTSSettings();
                await setupTTSPersistence();
            })();

            // Re-initialize when Gradio updates the interface
            const observer = new MutationObserver(function(mutations) {
                let shouldReinitialize = false;
                mutations.forEach(function(mutation) {
                    if (mutation.type === 'childList' && mutation.addedNodes.length > 0) {
                        // Check if any added nodes contain TTS-related elements
                        for (const node of mutation.addedNodes) {
                            if (node.nodeType === Node.ELEMENT_NODE) {
                                if (node.querySelector && (
                                    node.querySelector('#tts-enable-checkbox, #tts-volume-slider') ||
                                    node.id === 'tts-enable-checkbox' ||
                                    node.id === 'tts-volume-slider'
                                )) {
                                    shouldReinitialize = true;
                                    break;
                                }
                            }
                        }
                    }
                });

                if (shouldReinitialize) {
                    // Debounce re-initialization to avoid excessive calls
                    clearTimeout(window.ttsReinitTimer);
                    window.ttsReinitTimer = setTimeout(async () => {
                        await initializeTTSSettings();
                        await setupTTSPersistence();
                    }, 100);
                }
            });

            observer.observe(document.body, {
                childList: true,
                subtree: true
            });
        }
        """,
    ) as interface:

        # Header
        gr.Markdown(
            """
        # 🪙 Bitcoin Knowledge Assistant
        
        Ask questions about Bitcoin, blockchain technology, Lightning Network, dApps, regulations, and more!
        
        Powered by **Pinecone Assistant** with intelligent document retrieval
        
        *Automatically finds the most relevant sources to answer your questions.*
        """
        )

        with gr.Row():
            with gr.Column(scale=2):
                # Main chat interface
                with gr.Group():
                    question_input = gr.Textbox(
                        label="Ask a Bitcoin Question",
                        placeholder="e.g., What is Bitcoin and how does it work?",
                        lines=3,
                        elem_classes=["question-box"],
                    )

                    with gr.Row():
                        submit_btn = gr.Button(
                            "Ask Question", variant="primary", size="lg"
                        )
                        clear_btn = gr.Button("Clear", variant="secondary")

                # TTS Controls - positioned beneath the chatbot window
                with gr.Group(elem_classes=["tts-controls"]):
                    gr.Markdown("### 🔊 Voice Controls")
                    
                    with gr.Row():
                        tts_enabled = gr.Checkbox(
                            label="Enable Voice",
                            value=True,  # Default value, will be overridden by JS
                            info="Toggle text-to-speech for responses",
                            elem_id="tts-enable-checkbox"
                        )

                    with gr.Row():
                        with gr.Column(scale=4):
                            volume_slider = gr.Slider(
                                minimum=0.0,
                                maximum=1.0,
                                value=0.7,  # Default value, will be overridden by JS
                                step=0.1,
                                label="Voice Volume",
                                info="Adjust audio playback volume",
                                elem_id="tts-volume-slider"
                            )
                        with gr.Column(scale=1):
                            volume_display = gr.Textbox(
                                value="Volume: 70%",
                                interactive=False,
                                show_label=False,
                                container=False
                            )
                    
                    # TTS Status and Animation Display
                    tts_status = gr.HTML(
                        value=get_tts_status_display(False),
                        elem_classes=["tts-status"]
                    )
                    
                    # Recovery button for TTS errors
                    with gr.Row():
                        tts_recovery_btn = gr.Button(
                            "🔄 Retry TTS Connection",
                            size="sm",
                            variant="secondary",
                            visible=False
                        )
                    
                    # Audio Output Component
                    audio_output = gr.Audio(
                        label="Generated Speech",
                        autoplay=True,
                        visible=True,
                        interactive=False,
                        elem_classes=["audio-component"]
                    )

                # Sample questions
                with gr.Group():
                    gr.Markdown("### 💡 Sample Questions")
                    sample_buttons = []
                    for i in range(0, len(SAMPLE_QUESTIONS), 2):
                        with gr.Row():
                            for j in range(2):
                                if i + j < len(SAMPLE_QUESTIONS):
                                    btn = gr.Button(
                                        SAMPLE_QUESTIONS[i + j],
                                        size="sm",
                                        variant="outline",
                                    )
                                    sample_buttons.append(
                                        (btn, SAMPLE_QUESTIONS[i + j])
                                    )

            with gr.Column(scale=3):
                # Answer display
                answer_output = gr.Markdown(
                    label="Answer",
                    value="Ask a question to get started!",
                    elem_classes=["answer-box"],
                )

                sources_output = gr.Markdown(label="Sources", value="")

        # Status and info section
        with gr.Row():
            with gr.Column():
                with gr.Group():
                    gr.Markdown("### 🔧 System Status")
                    status_output = gr.Markdown(
                        "Click 'Check Status' to verify API connection"
                    )
                    status_btn = gr.Button("Check Status", size="sm")

            with gr.Column():
                with gr.Group():
                    gr.Markdown("### 📚 Knowledge Base")
                    sources_list_output = gr.Markdown(
                        "Click 'List Sources' to see available documents"
                    )
                    sources_btn = gr.Button("List Sources", size="sm")

        # Event handlers
        def submit_question_with_progress(question, tts_enabled_val, volume_val):
            """Submit question with real-time progress updates and enhanced visual feedback"""
            if not question.strip():
                yield "Please enter a question.", "", get_tts_status_display(False), None, gr.update(visible=False)
                return
            
            # Skip TTS synthesis entirely if voice is disabled (Requirement 2.3)
            if not tts_enabled_val:
                # Show processing state briefly
                yield "", "", get_tts_status_display(False, is_loading=True), None, gr.update(visible=False)
                
                # Query the assistant without TTS
                answer, sources, audio_data, streaming_info = query_bitcoin_assistant_with_streaming(
                    question, False, volume_val
                )
                
                # Return with disabled status using enhanced styling
                disabled_status = get_tts_status_display(False, is_disabled=True)
                yield answer, sources, disabled_status, None, gr.update(visible=False)
                return
            
            # Show initial loading state
            yield "", "", get_tts_status_display(False, is_loading=True), None, gr.update(visible=False)
            
            # Check TTS status before starting
            has_tts_error, error_info = check_tts_status()
            
            if has_tts_error:
                # Show error immediately if TTS service is unavailable
                error_status = get_tts_status_display(False, has_error=True, error_info=error_info)
                yield "", "", error_status, None, gr.update(visible=True)
                return
            
            # Show synthesis animation during processing
            tts_state.start_synthesis()
            synthesis_status = get_tts_status_display(True)  # Show waveform animation
            yield "", "", synthesis_status, None, gr.update(visible=False)
            
            # Query the assistant with streaming support (TTS enabled)
            answer, sources, audio_data, streaming_info = query_bitcoin_assistant_with_streaming(
                question, tts_enabled_val, volume_val
            )
            
            # Stop synthesis animation
            tts_state.stop_synthesis()
            
            # Check TTS status again after query to catch any new errors
            has_tts_error_after, error_info_after = check_tts_status()
            
            # Prepare final results with enhanced visual feedback
            audio_output_val = None
            final_status = get_tts_status_display(False)
            show_recovery_button = False
            
            if has_tts_error_after:
                # TTS error occurred during synthesis
                final_status = get_tts_status_display(False, has_error=True, error_info=error_info_after)
                show_recovery_button = True
            elif audio_data:
                # Apply volume control to audio data (Requirement 2.5)
                audio_output_val = audio_data
                
                # Determine if this was cached audio (instant replay) per requirement 3.5
                is_cached_audio = streaming_info and streaming_info.get("instant_replay", False)
                
                # Show appropriate playback status with enhanced visual feedback
                if is_cached_audio:
                    # Hide animation for cached audio (Requirement 3.5) and show instant replay status
                    final_status = get_tts_status_display(False, is_playing=True, is_cached=True)
                else:
                    # Show synthesis completion status for new audio
                    synthesis_time = streaming_info.get("synthesis_time", 0) if streaming_info else 0
                    final_status = get_tts_status_display(False, is_playing=True, synthesis_time=synthesis_time)
            else:
                # TTS was enabled but no audio was returned (likely due to error)
                final_status = get_tts_status_display(False, has_error=True, error_info={"error_type": "SYNTHESIS_FAILED", "error_message": "Audio synthesis failed"})
                show_recovery_button = True
            
            yield answer, sources, final_status, audio_output_val, gr.update(visible=show_recovery_button)

        def submit_question(question, tts_enabled_val, volume_val):
            """Submit question with enhanced TTS visual feedback and smooth state transitions"""
            if not question.strip():
                return "Please enter a question.", "", get_tts_status_display(False), None, gr.update(visible=False)
            
            # Skip TTS synthesis entirely if voice is disabled (Requirement 2.3)
            if not tts_enabled_val:
                # Query the assistant without TTS
                answer, sources, audio_data, streaming_info = query_bitcoin_assistant_with_streaming(
                    question, False, volume_val
                )
                
                # Return with disabled status using enhanced styling
                disabled_status = """
                <div class="tts-status ready" style="display: flex; align-items: center; justify-content: center; padding: 10px; background: linear-gradient(135deg, #f3f4f6 0%, #e5e7eb 100%); border: 1px solid #d1d5db; border-radius: 8px; transition: all 0.3s ease-in-out;">
                    <span style="color: #6b7280; font-size: 13px; font-weight: 500;">🔇 Voice disabled</span>
                </div>
                """
                return answer, sources, disabled_status, None, gr.update(visible=False)
            
            # Check TTS status before starting (only if TTS is enabled)
            has_tts_error, error_info = check_tts_status()
            
            # Show loading indicator first, then synthesis animation if TTS is enabled and no errors
            if not has_tts_error:
                tts_state.start_synthesis()
                # Start with loading indicator for initial processing
                loading_status = get_tts_status_display(False, is_loading=True)
            else:
                loading_status = get_tts_status_display(False, has_error=True, error_info=error_info)
            
            # Query the assistant with streaming support (TTS enabled)
            answer, sources, audio_data, streaming_info = query_bitcoin_assistant_with_streaming(
                question, tts_enabled_val, volume_val
            )
            
            # Stop synthesis animation
            tts_state.stop_synthesis()
            
            # Check TTS status again after query to catch any new errors
            has_tts_error_after, error_info_after = check_tts_status()
            
            # Prepare audio output and final status based on streaming info and error state
            audio_output_val = None
            final_status = get_tts_status_display(False)
            show_recovery_button = False
            
            if has_tts_error_after:
                # TTS error occurred during synthesis
                final_status = get_tts_status_display(False, has_error=True, error_info=error_info_after)
                show_recovery_button = True
            elif audio_data:
                # Apply volume control to audio data (Requirement 2.5)
                audio_output_val = audio_data
                
                # Determine if this was cached audio (instant replay) per requirement 3.5
                is_cached_audio = streaming_info and streaming_info.get("instant_replay", False)
                
                # Show appropriate playback status with enhanced visual feedback
                if is_cached_audio:
                    # Hide animation for cached audio (Requirement 3.5) and show instant replay status
                    final_status = """
                    <div class="tts-status playing" style="display: flex; align-items: center; justify-content: center; padding: 10px; background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%); border: 1px solid #86efac; border-radius: 8px; transition: all 0.3s ease-in-out;">
                        <div style="display: flex; align-items: center; gap: 8px;">
                            <div style="width: 0; height: 0; border-left: 8px solid #10b981; border-top: 6px solid transparent; border-bottom: 6px solid transparent;"></div>
                            <span style="color: #10b981; font-size: 13px; font-weight: 500; animation: fade-in 0.3s ease-in-out;">⚡ Instant replay (cached)</span>
                        </div>
                    </div>
                    """
                else:
                    # Show synthesis completion status for new audio
                    synthesis_time = streaming_info.get("synthesis_time", 0) if streaming_info else 0
                    final_status = f"""
                    <div class="tts-status playing" style="display: flex; align-items: center; justify-content: center; padding: 10px; background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%); border: 1px solid #93c5fd; border-radius: 8px; transition: all 0.3s ease-in-out;">
                        <div style="display: flex; align-items: center; gap: 8px;">
                            <div style="width: 0; height: 0; border-left: 8px solid #3b82f6; border-top: 6px solid transparent; border-bottom: 6px solid transparent;"></div>
                            <span style="color: #3b82f6; font-size: 13px; font-weight: 500; animation: fade-in 0.3s ease-in-out;">🔊 Synthesized in {synthesis_time:.1f}s</span>
                        </div>
                    </div>
                    """
            else:
                # TTS was enabled but no audio was returned (likely due to error)
                final_status = get_tts_status_display(False, has_error=True, error_info={"error_type": "SYNTHESIS_FAILED", "error_message": "Audio synthesis failed"})
                show_recovery_button = True
            
            return answer, sources, final_status, audio_output_val, gr.update(visible=show_recovery_button)

        def set_sample_question(sample_q):
            return sample_q

        def clear_all():
            """Clear all inputs and outputs"""
            return ("", "Ask a question to get started!", "", get_tts_status_display(False), None)

        def attempt_tts_recovery():
            """Attempt to recover TTS service from error state"""
            try:
                response = requests.post(f"{API_BASE_URL}/tts/recovery", timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    if data.get("recovery_successful"):
                        return get_tts_status_display(False), gr.update(visible=False)
                    else:
                        error_state = data.get("current_error_state", {})
                        return get_tts_status_display(False, has_error=True, error_info=error_state), gr.update(visible=True)
                else:
                    return get_tts_status_display(False, has_error=True, error_info={"error_type": "RECOVERY_FAILED", "error_message": "Recovery request failed"}), gr.update(visible=True)
            except Exception as e:
                return get_tts_status_display(False, has_error=True, error_info={"error_type": "CONNECTION_ERROR", "error_message": str(e)}), gr.update(visible=True)

        def update_tts_status(tts_enabled_val):
            """Update TTS status when toggle changes with smooth transitions"""
            if tts_enabled_val:
                # Check for errors when enabling TTS
                has_error, error_info = check_tts_status()
                if has_error:
                    return (
                        get_tts_status_display(False, has_error=True, error_info=error_info),
                        gr.update(visible=True)  # Show recovery button
                    )
                else:
                    return (
                        get_tts_status_display(False),  # Ready state with enhanced styling
                        gr.update(visible=False)  # Hide recovery button
                    )
            else:
                # Enhanced disabled status with smooth transitions
                disabled_status = """
                <div class="tts-status ready" style="display: flex; align-items: center; justify-content: center; padding: 10px; background: linear-gradient(135deg, #f3f4f6 0%, #e5e7eb 100%); border: 1px solid #d1d5db; border-radius: 8px; transition: all 0.3s ease-in-out;">
                    <span style="color: #6b7280; font-size: 13px; font-weight: 500; animation: fade-in 0.3s ease-in-out;">🔇 Voice disabled</span>
                </div>
                """
                return (
                    disabled_status,
                    gr.update(visible=False)  # Hide recovery button
                )

        def update_volume_display(volume_val):
            """Update volume display when slider changes"""
            volume_percent = int(volume_val * 100)
            return f"Volume: {volume_percent}%"

        # Wire up the interface with progressive visual feedback
        submit_btn.click(
            fn=submit_question_with_progress,
            inputs=[question_input, tts_enabled, volume_slider],
            outputs=[answer_output, sources_output, tts_status, audio_output, tts_recovery_btn],
        )

        question_input.submit(
            fn=submit_question_with_progress,
            inputs=[question_input, tts_enabled, volume_slider],
            outputs=[answer_output, sources_output, tts_status, audio_output, tts_recovery_btn],
        )

        clear_btn.click(
            fn=clear_all,
            outputs=[question_input, answer_output, sources_output, tts_status, audio_output],
        )

        # Update TTS status when toggle changes
        tts_enabled.change(
            fn=update_tts_status,
            inputs=[tts_enabled],
            outputs=[tts_status, tts_recovery_btn]
        )

        # TTS recovery button
        tts_recovery_btn.click(
            fn=attempt_tts_recovery,
            outputs=[tts_status, tts_recovery_btn]
        )

        # Update volume display when slider changes
        volume_slider.change(
            fn=update_volume_display,
            inputs=[volume_slider],
            outputs=[volume_display]
        )

        status_btn.click(fn=check_api_health, outputs=status_output)

        sources_btn.click(fn=get_available_sources, outputs=sources_list_output)

        # Wire up sample question buttons
        for btn, sample_q in sample_buttons:
            btn.click(
                fn=set_sample_question,
                inputs=gr.State(sample_q),
                outputs=question_input,
            )

    return interface


if __name__ == "__main__":
    import argparse
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Bitcoin Knowledge Assistant Web UI")
    parser.add_argument("--host", default=None, help="Host to bind the server to")
    parser.add_argument("--port", type=int, default=None, help="Port to bind the server to")
    args = parser.parse_args()
    
    # Create and launch the interface
    interface = create_bitcoin_assistant_ui()

    print("🚀 Starting Bitcoin Knowledge Assistant Web UI...")
    print("📡 Make sure the FastAPI server is running on http://localhost:8000")

    # Get host and port from command line args, environment, or defaults
    ui_host = args.host or os.getenv("GRADIO_SERVER_NAME", os.getenv("UI_HOST", "0.0.0.0"))
    
    if args.port is not None:
        ui_port = args.port
    else:
        try:
            ui_port = int(os.getenv("GRADIO_SERVER_PORT", os.getenv("UI_PORT", 7860)))
        except ValueError:
            print("⚠️  Invalid UI_PORT value, defaulting to 7860")
            ui_port = 7860

    print(f"🌐 Gradio UI will be available at http://{ui_host}:{ui_port}")

    interface.launch(
        server_name=ui_host, server_port=ui_port, share=False, show_error=True
    )
