"""
Audio processing utilities for TTS integration.

This module provides utilities for processing audio data and extracting
clean content for text-to-speech synthesis.
"""

import re
import base64
import io
import logging
import threading
from typing import Iterator, Optional, Dict, Any, Union
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Audio processing constants
MAX_AUDIO_SIZE = 50 * 1024 * 1024  # 50MB maximum audio file size


class ContentExtractionError(Exception):
    """Exception raised when content extraction fails."""
    pass


class AudioProcessingError(Exception):
    """Exception raised when audio processing fails."""
    pass


class ResponseContentExtractor:
    """Extracts clean content from Pinecone Assistant responses for TTS."""

    # Pre-compiled optimized regex patterns for better performance
    # Patterns that need to match across lines (with DOTALL)
    _MULTILINE_SOURCE_PATTERNS = [
        re.compile(r'\*\*Sources?\*\*(?:[^\n]*\n)*?(?=\n\n|\Z)', re.DOTALL | re.IGNORECASE | re.MULTILINE),
        re.compile(r'## Sources?(?:[^\n]*\n)*?(?=\n\n|\Z)', re.DOTALL | re.IGNORECASE | re.MULTILINE),
        re.compile(r'Sources?\.(?:[^\n]*\n)*?(?=\n\n|\Z)', re.DOTALL | re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*Sources?\s*$(?:[^\n]*\n)*?(?=\n\n|\Z)', re.DOTALL | re.IGNORECASE | re.MULTILINE),
    ]

    # Single-line patterns (without DOTALL for better performance)
    _SINGLE_LINE_SOURCE_PATTERNS = [
        re.compile(r'\*Source:[^\n]*\*', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*Source:[^\n]*$', re.IGNORECASE | re.MULTILINE),
        re.compile(r'\[[^\]]*\]\([^)]*\)', re.IGNORECASE),  # Markdown links
        re.compile(r'https?://[^\s)]+', re.IGNORECASE),     # URLs - more specific end boundary
        re.compile(r'\*Published:[^\n]*\*', re.IGNORECASE | re.MULTILINE),
        re.compile(r'\*Relevance:[^\n]*\*', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*Relevance:[^\n]*$', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^-{3,}$', re.MULTILINE),               # Horizontal rules - anchored to line
        re.compile(r'^\s*## Result \d+\s*$', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^\s*Result \d+\.\s*$', re.IGNORECASE | re.MULTILINE),
    ]

    # Pre-compiled metadata patterns
    _METADATA_PATTERNS = [
        re.compile(r'\*\*Query:\*\*[^\n]*\n', re.IGNORECASE | re.MULTILINE),
        re.compile(r'Query:[^\n]*\n', re.IGNORECASE | re.MULTILINE),
        re.compile(r'Found \d+ relevant result[^.]*\.', re.IGNORECASE),
        re.compile(r'\d+ result[^.]*include[^.]*source[^.]*\.', re.IGNORECASE),
    ]

    # Pre-compiled markdown cleaning patterns
    _MARKDOWN_PATTERNS = [
        re.compile(r'\*\*([^*]+)\*\*'),                    # Bold - capture group for replacement
        re.compile(r'\*([^*]+)\*'),                        # Italic - capture group for replacement
        re.compile(r'_([^_]+)_'),                          # Italic underscore - capture group
        re.compile(r'^\s*#{1,6}\s*(.+)$', re.MULTILINE),   # Headers - capture group for replacement
        re.compile(r'```[^`]*```', re.DOTALL),             # Code blocks - optimized for non-greedy
        re.compile(r'`([^`]+)`'),                          # Inline code - capture group
        re.compile(r'^\s*>\s*[^\n]*$', re.MULTILINE),      # Blockquotes - more specific
        re.compile(r'^\s*[-*+]\s*', re.MULTILINE),         # List bullets
        re.compile(r'^\s*\d+\.\s*', re.MULTILINE),         # Numbered lists
    ]

    # Pre-compiled whitespace normalization patterns
    _WHITESPACE_PATTERNS = [
        re.compile(r'\n{3,}'),                             # Multiple newlines
        re.compile(r' {2,}'),                              # Multiple spaces
    ]
    
    @staticmethod
    def extract_main_content(response_text: str) -> str:
        """
        Extract main response content, filtering out sources and metadata.
        
        Args:
            response_text: Full response text from Pinecone Assistant
            
        Returns:
            Clean text suitable for TTS synthesis
            
        Raises:
            ContentExtractionError: If extraction fails
        """
        if not response_text or not isinstance(response_text, str):
            raise ContentExtractionError("Invalid response text provided")
        
        try:
            # Start with the original text
            clean_text = response_text.strip()
            
            # Clean up markdown formatting first (before removing sources)
            clean_text = ResponseContentExtractor._clean_markdown(clean_text)
            
            # Remove source sections and citations using pre-compiled patterns
            # Apply multiline patterns first (for sections that span multiple lines)
            for pattern in ResponseContentExtractor._MULTILINE_SOURCE_PATTERNS:
                clean_text = pattern.sub('', clean_text)

            # Apply single-line patterns (more efficient without DOTALL)
            for pattern in ResponseContentExtractor._SINGLE_LINE_SOURCE_PATTERNS:
                clean_text = pattern.sub('', clean_text)

            # Remove metadata patterns using pre-compiled patterns
            for pattern in ResponseContentExtractor._METADATA_PATTERNS:
                clean_text = pattern.sub('', clean_text)
            
            # Normalize whitespace
            clean_text = ResponseContentExtractor._normalize_whitespace(clean_text)
            
            # Validate result
            if not clean_text.strip():
                logger.warning("Content extraction resulted in empty text")
                return "No content available for synthesis."
            
            logger.debug(f"Extracted {len(clean_text)} characters from {len(response_text)} original characters")
            return clean_text.strip()
            
        except Exception as e:
            logger.error(f"Content extraction failed: {e}")
            raise ContentExtractionError(f"Failed to extract content: {e}")
    
    @staticmethod
    def _clean_markdown(text: str) -> str:
        """Remove or convert markdown formatting for better TTS readability."""
        # Use pre-compiled patterns for better performance
        patterns = ResponseContentExtractor._MARKDOWN_PATTERNS

        # Remove bold/italic markers but keep the text (with capture groups)
        text = patterns[0].sub(r'\1', text)  # Bold
        text = patterns[1].sub(r'\1', text)  # Italic
        text = patterns[2].sub(r'\1', text)  # Italic underscore

        # Convert headers to plain text with pauses
        text = patterns[3].sub(r'\1.', text)

        # Remove code blocks and inline code
        text = patterns[4].sub('', text)     # Code blocks
        text = patterns[5].sub(r'\1', text)  # Inline code

        # Remove blockquotes
        text = patterns[6].sub('', text)

        # Convert lists to readable format
        text = patterns[7].sub('', text)     # List bullets
        text = patterns[8].sub('', text)     # Numbered lists

        return text
    
    @staticmethod
    def _normalize_whitespace(text: str) -> str:
        """Normalize whitespace for better TTS flow."""
        # Use pre-compiled patterns for better performance
        patterns = ResponseContentExtractor._WHITESPACE_PATTERNS

        # Replace multiple newlines with double newlines (paragraph breaks)
        text = patterns[0].sub('\n\n', text)

        # Replace multiple spaces with single spaces
        text = patterns[1].sub(' ', text)

        # Remove leading/trailing whitespace from lines
        lines = [line.strip() for line in text.split('\n')]
        text = '\n'.join(lines)

        # Remove empty lines but preserve paragraph breaks
        lines = text.split('\n')
        cleaned_lines = []
        for line in lines:
            if line.strip() or (cleaned_lines and cleaned_lines[-1]):
                cleaned_lines.append(line)

        # Join and remove excessive empty lines
        text = '\n'.join(cleaned_lines)
        text = patterns[0].sub('\n\n', text)  # Use pre-compiled pattern again

        # Remove empty lines at start and end
        text = text.strip()

        return text
    
    @staticmethod
    def extract_from_structured_response(response_data: Dict[str, Any]) -> str:
        """
        Extract content from structured response format.
        
        Args:
            response_data: Structured response dictionary
            
        Returns:
            Clean text for TTS synthesis
        """
        if not isinstance(response_data, dict):
            raise ContentExtractionError("Response data must be a dictionary")
        
        # Try to get the main answer/content
        content = None
        
        # Check common response formats
        if 'answer' in response_data:
            content = response_data['answer']
        elif 'content' in response_data:
            if isinstance(response_data['content'], list):
                # Handle MCP-style content format
                text_parts = []
                for item in response_data['content']:
                    if isinstance(item, dict) and item.get('type') == 'text':
                        text_parts.append(item.get('text', ''))
                content = '\n'.join(text_parts)
            else:
                content = response_data['content']
        elif 'formatted_response' in response_data:
            content = response_data['formatted_response']
        elif 'text' in response_data:
            content = response_data['text']
        
        if not content:
            raise ContentExtractionError("No extractable content found in response data")
        
        return ResponseContentExtractor.extract_main_content(str(content))


class AudioFormatConverter:
    """Handles audio format conversion for Gradio compatibility."""
    
    @staticmethod
    def convert_to_gradio_format(audio_bytes: bytes, format_type: str = "mp3") -> str:
        """
        Convert audio bytes to Gradio-compatible format.

        Args:
            audio_bytes: Raw audio data
            format_type: Audio format (mp3, wav, etc.)

        Returns:
            Base64-encoded data URI for Gradio

        Raises:
            AudioProcessingError: If conversion fails or audio size exceeds limit
        """
        if not audio_bytes:
            raise AudioProcessingError("No audio data provided")

        # Check audio size to prevent excessive memory usage
        audio_size = len(audio_bytes)
        if audio_size > MAX_AUDIO_SIZE:
            raise AudioProcessingError(
                f"Audio data too large: {audio_size:,} bytes exceeds maximum limit of {MAX_AUDIO_SIZE:,} bytes ({MAX_AUDIO_SIZE // (1024 * 1024)}MB)"
            )

        try:
            # Encode audio data as base64
            encoded_audio = base64.b64encode(audio_bytes).decode('utf-8')
            
            # Create data URI based on format
            mime_types = {
                'mp3': 'audio/mpeg',
                'wav': 'audio/wav',
                'ogg': 'audio/ogg',
                'flac': 'audio/flac'
            }
            
            mime_type = mime_types.get(format_type.lower(), 'audio/mpeg')
            data_uri = f"data:{mime_type};base64,{encoded_audio}"
            
            logger.debug(f"Converted {len(audio_bytes)} bytes to Gradio format ({format_type})")
            return data_uri
            
        except Exception as e:
            logger.error(f"Audio format conversion failed: {e}")
            raise AudioProcessingError(f"Failed to convert audio format: {e}")
    
    @staticmethod
    def prepare_for_streaming(audio_bytes: bytes, chunk_size: int = 8192) -> Iterator[bytes]:
        """
        Prepare audio bytes for streaming to UI.
        
        Args:
            audio_bytes: Raw audio data
            chunk_size: Size of each chunk in bytes
            
        Yields:
            Audio data chunks for streaming
            
        Raises:
            AudioProcessingError: If streaming preparation fails
        """
        if not audio_bytes:
            raise AudioProcessingError("No audio data provided for streaming")
        
        try:
            # Create a BytesIO object for streaming
            audio_stream = io.BytesIO(audio_bytes)
            
            # Yield chunks of the specified size
            while True:
                chunk = audio_stream.read(chunk_size)
                if not chunk:
                    break
                yield chunk
            
            logger.debug(f"Prepared {len(audio_bytes)} bytes for streaming in {chunk_size}-byte chunks")
            
        except Exception as e:
            logger.error(f"Audio streaming preparation failed: {e}")
            raise AudioProcessingError(f"Failed to prepare audio for streaming: {e}")
    
    @staticmethod
    def create_gradio_audio_component_data(audio_bytes: bytes, sample_rate: int = 44100) -> tuple:
        """
        Create data tuple for Gradio Audio component.
        
        Args:
            audio_bytes: Raw audio data
            sample_rate: Audio sample rate
            
        Returns:
            Tuple of (sample_rate, audio_data) for Gradio Audio component
            
        Raises:
            AudioProcessingError: If component data creation fails
        """
        if not audio_bytes:
            raise AudioProcessingError("No audio data provided")
        
        try:
            # For Gradio Audio component, we need to return the raw bytes
            # The component will handle the proper formatting
            logger.debug(f"Created Gradio audio component data: {len(audio_bytes)} bytes at {sample_rate}Hz")
            return (sample_rate, audio_bytes)
            
        except Exception as e:
            logger.error(f"Gradio audio component data creation failed: {e}")
            raise AudioProcessingError(f"Failed to create Gradio audio data: {e}")


class AudioStreamProcessor:
    """Processes audio streams for real-time playback."""
    
    @staticmethod
    def validate_audio_data(audio_bytes: bytes) -> bool:
        """
        Validate audio data integrity.
        
        Args:
            audio_bytes: Audio data to validate
            
        Returns:
            True if valid, False otherwise
        # If we can't identify the format, assume it's valid
        # (ElevenLabs API should return valid audio)
        logger.warning(f"Could not identify audio format, assuming valid. First 16 bytes: {audio_bytes[:16].hex()}")
        return True
        return True
    
    @staticmethod
    def estimate_duration(audio_bytes: bytes, format_type: str = "mp3") -> Optional[float]:
        """
        Estimate audio duration in seconds.
        
        Args:
            audio_bytes: Audio data
            format_type: Audio format
            
        Returns:
            Estimated duration in seconds, or None if cannot estimate
        """
        if not audio_bytes:
            return None
        
        try:
            # Rough estimation based on file size and format
            # These are approximations for common bitrates
            if format_type.lower() == "mp3":
                # Assume 128 kbps MP3
                bitrate = 128 * 1000 / 8  # bytes per second
                duration = len(audio_bytes) / bitrate
            elif format_type.lower() == "wav":
                # Assume 44.1kHz 16-bit stereo WAV
                bitrate = 44100 * 2 * 2  # bytes per second
                duration = len(audio_bytes) / bitrate
            else:
                # Generic estimation
                duration = len(audio_bytes) / 16000  # Very rough estimate
            
            return max(0.1, duration)  # Minimum 0.1 seconds
            
        except Exception:
            return None


class AudioStreamingManager:
    """Manages audio streaming for real-time TTS playback."""
    
    def __init__(self):
        self._lock = threading.Lock()
        self.current_stream = None
        self.is_streaming = False
        self.stream_callbacks = []
    
    def prepare_streaming_audio(self, audio_bytes: bytes, is_cached: bool = False) -> Dict[str, Any]:
        """
        Prepare audio for streaming playback.
        
        Args:
            audio_bytes: Raw audio data
            is_cached: Whether this audio is from cache (instant replay)
            
        Returns:
            Dictionary with streaming audio data and metadata
        """
        if not AudioStreamProcessor.validate_audio_data(audio_bytes):
            raise AudioProcessingError("Invalid audio data for streaming")
        
        try:
            # Estimate duration for UI feedback
            duration = AudioStreamProcessor.estimate_duration(audio_bytes)
            
            # Create streaming data structure
            streaming_data = {
                "audio_bytes": audio_bytes,
                "duration": duration,
                "is_cached": is_cached,
                "format": "mp3",  # ElevenLabs default
                "sample_rate": 44100,
                "size_bytes": len(audio_bytes),
                "streaming_ready": True
            }
            
            # Convert to Gradio-compatible format
            gradio_audio = AudioFormatConverter.convert_to_gradio_format(audio_bytes)
            streaming_data["gradio_audio"] = gradio_audio
            
            # Create tuple for Gradio Audio component (sample_rate, audio_data)
            gradio_tuple = AudioFormatConverter.create_gradio_audio_component_data(audio_bytes)
            streaming_data["gradio_tuple"] = gradio_tuple
            
            logger.info(f"Prepared streaming audio: {len(audio_bytes)} bytes, duration: {duration:.1f}s, cached: {is_cached}")
            return streaming_data
            
        except Exception as e:
            logger.error(f"Failed to prepare streaming audio: {e}")
            raise AudioProcessingError(f"Streaming preparation failed: {e}")
    
    def create_instant_replay_data(self, cached_audio_bytes: bytes) -> Dict[str, Any]:
        """
        Create streaming data for instant replay of cached audio.
        
        Args:
            cached_audio_bytes: Cached audio data
            
        Returns:
            Streaming data optimized for instant playback
        """
        streaming_data = self.prepare_streaming_audio(cached_audio_bytes, is_cached=True)
        
        # Mark as instant replay for UI handling
        streaming_data["instant_replay"] = True
        streaming_data["synthesis_time"] = 0.0  # No synthesis needed
        
        logger.debug("Created instant replay data for cached audio")
        return streaming_data
    
    def create_synthesized_audio_data(self, audio_bytes: bytes, synthesis_time: float = None) -> Dict[str, Any]:
        """
        Create streaming data for newly synthesized audio.
        
        Args:
            audio_bytes: Newly synthesized audio data
            synthesis_time: Time taken for synthesis (optional)
            
        Returns:
            Streaming data for new synthesis
        """
        streaming_data = self.prepare_streaming_audio(audio_bytes, is_cached=False)
        
        # Add synthesis metadata
        streaming_data["instant_replay"] = False
        streaming_data["synthesis_time"] = synthesis_time or 0.0
        
        logger.debug(f"Created synthesized audio data (synthesis time: {synthesis_time:.2f}s)")
        return streaming_data
    
    def get_streaming_chunks(self, audio_bytes: bytes, chunk_size: int = 8192) -> Iterator[bytes]:
        """
        Get audio chunks for streaming playback.
        
        Args:
            audio_bytes: Audio data to stream
            chunk_size: Size of each chunk
            
        Yields:
            Audio chunks for streaming
        """
        return AudioFormatConverter.prepare_for_streaming(audio_bytes, chunk_size)
    
    def start_streaming(self, streaming_data: Dict[str, Any]) -> bool:
        """
        Start streaming audio playback.
        
        Args:
            streaming_data: Prepared streaming data
            
        Returns:
            True if streaming started successfully
        """
        try:
            with self._lock:
                self.current_stream = streaming_data
                self.is_streaming = True

                # Notify callbacks
                for callback in self.stream_callbacks:
                    try:
                        callback("stream_started", streaming_data)
                    except Exception as e:
                        logger.warning(f"Stream callback failed: {e}")

            logger.info("Audio streaming started")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start streaming: {e}")
            return False
    
    def stop_streaming(self):
        """Stop current audio streaming."""
        with self._lock:
            if self.is_streaming:
                self.is_streaming = False

                # Notify callbacks
                for callback in self.stream_callbacks:
                    try:
                        callback("stream_stopped", self.current_stream)
                    except Exception as e:
                        logger.warning(f"Stream callback failed: {e}")

                self.current_stream = None
                logger.info("Audio streaming stopped")
    
    def add_stream_callback(self, callback):
        """Add callback for stream events."""
        with self._lock:
            self.stream_callbacks.append(callback)

    def remove_stream_callback(self, callback):
        """Remove stream callback."""
        with self._lock:
            if callback in self.stream_callbacks:
                self.stream_callbacks.remove(callback)
    
    def get_stream_status(self) -> Dict[str, Any]:
        """Get current streaming status."""
        with self._lock:
            return {
                "is_streaming": self.is_streaming,
                "has_current_stream": self.current_stream is not None,
                "current_stream_info": {
                    "duration": self.current_stream.get("duration") if self.current_stream else None,
                    "is_cached": self.current_stream.get("is_cached") if self.current_stream else None,
                    "size_bytes": self.current_stream.get("size_bytes") if self.current_stream else None
                } if self.current_stream else None
            }


# Global streaming manager instance
_streaming_manager: Optional[AudioStreamingManager] = None


def get_audio_streaming_manager() -> AudioStreamingManager:
    """Get global audio streaming manager instance."""
    global _streaming_manager
    if _streaming_manager is None:
        _streaming_manager = AudioStreamingManager()
    return _streaming_manager


# Convenience functions for common operations
def extract_tts_content(response_text: str) -> str:
    """
    Convenience function to extract TTS-ready content from response text.
    
    Args:
        response_text: Full response text
        
    Returns:
        Clean text for TTS synthesis
    """
    return ResponseContentExtractor.extract_main_content(response_text)


def prepare_audio_for_gradio(audio_bytes: bytes, format_type: str = "mp3") -> str:
    """
    Convenience function to prepare audio for Gradio display.
    
    Args:
        audio_bytes: Raw audio data
        format_type: Audio format
        
    Returns:
        Gradio-compatible data URI
    """
    return AudioFormatConverter.convert_to_gradio_format(audio_bytes, format_type)


def stream_audio_chunks(audio_bytes: bytes, chunk_size: int = 8192) -> Iterator[bytes]:
    """
    Convenience function to stream audio in chunks.
    
    Args:
        audio_bytes: Raw audio data
        chunk_size: Size of each chunk
        
    Yields:
        Audio data chunks
    """
    return AudioFormatConverter.prepare_for_streaming(audio_bytes, chunk_size)


def prepare_audio_for_streaming(audio_bytes: bytes, is_cached: bool = False) -> Dict[str, Any]:
    """
    Convenience function to prepare audio for streaming playback.
    
    This function delegates to the AudioStreamingManager prepare_streaming_audio method
    to avoid confusion between the manager method and convenience wrapper.
    
    Args:
        audio_bytes: Raw audio data
        is_cached: Whether audio is from cache
        
    Returns:
        Streaming-ready audio data
    """
    manager = get_audio_streaming_manager()
    return manager.prepare_streaming_audio(audio_bytes, is_cached)


def create_gradio_streaming_audio(audio_bytes: bytes, is_cached: bool = False) -> tuple:
    """
    Convenience function to create Gradio Audio component data for streaming.
    
    Args:
        audio_bytes: Raw audio data
        is_cached: Whether audio is from cache
        
    Returns:
        Tuple for Gradio Audio component (sample_rate, audio_data)
        
    Raises:
        AudioProcessingError: If streaming preparation fails
    """
    try:
        streaming_data = prepare_audio_for_streaming(audio_bytes, is_cached)
        return streaming_data["gradio_tuple"]
    except (KeyError, AudioProcessingError) as e:
        raise AudioProcessingError(f"Failed to create Gradio streaming audio: {e}")