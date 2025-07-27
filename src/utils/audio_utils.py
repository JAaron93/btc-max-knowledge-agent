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
import tempfile
import os
import weakref
import atexit
import time
from typing import Iterator, Optional, Dict, Any, Union
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Audio processing constants
MAX_AUDIO_SIZE = 50 * 1024 * 1024  # 50MB maximum audio file size

# Optimized streaming buffer sizes for different scenarios
STREAMING_BUFFER_SIZES = {
    'default': 8192,      # 8KB - good balance for most cases
    'low_latency': 4096,  # 4KB - for real-time applications
    'high_throughput': 16384,  # 16KB - for large files
    'mobile': 2048,       # 2KB - for mobile/low bandwidth
    'desktop': 12288      # 12KB - for desktop applications
}

# Buffer size selection based on audio characteristics
def get_optimal_buffer_size(audio_size: int, is_cached: bool = False, connection_type: str = 'default') -> int:
    """
    Calculate optimal buffer size based on audio characteristics and connection type.
    
    Args:
        audio_size: Size of audio data in bytes
        is_cached: Whether audio is from cache (instant replay)
        connection_type: Type of connection ('default', 'low_latency', 'high_throughput', 'mobile', 'desktop')
    
    Returns:
        Optimal buffer size in bytes
    """
    base_size = STREAMING_BUFFER_SIZES.get(connection_type, STREAMING_BUFFER_SIZES['default'])
    
    # For cached audio, use smaller buffers for instant playback
    if is_cached:
        return min(base_size, 4096)
    
    # For very small audio files, use smaller buffers
    if audio_size < 32768:  # Less than 32KB
        return min(base_size, 2048)
    
    # For large audio files, use larger buffers for efficiency
    if audio_size > 1024 * 1024:  # Greater than 1MB
        return max(base_size, 16384)
    
    return base_size


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
            logger.warning("Content extraction attempted with invalid response text")
            raise ContentExtractionError("Invalid response text provided")
        
        logger.info(f"Starting content extraction from {len(response_text)} characters")
        
        try:
            # Start with the original text
            clean_text = response_text.strip()
            
            # Clean up markdown formatting first (before removing sources)
            clean_text = ResponseContentExtractor._clean_markdown(clean_text)
            logger.debug(f"After markdown cleaning: {len(clean_text)} characters")
            
            # Remove source sections and citations using pre-compiled patterns
            # Apply multiline patterns first (for sections that span multiple lines)
            for pattern in ResponseContentExtractor._MULTILINE_SOURCE_PATTERNS:
                clean_text = pattern.sub('', clean_text)

            # Apply single-line patterns (more efficient without DOTALL)
            for pattern in ResponseContentExtractor._SINGLE_LINE_SOURCE_PATTERNS:
                clean_text = pattern.sub('', clean_text)
            
            logger.debug(f"After source removal: {len(clean_text)} characters")

            # Remove metadata patterns using pre-compiled patterns
            for pattern in ResponseContentExtractor._METADATA_PATTERNS:
                clean_text = pattern.sub('', clean_text)
            
            logger.debug(f"After metadata removal: {len(clean_text)} characters")
            
            # Normalize whitespace
            clean_text = ResponseContentExtractor._normalize_whitespace(clean_text)
            
            # Validate result
            if not clean_text.strip():
                logger.warning("Content extraction resulted in empty text after processing")
                return "No content available for synthesis."
            
            logger.info(f"Content extraction successful: {len(clean_text)} characters extracted from {len(response_text)} original characters")
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
    def prepare_for_streaming(audio_bytes: bytes, chunk_size: Optional[int] = None, 
                            is_cached: bool = False, connection_type: str = 'default') -> Iterator[bytes]:
        """
        Prepare audio bytes for streaming to UI with optimized buffer sizes.
        
        Args:
            audio_bytes: Raw audio data
            chunk_size: Size of each chunk in bytes (auto-calculated if None)
            is_cached: Whether audio is from cache (affects buffer size)
            connection_type: Type of connection for buffer optimization
            
        Yields:
            Audio data chunks for streaming
            
        Raises:
            AudioProcessingError: If streaming preparation fails
        """
        if not audio_bytes:
            raise AudioProcessingError("No audio data provided for streaming")
        
        try:
            # Calculate optimal chunk size if not provided
            if chunk_size is None:
                chunk_size = get_optimal_buffer_size(len(audio_bytes), is_cached, connection_type)
            
            # Create a BytesIO object for streaming
            audio_stream = io.BytesIO(audio_bytes)
            
            # Yield chunks of the optimized size
            chunks_yielded = 0
            while True:
                chunk = audio_stream.read(chunk_size)
                if not chunk:
                    break
                yield chunk
                chunks_yielded += 1
            
            logger.debug(f"Prepared {len(audio_bytes)} bytes for streaming in {chunks_yielded} chunks of {chunk_size} bytes (cached: {is_cached})")
            
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


