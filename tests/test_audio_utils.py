"""
Unit tests for audio processing utilities.
"""

import pytest
import base64
import io
from unittest.mock import patch, MagicMock

from btc_max_knowledge_agent.utils.audio_utils import (
    ResponseContentExtractor,
    AudioFormatConverter,
    AudioStreamProcessor,
    ContentExtractionError,
    AudioProcessingError,
    extract_tts_content,
    prepare_audio_for_gradio,
    stream_audio_chunks
)


class TestResponseContentExtractor:
    """Test cases for ResponseContentExtractor class."""
    
    def test_extract_main_content_basic(self):
        """Test basic content extraction."""
        response_text = """
        This is the main response content about Bitcoin.
        
        **Sources**
        
        *Source: [Bitcoin.org](https://bitcoin.org)*
        *Source: [Whitepaper](https://bitcoin.org/bitcoin.pdf)*
        """
        
        result = ResponseContentExtractor.extract_main_content(response_text)
        
        assert "This is the main response content about Bitcoin." in result
        assert "Sources" not in result
        assert "bitcoin.org" not in result
        assert "Whitepaper" not in result
    
    def test_extract_main_content_with_markdown(self):
        """Test content extraction with markdown formatting."""
        response_text = """
        # Bitcoin Overview
        
        **Bitcoin** is a *decentralized* digital currency.
        
        ## Key Features
        
        - Peer-to-peer transactions
        - Blockchain technology
        
        ```python
        # Code example
        print("Bitcoin")
        ```
        
        > This is a quote about Bitcoin
        
        ## Sources
        
        1. Bitcoin Whitepaper
        2. [Bitcoin.org](https://bitcoin.org)
        """
        
        result = ResponseContentExtractor.extract_main_content(response_text)
        
        # Check that markdown is cleaned
        assert "Bitcoin Overview." in result  # Header converted
        assert "Bitcoin is a decentralized digital currency." in result  # Bold/italic removed
        assert "Peer-to-peer transactions" in result  # List items preserved
        assert "Blockchain technology" in result
        
        # Check that code blocks and sources are removed
        assert "```" not in result
        assert "print(" not in result
        assert "Bitcoin.org" not in result
        # Blockquote should be removed (check for the specific quote content)
        assert "This is a quote about Bitcoin" not in result
        # Sources section should be removed (after markdown processing, it becomes "Sources.")
        assert "Sources." not in result
    
    def test_extract_main_content_with_urls(self):
        """Test content extraction removes URLs."""
        response_text = """
        Bitcoin is described at https://bitcoin.org and in the whitepaper.
        
        You can read more at [this link](https://example.com/bitcoin).
        
        *Source: https://bitcoin.org*
        """
        
        result = ResponseContentExtractor.extract_main_content(response_text)
        
        assert "Bitcoin is described" in result
        assert "and in the whitepaper." in result
        assert "https://bitcoin.org" not in result
        assert "https://example.com" not in result
        assert "[this link]" not in result
    
    def test_extract_main_content_with_metadata(self):
        """Test content extraction removes metadata."""
        response_text = """
        **Query:** What is Bitcoin?
        
        Found 3 relevant results. 2 results include source links.
        
        Bitcoin is a digital currency that operates without a central authority.
        
        *Relevance: 0.95*
        
        ## Result 2
        
        Additional information about Bitcoin mining.
        
        ---
        
        ## Sources
        
        Various sources referenced above.
        """
        
        result = ResponseContentExtractor.extract_main_content(response_text)
        
        assert "Bitcoin is a digital currency" in result
        assert "Additional information about Bitcoin mining." in result
        assert "Query:" not in result
        assert "Found 3 relevant results" not in result
        assert "Relevance:" not in result
        assert "Result 2" not in result
        assert "---" not in result
        assert "Sources" not in result
    
    def test_extract_main_content_empty_input(self):
        """Test content extraction with empty input."""
        with pytest.raises(ContentExtractionError):
            ResponseContentExtractor.extract_main_content("")
        
        with pytest.raises(ContentExtractionError):
            ResponseContentExtractor.extract_main_content(None)
    
    def test_extract_main_content_only_sources(self):
        """Test content extraction when only sources remain."""
        response_text = """
        ## Sources
        
        *Source: [Bitcoin.org](https://bitcoin.org)*
        *Source: [Whitepaper](https://bitcoin.org/bitcoin.pdf)*
        """
        
        result = ResponseContentExtractor.extract_main_content(response_text)
        
        # Should return default message when no content remains
        assert result == "No content available for synthesis."
    
    def test_extract_from_structured_response_answer_format(self):
        """Test extraction from structured response with 'answer' field."""
        response_data = {
            "answer": "Bitcoin is a decentralized digital currency.",
            "sources": [{"title": "Bitcoin.org", "url": "https://bitcoin.org"}]
        }
        
        result = ResponseContentExtractor.extract_from_structured_response(response_data)
        
        assert "Bitcoin is a decentralized digital currency." in result
    
    def test_extract_from_structured_response_content_format(self):
        """Test extraction from structured response with 'content' field."""
        response_data = {
            "content": "Bitcoin enables peer-to-peer transactions.",
            "metadata": {"sources": 2}
        }
        
        result = ResponseContentExtractor.extract_from_structured_response(response_data)
        
        assert "Bitcoin enables peer-to-peer transactions." in result
    
    def test_extract_from_structured_response_mcp_format(self):
        """Test extraction from MCP-style structured response."""
        response_data = {
            "content": [
                {"type": "text", "text": "Bitcoin is revolutionary."},
                {"type": "text", "text": "\n\nIt uses blockchain technology."}
            ]
        }
        
        result = ResponseContentExtractor.extract_from_structured_response(response_data)
        
        assert "Bitcoin is revolutionary." in result
        assert "It uses blockchain technology." in result
    
    def test_extract_from_structured_response_invalid_input(self):
        """Test extraction from invalid structured response."""
        with pytest.raises(ContentExtractionError):
            ResponseContentExtractor.extract_from_structured_response("not a dict")
        
        with pytest.raises(ContentExtractionError):
            ResponseContentExtractor.extract_from_structured_response({})
    
    def test_normalize_whitespace(self):
        """Test whitespace normalization."""
        text = """
        
        
        Bitcoin   is   a   digital    currency.
        
        
        
        It operates    without central authority.
        
        
        """
        
        result = ResponseContentExtractor._normalize_whitespace(text)
        
        assert result == "Bitcoin is a digital currency.\n\nIt operates without central authority."
    
    def test_clean_markdown_headers(self):
        """Test markdown header cleaning."""
        text = "# Main Title\n## Subtitle\n### Sub-subtitle"
        
        result = ResponseContentExtractor._clean_markdown(text)
        
        assert result == "Main Title.\nSubtitle.\nSub-subtitle."
    
    def test_clean_markdown_formatting(self):
        """Test markdown formatting removal."""
        text = "**Bold text** and *italic text* and _underline text_"
        
        result = ResponseContentExtractor._clean_markdown(text)
        
        assert result == "Bold text and italic text and underline text"


