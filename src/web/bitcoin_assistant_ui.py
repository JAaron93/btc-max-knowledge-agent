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


def create_waveform_animation() -> str:
    """Create animated waveform SVG for TTS synthesis"""
    return """
    <div style="display: flex; align-items: center; justify-content: center; padding: 10px;">
        <svg width="100" height="30" viewBox="0 0 100 30">
            <rect x="5" y="10" width="3" height="10" fill="#3b82f6" opacity="0.8">
                <animate attributeName="height" values="10;20;10" dur="0.8s" repeatCount="indefinite"/>
                <animate attributeName="y" values="10;5;10" dur="0.8s" repeatCount="indefinite"/>
            </rect>
            <rect x="12" y="8" width="3" height="14" fill="#3b82f6" opacity="0.7">
                <animate attributeName="height" values="14;24;14" dur="1.2s" repeatCount="indefinite"/>
                <animate attributeName="y" values="8;3;8" dur="1.2s" repeatCount="indefinite"/>
            </rect>
            <rect x="19" y="12" width="3" height="6" fill="#3b82f6" opacity="0.9">
                <animate attributeName="height" values="6;16;6" dur="0.6s" repeatCount="indefinite"/>
                <animate attributeName="y" values="12;7;12" dur="0.6s" repeatCount="indefinite"/>
            </rect>
            <rect x="26" y="9" width="3" height="12" fill="#3b82f6" opacity="0.6">
                <animate attributeName="height" values="12;22;12" dur="1.0s" repeatCount="indefinite"/>
                <animate attributeName="y" values="9;4;9" dur="1.0s" repeatCount="indefinite"/>
            </rect>
            <rect x="33" y="11" width="3" height="8" fill="#3b82f6" opacity="0.8">
                <animate attributeName="height" values="8;18;8" dur="0.9s" repeatCount="indefinite"/>
                <animate attributeName="y" values="11;6;11" dur="0.9s" repeatCount="indefinite"/>
            </rect>
            <rect x="40" y="7" width="3" height="16" fill="#3b82f6" opacity="0.7">
                <animate attributeName="height" values="16;26;16" dur="1.1s" repeatCount="indefinite"/>
                <animate attributeName="y" values="7;2;7" dur="1.1s" repeatCount="indefinite"/>
            </rect>
            <rect x="47" y="10" width="3" height="10" fill="#3b82f6" opacity="0.9">
                <animate attributeName="height" values="10;20;10" dur="0.7s" repeatCount="indefinite"/>
                <animate attributeName="y" values="10;5;10" dur="0.7s" repeatCount="indefinite"/>
            </rect>
            <rect x="54" y="13" width="3" height="4" fill="#3b82f6" opacity="0.6">
                <animate attributeName="height" values="4;14;4" dur="1.3s" repeatCount="indefinite"/>
                <animate attributeName="y" values="13;8;13" dur="1.3s" repeatCount="indefinite"/>
            </rect>
            <rect x="61" y="9" width="3" height="12" fill="#3b82f6" opacity="0.8">
                <animate attributeName="height" values="12;22;12" dur="0.8s" repeatCount="indefinite"/>
                <animate attributeName="y" values="9;4;9" dur="0.8s" repeatCount="indefinite"/>
            </rect>
            <rect x="68" y="11" width="3" height="8" fill="#3b82f6" opacity="0.7">
                <animate attributeName="height" values="8;18;8" dur="1.0s" repeatCount="indefinite"/>
                <animate attributeName="y" values="11;6;11" dur="1.0s" repeatCount="indefinite"/>
            </rect>
            <rect x="75" y="8" width="3" height="14" fill="#3b82f6" opacity="0.9">
                <animate attributeName="height" values="14;24;14" dur="0.9s" repeatCount="indefinite"/>
                <animate attributeName="y" values="8;3;8" dur="0.9s" repeatCount="indefinite"/>
            </rect>
            <rect x="82" y="12" width="3" height="6" fill="#3b82f6" opacity="0.6">
                <animate attributeName="height" values="6;16;6" dur="1.1s" repeatCount="indefinite"/>
                <animate attributeName="y" values="12;7;12" dur="1.1s" repeatCount="indefinite"/>
            </rect>
            <rect x="89" y="10" width="3" height="10" fill="#3b82f6" opacity="0.8">
                <animate attributeName="height" values="10;20;10" dur="0.7s" repeatCount="indefinite"/>
                <animate attributeName="y" values="10;5;10" dur="0.7s" repeatCount="indefinite"/>
            </rect>
        </svg>
        <span style="margin-left: 10px; color: #3b82f6; font-size: 14px;">Synthesizing speech...</span>
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


def get_tts_status_display(is_synthesizing: bool, has_error: bool = False, error_info: Optional[Dict] = None) -> str:
    """Get TTS status display HTML with comprehensive error information and graceful fallback"""
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
        <div style="display: flex; align-items: center; justify-content: center; padding: 8px; background-color: #fef2f2; border: 1px solid #fecaca; border-radius: 6px;" title="{tooltip}">
            <span style="color: {color}; font-size: 12px; cursor: help; font-weight: 500;">{display_message}{muted_indicator}</span>
        </div>
        """
    elif has_error:
        # Fallback error display for cases without detailed error info
        return """
        <div style="display: flex; align-items: center; justify-content: center; padding: 8px; background-color: #fef2f2; border: 1px solid #fecaca; border-radius: 6px;" title="Text-to-speech service temporarily unavailable - text will continue to display normally">
            <span style="color: #dc2626; font-size: 12px; cursor: help; font-weight: 500;">🔴 TTS Error - Text continues normally</span>
        </div>
        """
    elif is_synthesizing:
        return create_waveform_animation()
    else:
        return """
        <div style="display: flex; align-items: center; justify-content: center; padding: 5px;">
            <span style="color: #6b7280; font-size: 12px;">🔊 Ready for voice synthesis</span>
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
        }
        .tts-status {
            text-align: center;
            padding: 10px;
            border-radius: 6px;
            background-color: #ffffff;
            border: 1px solid #e5e7eb;
        }
        .audio-component {
            margin-top: 10px;
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
                            value=True,
                            info="Toggle text-to-speech for responses"
                        )
                        
                    with gr.Row():
                        with gr.Column(scale=4):
                            volume_slider = gr.Slider(
                                minimum=0.0,
                                maximum=1.0,
                                value=0.7,
                                step=0.1,
                                label="Voice Volume",
                                info="Adjust audio playback volume"
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
        def submit_question(question, tts_enabled_val, volume_val):
            """Submit question with TTS streaming support and comprehensive error handling"""
            if not question.strip():
                return "Please enter a question.", "", get_tts_status_display(False), None, gr.update(visible=False)
            
            # Check TTS status before starting
            has_tts_error, error_info = check_tts_status()
            
            # Show synthesis animation if TTS is enabled and no errors
            if tts_enabled_val and not has_tts_error:
                tts_state.start_synthesis()
                synthesis_status = get_tts_status_display(True)
            elif has_tts_error:
                synthesis_status = get_tts_status_display(False, has_error=True, error_info=error_info)
            else:
                synthesis_status = get_tts_status_display(False)
            
            # Query the assistant with streaming support
            answer, sources, audio_data, streaming_info = query_bitcoin_assistant_with_streaming(
                question, tts_enabled_val, volume_val
            )
            
            # Stop synthesis animation
            tts_state.stop_synthesis()
            
            # Check TTS status again after query to catch any new errors
            has_tts_error_after, error_info_after = check_tts_status()
            
            # Prepare audio output based on streaming info and error state
            audio_output_val = None
            final_status = get_tts_status_display(False)
            show_recovery_button = False
            
            if has_tts_error_after and tts_enabled_val:
                # TTS error occurred during synthesis
                final_status = get_tts_status_display(False, has_error=True, error_info=error_info_after)
                show_recovery_button = True
            elif audio_data and tts_enabled_val:
                audio_output_val = audio_data
                
                # Update status based on whether it was cached (instant replay)
                if streaming_info and streaming_info.get("instant_replay"):
                    final_status = """
                    <div style="display: flex; align-items: center; justify-content: center; padding: 5px;">
                        <span style="color: #10b981; font-size: 12px;">⚡ Instant replay (cached)</span>
                    </div>
                    """
                else:
                    synthesis_time = streaming_info.get("synthesis_time", 0) if streaming_info else 0
                    final_status = f"""
                    <div style="display: flex; align-items: center; justify-content: center; padding: 5px;">
                        <span style="color: #3b82f6; font-size: 12px;">🔊 Synthesized in {synthesis_time:.1f}s</span>
                    </div>
                    """
            elif tts_enabled_val:
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
            """Update TTS status when toggle changes"""
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
                        get_tts_status_display(False),
                        gr.update(visible=False)  # Hide recovery button
                    )
            else:
                return (
                    """
                    <div style="display: flex; align-items: center; justify-content: center; padding: 5px;">
                        <span style="color: #6b7280; font-size: 12px;">🔇 Voice disabled</span>
                    </div>
                    """,
                    gr.update(visible=False)  # Hide recovery button
                )

        def update_volume_display(volume_val):
            """Update volume display when slider changes"""
            volume_percent = int(volume_val * 100)
            return f"Volume: {volume_percent}%"

        # Wire up the interface
        submit_btn.click(
            fn=submit_question,
            inputs=[question_input, tts_enabled, volume_slider],
            outputs=[answer_output, sources_output, tts_status, audio_output, tts_recovery_btn],
        )

        question_input.submit(
            fn=submit_question,
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