class TempFileWrapper:
    """Wrapper for temporary files with cleanup capability."""
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.created_at = time.time()
    
    def cleanup(self) -> bool:
        """Clean up the temporary file."""
        try:
            if os.path.exists(self.file_path):
                os.unlink(self.file_path)
                return True
            return False
        except Exception:
            return False
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Context manager exit - cleanup the temporary file.
        
        Args:
            exc_type: Exception type if an exception occurred, None otherwise
            exc_val: Exception value if an exception occurred, None otherwise
            exc_tb: Exception traceback if an exception occurred, None otherwise
            
        Returns:
            False: Exceptions are intentionally not suppressed. Any exceptions
                  that occurred within the context manager will be re-raised,
                  allowing proper error handling by the calling code.
        """
        self.cleanup()
        return False  # Don't suppress exceptions
    
    def __del__(self):
        """Cleanup on destruction."""
        try:
            self.cleanup()
        except Exception:
            pass


class TemporaryFileManager:
    """Manages temporary audio files with automatic cleanup."""
    
    def __init__(self):
        self._temp_files: weakref.WeakSet = weakref.WeakSet()
        self._lock = threading.Lock()
        
        # Register cleanup on exit
        atexit.register(self.cleanup_all)
    
    def create_temp_file(self, audio_data: bytes, suffix: str = '.mp3') -> str:
        """
        Create a temporary file for audio data.
        
        Args:
            audio_data: Audio data to write
            suffix: File suffix
            
        Returns:
            Path to temporary file
        """
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
                temp_file.write(audio_data)
                temp_path = temp_file.name
            
            # Register for cleanup
            with self._lock:
                self._temp_files.add(TempFileWrapper(temp_path))
            
            logger.debug(f"Created temporary audio file: {temp_path}")
            return temp_path
            
        except Exception as e:
            logger.error(f"Failed to create temporary file: {e}")
            raise AudioProcessingError(f"Temporary file creation failed: {e}")
    
    def cleanup_file(self, file_path: str) -> bool:
        """
        Clean up a specific temporary file.
        
        Args:
            file_path: Path to file to clean up
            
        Returns:
            True if cleaned up successfully
        """
        try:
            if os.path.exists(file_path):
                os.unlink(file_path)
                logger.debug(f"Cleaned up temporary file: {file_path}")
                return True
            return False
        except Exception as e:
            logger.warning(f"Failed to cleanup temporary file {file_path}: {e}")
            return False
    
    def cleanup_all(self) -> int:
        """
        Clean up all registered temporary files.
        
        Returns:
            Number of files cleaned up
        """
        cleaned_count = 0
        with self._lock:
            for temp_file in list(self._temp_files):
                try:
                    if hasattr(temp_file, 'cleanup') and callable(temp_file.cleanup):
                        if temp_file.cleanup():
                            cleaned_count += 1
                except Exception as e:
                    logger.debug(f"Error during temp file cleanup: {e}")
        
        if cleaned_count > 0:
            logger.info(f"Cleaned up {cleaned_count} temporary audio files")
        
        return cleaned_count
    
    def get_stats(self) -> Dict[str, Any]:
        """Get temporary file statistics."""
        with self._lock:
            active_files = len(self._temp_files)
            
        return {
            'active_temp_files': active_files,
            'temp_dir': tempfile.gettempdir()
        }


class AudioStreamingManager:
    """Manages audio streaming for real-time TTS playback with resource management."""
    
    def __init__(self):
        self._lock = threading.Lock()
        self.current_stream = None
        self.is_streaming = False
        self.stream_callbacks = []
        self.temp_file_manager = TemporaryFileManager()
        
        # Performance tracking
        self._stream_stats = {
            'streams_started': 0,
            'streams_completed': 0,
            'total_bytes_streamed': 0,
            'average_stream_duration': 0.0,
            'temp_files_cleaned': 0
        }
        self._stats_lock = threading.Lock()
    
    def prepare_streaming_audio(self, audio_bytes: bytes, is_cached: bool = False, 
                              connection_type: str = 'default') -> Dict[str, Any]:
        """
        Prepare audio for streaming playback with optimized buffer sizes.
        
        Args:
            audio_bytes: Raw audio data
            is_cached: Whether this audio is from cache (instant replay)
            connection_type: Connection type for buffer optimization
            
        Returns:
            Dictionary with streaming audio data and metadata
        """
        if not AudioStreamProcessor.validate_audio_data(audio_bytes):
            raise AudioProcessingError("Invalid audio data for streaming")
        
        try:
            # Estimate duration for UI feedback
            duration = AudioStreamProcessor.estimate_duration(audio_bytes)
            
            # Calculate optimal buffer size for this audio
            optimal_buffer_size = get_optimal_buffer_size(len(audio_bytes), is_cached, connection_type)
            
            # Create streaming data structure with optimization metadata
            streaming_data = {
                "audio_bytes": audio_bytes,
                "duration": duration,
                "is_cached": is_cached,
                "format": "mp3",  # ElevenLabs default
                "sample_rate": 44100,
                "size_bytes": len(audio_bytes),
                "streaming_ready": True,
                "optimal_buffer_size": optimal_buffer_size,
                "connection_type": connection_type,
                "estimated_chunks": len(audio_bytes) // optimal_buffer_size + (1 if len(audio_bytes) % optimal_buffer_size else 0)
            }
            
            # Convert to Gradio-compatible format
            gradio_audio = AudioFormatConverter.convert_to_gradio_format(audio_bytes)
            streaming_data["gradio_audio"] = gradio_audio
            
            # Create tuple for Gradio Audio component (sample_rate, audio_data)
            gradio_tuple = AudioFormatConverter.create_gradio_audio_component_data(audio_bytes)
            streaming_data["gradio_tuple"] = gradio_tuple
            
            logger.info(f"Prepared streaming audio: {len(audio_bytes)} bytes, duration: {duration:.1f}s, cached: {is_cached}, buffer: {optimal_buffer_size}")
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
    
    def get_streaming_chunks(self, audio_bytes: bytes, chunk_size: Optional[int] = None, 
                           is_cached: bool = False, connection_type: str = 'default') -> Iterator[bytes]:
        """
        Get audio chunks for streaming playback with optimized buffer sizes.
        
        Args:
            audio_bytes: Audio data to stream
            chunk_size: Size of each chunk (auto-calculated if None)
            is_cached: Whether audio is from cache
            connection_type: Connection type for optimization
            
        Yields:
            Audio chunks for streaming
        """
        return AudioFormatConverter.prepare_for_streaming(audio_bytes, chunk_size, is_cached, connection_type)
    
    def start_streaming(self, streaming_data: Dict[str, Any]) -> bool:
        """
        Start streaming audio playback with performance tracking.
        
        Args:
            streaming_data: Prepared streaming data
            
        Returns:
            True if streaming started successfully
        """
        try:
            with self._lock:
                self.current_stream = streaming_data
                self.is_streaming = True
                
                # Track performance
                with self._stats_lock:
                    self._stream_stats['streams_started'] += 1
                    self._stream_stats['total_bytes_streamed'] += streaming_data.get('size_bytes', 0)

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
        """Stop current audio streaming with cleanup."""
        with self._lock:
            if self.is_streaming:
                self.is_streaming = False
                
                # Track completion
                with self._stats_lock:
                    self._stream_stats['streams_completed'] += 1

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
    
    def cleanup_resources(self) -> Dict[str, int]:
        """Clean up all streaming resources."""
        cleanup_results = {
            'temp_files_cleaned': 0,
            'streams_stopped': 0
        }
        
        # Stop current streaming
        if self.is_streaming:
            self.stop_streaming()
            cleanup_results['streams_stopped'] = 1
        
        # Clean up temporary files
        cleanup_results['temp_files_cleaned'] = self.temp_file_manager.cleanup_all()
        
        # Reset performance stats
        with self._stats_lock:
            self._stream_stats = {
                'streams_started': 0,
                'streams_completed': 0,
                'total_bytes_streamed': 0,
                'average_stream_duration': 0.0,
                'temp_files_cleaned': cleanup_results['temp_files_cleaned']
            }
        
        logger.info(f"Streaming resources cleaned up: {cleanup_results}")
        return cleanup_results
    
    def optimize_streaming_performance(self, force_gc: bool = False) -> Dict[str, Any]:
        """
        Optimize streaming performance by cleaning up resources.
        
        Args:
            force_gc: Whether to force garbage collection. Defaults to False
                     to avoid performance impact in production. Set to True
                     only when memory cleanup is specifically needed.
        
        Returns:
            Dictionary with optimization results including cleanup stats
        """
        optimization_results = {
            'temp_files_cleaned': 0,
            'memory_freed': False,
            'gc_performed': False
        }
        
        # Clean up temporary files
        optimization_results['temp_files_cleaned'] = self.temp_file_manager.cleanup_all()
        
        # Conditionally perform garbage collection
        if force_gc:
            try:
                import gc
                collected = gc.collect()
                optimization_results['memory_freed'] = collected > 0
                optimization_results['objects_collected'] = collected
                optimization_results['gc_performed'] = True
            except ImportError:
                optimization_results['memory_freed'] = False
                optimization_results['gc_performed'] = False
        else:
            optimization_results['objects_collected'] = 0
        
        return optimization_results
    
    def get_stream_status(self) -> Dict[str, Any]:
        """Get current streaming status with performance metrics."""
        with self._lock:
            current_stream_info = None
            if self.current_stream:
                current_stream_info = {
                    "duration": self.current_stream.get("duration"),
                    "is_cached": self.current_stream.get("is_cached"),
                    "size_bytes": self.current_stream.get("size_bytes"),
                    "optimal_buffer_size": self.current_stream.get("optimal_buffer_size"),
                    "connection_type": self.current_stream.get("connection_type"),
                    "estimated_chunks": self.current_stream.get("estimated_chunks")
                }
            
            with self._stats_lock:
                performance_stats = self._stream_stats.copy()
            
            temp_file_stats = self.temp_file_manager.get_stats()
            
            return {
                "is_streaming": self.is_streaming,
                "has_current_stream": self.current_stream is not None,
                "current_stream_info": current_stream_info,
                "performance": performance_stats,
                "temp_files": temp_file_stats
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


def stream_audio_chunks(audio_bytes: bytes, chunk_size: Optional[int] = None, 
                       is_cached: bool = False, connection_type: str = 'default') -> Iterator[bytes]:
    """
    Convenience function to stream audio in chunks with optimized buffer sizes.
    
    Args:
        audio_bytes: Raw audio data
        chunk_size: Size of each chunk (auto-calculated if None)
        is_cached: Whether audio is from cache
        connection_type: Connection type for optimization
        
    Yields:
        Audio data chunks
    """
    return AudioFormatConverter.prepare_for_streaming(audio_bytes, chunk_size, is_cached, connection_type)


def prepare_audio_for_streaming(audio_bytes: bytes, is_cached: bool = False, 
                              connection_type: str = 'default') -> Dict[str, Any]:
    """
    Convenience function to prepare audio for streaming playback with optimized buffers.
    
    This function delegates to the AudioStreamingManager prepare_streaming_audio method
    to avoid confusion between the manager method and convenience wrapper.
    
    Args:
        audio_bytes: Raw audio data
        is_cached: Whether audio is from cache
        connection_type: Connection type for buffer optimization
        
    Returns:
        Streaming-ready audio data
    """
    manager = get_audio_streaming_manager()
    return manager.prepare_streaming_audio(audio_bytes, is_cached, connection_type)