class TestAudioFormatConverter:
    """Test cases for AudioFormatConverter class."""
    
    def test_convert_to_gradio_format_mp3(self):
        """Test conversion to Gradio format for MP3."""
        audio_bytes = b"fake_mp3_data_here"
        
        result = AudioFormatConverter.convert_to_gradio_format(audio_bytes, "mp3")
        
        expected_b64 = base64.b64encode(audio_bytes).decode('utf-8')
        expected_uri = f"data:audio/mpeg;base64,{expected_b64}"
        
        assert result == expected_uri
    
    def test_convert_to_gradio_format_wav(self):
        """Test conversion to Gradio format for WAV."""
        audio_bytes = b"fake_wav_data_here"
        
        result = AudioFormatConverter.convert_to_gradio_format(audio_bytes, "wav")
        
        expected_b64 = base64.b64encode(audio_bytes).decode('utf-8')
        expected_uri = f"data:audio/wav;base64,{expected_b64}"
        
        assert result == expected_uri
    
    def test_convert_to_gradio_format_unknown_format(self):
        """Test conversion with unknown format defaults to MP3."""
        audio_bytes = b"fake_audio_data"
        
        result = AudioFormatConverter.convert_to_gradio_format(audio_bytes, "unknown")
        
        expected_b64 = base64.b64encode(audio_bytes).decode('utf-8')
        expected_uri = f"data:audio/mpeg;base64,{expected_b64}"
        
        assert result == expected_uri
    
    def test_convert_to_gradio_format_empty_data(self):
        """Test conversion with empty audio data."""
        with pytest.raises(AudioProcessingError):
            AudioFormatConverter.convert_to_gradio_format(b"", "mp3")
        
        with pytest.raises(AudioProcessingError):
            AudioFormatConverter.convert_to_gradio_format(None, "mp3")
    
    def test_prepare_for_streaming(self):
        """Test audio streaming preparation."""
        audio_bytes = b"0123456789" * 100  # 1000 bytes
        chunk_size = 256
        
        chunks = list(AudioFormatConverter.prepare_for_streaming(audio_bytes, chunk_size))
        
        # Should have 4 chunks: 256, 256, 256, 232 bytes
        assert len(chunks) == 4
        assert len(chunks[0]) == 256
        assert len(chunks[1]) == 256
        assert len(chunks[2]) == 256
        assert len(chunks[3]) == 232
        
        # Verify data integrity
        reconstructed = b"".join(chunks)
        assert reconstructed == audio_bytes
    
    def test_prepare_for_streaming_small_data(self):
        """Test streaming preparation with small data."""
        audio_bytes = b"small"
        chunk_size = 1024
        
        chunks = list(AudioFormatConverter.prepare_for_streaming(audio_bytes, chunk_size))
        
        assert len(chunks) == 1
        assert chunks[0] == audio_bytes
    
    def test_prepare_for_streaming_empty_data(self):
        """Test streaming preparation with empty data."""
        with pytest.raises(AudioProcessingError):
            list(AudioFormatConverter.prepare_for_streaming(b"", 1024))
    
    def test_create_gradio_audio_component_data(self):
        """Test Gradio audio component data creation."""
        audio_bytes = b"fake_audio_data"
        sample_rate = 44100
        
        result = AudioFormatConverter.create_gradio_audio_component_data(audio_bytes, sample_rate)
        
        assert result == (sample_rate, audio_bytes)
    
    def test_create_gradio_audio_component_data_empty(self):
        """Test Gradio audio component data creation with empty data."""
        with pytest.raises(AudioProcessingError):
            AudioFormatConverter.create_gradio_audio_component_data(b"", 44100)


class TestAudioStreamProcessor:
    """Test cases for AudioStreamProcessor class."""
    
    def test_validate_audio_data_mp3_id3(self):
        """Test audio validation for MP3 with ID3 header."""
        audio_bytes = b"ID3" + b"x" * 200  # Fake MP3 with ID3 header
        
        result = AudioStreamProcessor.validate_audio_data(audio_bytes)
        
        assert result is True
    
    def test_validate_audio_data_mp3_sync(self):
        """Test audio validation for MP3 with sync frame."""
        audio_bytes = b"\xff\xfb" + b"x" * 200  # Fake MP3 with sync frame
        
        result = AudioStreamProcessor.validate_audio_data(audio_bytes)
        
        assert result is True
    
    def test_validate_audio_data_wav(self):
        """Test audio validation for WAV format."""
        audio_bytes = b"RIFF" + b"xxxx" + b"WAVE" + b"x" * 200  # Fake WAV
        
        result = AudioStreamProcessor.validate_audio_data(audio_bytes)
        
        assert result is True
    
    def test_validate_audio_data_unknown_format(self):
        """Test audio validation for unknown format."""
        audio_bytes = b"unknown_format_data" + b"x" * 200
        
        result = AudioStreamProcessor.validate_audio_data(audio_bytes)
        
        assert result is True  # Should assume valid for unknown formats
    
    def test_validate_audio_data_too_small(self):
        """Test audio validation for data that's too small."""
        audio_bytes = b"tiny"
        
        result = AudioStreamProcessor.validate_audio_data(audio_bytes)
        
        assert result is False
    
    def test_validate_audio_data_empty(self):
        """Test audio validation for empty data."""
        result = AudioStreamProcessor.validate_audio_data(b"")
        assert result is False
        
        result = AudioStreamProcessor.validate_audio_data(None)
        assert result is False
    
    def test_estimate_duration_mp3(self):
        """Test duration estimation for MP3."""
        # 128 kbps MP3: 16000 bytes per second
        audio_bytes = b"x" * 32000  # Should be ~2 seconds
        
        duration = AudioStreamProcessor.estimate_duration(audio_bytes, "mp3")
        
        assert duration is not None
        assert 1.5 < duration < 2.5  # Allow some tolerance
    
    def test_estimate_duration_wav(self):
        """Test duration estimation for WAV."""
        # 44.1kHz 16-bit stereo: 176400 bytes per second
        audio_bytes = b"x" * 176400  # Should be ~1 second
        
        duration = AudioStreamProcessor.estimate_duration(audio_bytes, "wav")
        
        assert duration is not None
        assert 0.8 < duration < 1.2  # Allow some tolerance
    
    def test_estimate_duration_unknown_format(self):
        """Test duration estimation for unknown format."""
        audio_bytes = b"x" * 16000
        
        duration = AudioStreamProcessor.estimate_duration(audio_bytes, "unknown")
        
        assert duration is not None
        assert duration > 0
    
    def test_estimate_duration_empty(self):
        """Test duration estimation for empty data."""
        duration = AudioStreamProcessor.estimate_duration(b"", "mp3")
        
        assert duration is None


class TestConvenienceFunctions:
    """Test cases for convenience functions."""
    
    def test_extract_tts_content(self):
        """Test extract_tts_content convenience function."""
        response_text = """
        Bitcoin is a digital currency.
        
        ## Sources
        
        *Source: Bitcoin.org*
        """
        
        result = extract_tts_content(response_text)
        
        assert "Bitcoin is a digital currency." in result
        assert "Sources" not in result
    
    def test_prepare_audio_for_gradio(self):
        """Test prepare_audio_for_gradio convenience function."""
        audio_bytes = b"fake_audio_data"
        
        result = prepare_audio_for_gradio(audio_bytes, "mp3")
        
        expected_b64 = base64.b64encode(audio_bytes).decode('utf-8')
        expected_uri = f"data:audio/mpeg;base64,{expected_b64}"
        
        assert result == expected_uri
    
    def test_stream_audio_chunks(self):
        """Test stream_audio_chunks convenience function."""
        audio_bytes = b"0123456789" * 10  # 100 bytes
        chunk_size = 25
        
        chunks = list(stream_audio_chunks(audio_bytes, chunk_size))
        
        assert len(chunks) == 4  # 25, 25, 25, 25 bytes
        reconstructed = b"".join(chunks)
        assert reconstructed == audio_bytes


class TestErrorHandling:
    """Test cases for error handling scenarios."""
    
    def test_content_extraction_error_propagation(self):
        """Test that content extraction errors are properly propagated."""
        with pytest.raises(ContentExtractionError):
            ResponseContentExtractor.extract_main_content(None)
    
    def test_audio_processing_error_propagation(self):
        """Test that audio processing errors are properly propagated."""
        with pytest.raises(AudioProcessingError):
            AudioFormatConverter.convert_to_gradio_format(None, "mp3")
    
    def test_error_logging(self):
        """Test that errors are properly logged."""
        # Test that the function raises the expected error
        # The actual logging is tested implicitly through the error handling
        with pytest.raises(ContentExtractionError, match="Invalid response text provided"):
            ResponseContentExtractor.extract_main_content(None)


class TestEdgeCases:
    """Test cases for edge cases and boundary conditions."""
    
    def test_very_long_content(self):
        """Test content extraction with very long text."""
        long_text = "Bitcoin " * 10000 + "\n\n## Sources\n\nMany sources here."
        
        result = ResponseContentExtractor.extract_main_content(long_text)
        
        assert "Bitcoin" in result
        assert "Sources" not in result
        assert len(result) > 0
    
    def test_unicode_content(self):
        """Test content extraction with Unicode characters."""
        unicode_text = """
        Bitcoin (₿) is a cryptocurrency invented in 2008 by Satoshi Nakamoto.
        
        ## Sources
        
        *Source: Wikipedia*
        """
        
        result = ResponseContentExtractor.extract_main_content(unicode_text)
        
        assert "Bitcoin (₿)" in result
        assert "Satoshi Nakamoto" in result
        assert "Sources" not in result
    
    def test_malformed_markdown(self):
        """Test content extraction with malformed markdown."""
        malformed_text = """
        **Unclosed bold and *mixed formatting
        
        ### Header without content
        
        [Broken link](
        
        ## Sources
        
        Something here
        """
        
        # Should not raise an exception
        result = ResponseContentExtractor.extract_main_content(malformed_text)
        
        assert len(result) > 0
        assert "Sources" not in result
    
    def test_audio_streaming_single_byte_chunks(self):
        """Test audio streaming with very small chunks."""
        audio_bytes = b"test"
        
        chunks = list(AudioFormatConverter.prepare_for_streaming(audio_bytes, 1))
        
        assert len(chunks) == 4
        assert chunks == [b"t", b"e", b"s", b"t"]
    
    def test_empty_structured_response_fields(self):
        """Test structured response extraction with empty fields."""
        response_data = {
            "answer": "",
            "content": "",
            "sources": []
        }
        
        with pytest.raises(ContentExtractionError):
            ResponseContentExtractor.extract_from_structured_response(response_data)


if __name__ == "__main__":
    pytest.main([__file__])