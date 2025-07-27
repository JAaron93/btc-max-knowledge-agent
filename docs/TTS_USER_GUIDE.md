# Text-to-Speech (TTS) User Guide

## Overview

The BTC Max Knowledge Agent now includes real-time text-to-speech functionality powered by ElevenLabs API. This feature converts the assistant's responses to natural-sounding speech, providing an enhanced interactive experience.

## Features

- **Real-time Speech Synthesis**: Converts assistant responses to audio using ElevenLabs API
- **Smart Caching**: Caches generated audio for instant replay without re-synthesis
- **User Controls**: Toggle voice on/off and adjust volume
- **Visual Feedback**: Waveform animation during synthesis
- **Error Handling**: Graceful fallback to text-only mode when TTS is unavailable
- **Content Filtering**: Only speaks main response content, filtering out sources and metadata

## Setup Instructions

### 1. Install Dependencies

Ensure you have the required dependencies installed:

```bash
pip install -r requirements.txt
```

The TTS feature requires the `elevenlabs` Python package, which is included in the requirements.

### 2. Get ElevenLabs API Key

1. Visit [ElevenLabs](https://elevenlabs.io/) and create an account
2. Navigate to your profile settings to find your API key
3. Copy the API key for the next step

### 3. Configure Environment Variables

Create or update your `.env` file with your ElevenLabs API key:

```bash
# ElevenLabs TTS Configuration
ELEVEN_LABS_API_KEY=your_api_key_here
```

**Important**: Never commit your API key to version control. The `.env` file should be in your `.gitignore`.

### 4. Launch the Application

Start the Bitcoin Assistant with TTS enabled:

```bash
python launch_bitcoin_assistant.py
```

The application will automatically detect the API key and enable TTS functionality.

## Using the TTS Feature

### User Interface Controls

When you launch the application, you'll see two new controls beneath the chat interface:

1. **Enable Voice Toggle**: Turn text-to-speech on or off
2. **Voice Volume Slider**: Adjust the audio playback volume (0-100%)

### Basic Usage

1. **Ask a Question**: Type your Bitcoin-related question as usual
2. **Automatic Speech**: If voice is enabled, the response will be automatically converted to speech
3. **Visual Feedback**: A waveform animation appears during speech synthesis
4. **Instant Replay**: Previously generated audio is cached for instant playback

### Voice Controls

- **Enable/Disable Voice**: Click the "Enable Voice" toggle to turn TTS on or off
- **Adjust Volume**: Use the volume slider to set your preferred audio level
- **Settings Persistence**: Your preferences are saved in browser storage

## Configuration Options

### Default Voice Settings

The system uses these default settings:

- **Voice**: ElevenLabs default voice (JBFqnCBsd6RMkjVDRZzb)
- **Model**: eleven_multilingual_v2
- **Format**: MP3 44.1kHz 128kbps
- **Volume**: 70%
- **Cache Size**: 100 entries or 50MB

### Advanced Configuration

For developers who want to customize the TTS behavior, you can modify the configuration in `src/utils/tts_service.py`:

```python
@dataclass
class TTSConfig:
    api_key: str
    voice_id: str = "JBFqnCBsd6RMkjVDRZzb"  # Change voice
    model_id: str = "eleven_multilingual_v2"  # Change model
    output_format: str = "mp3_44100_128"      # Change format
    volume: float = 0.7                       # Default volume
    cache_size: int = 100                     # Cache entries
```

## Troubleshooting

### Common Issues

#### 1. No Audio Output

**Symptoms**: Text appears but no speech is generated

**Solutions**:
- Check that "Enable Voice" toggle is turned on
- Verify your ElevenLabs API key is correctly set in `.env`
- Check your system audio settings and volume
- Look for error indicators in the UI (red error icon)

#### 2. API Key Errors

**Symptoms**: Red error icon appears, voice is disabled

**Solutions**:
- Verify your API key is correct and active
- Check that you have sufficient ElevenLabs API credits
- Ensure the API key has proper permissions

#### 3. Slow Speech Generation

**Symptoms**: Long delays before audio plays

**Solutions**:
- Check your internet connection
- Verify ElevenLabs service status
- Consider using a different voice model for faster synthesis

#### 4. Audio Quality Issues

**Symptoms**: Distorted or poor quality audio

**Solutions**:
- Check your system audio drivers
- Try adjusting the volume slider
- Verify your browser supports MP3 audio playback

### Error Indicators

The system provides visual feedback for different error states:

- **🔴 Red Icon**: API key invalid or missing
- **🟡 Yellow Icon**: Rate limit exceeded (automatic retry)
- **🟠 Orange Icon**: Server error (automatic retry)
- **⚫ Gray Icon**: Network connectivity issues

### Logging and Debugging

For troubleshooting, you can enable debug logging by setting the log level:

```bash
export LOG_LEVEL=DEBUG
python launch_bitcoin_assistant.py
```

Check the application logs for detailed TTS operation information:

- Synthesis requests and responses
- Cache hit/miss statistics
- Error details and retry attempts
- Performance metrics

## Performance Optimization

### Caching Benefits

The TTS system includes intelligent caching:

- **Memory Cache**: Instant replay of recently generated audio
- **Persistent Cache**: Audio survives application restarts
- **Smart Eviction**: Automatically manages memory usage

### Best Practices

1. **Keep Voice Enabled**: Caching works best when voice stays enabled
2. **Consistent Questions**: Similar questions benefit from cached responses
3. **Monitor Usage**: Check ElevenLabs usage to manage API costs
4. **Network Stability**: Stable internet improves synthesis reliability

## API Usage and Costs

### ElevenLabs Pricing

- TTS synthesis consumes ElevenLabs API credits
- Cached audio doesn't consume additional credits
- Monitor your usage in the ElevenLabs dashboard

### Cost Optimization

- Enable caching to reduce API calls
- Use shorter responses when possible
- Consider voice model selection for cost vs. quality balance

## Security Considerations

### API Key Security

- Never share your API key publicly
- Use environment variables, not hardcoded keys
- Regularly rotate your API keys
- Monitor API usage for unauthorized access

### Content Privacy

- Text sent to ElevenLabs for synthesis
- Audio is cached locally, not transmitted elsewhere
- Clear cache if handling sensitive information

## Support and Resources

### Documentation

- [ElevenLabs API Documentation](https://docs.elevenlabs.io/)
- [Project README](../README.md)
- [TTS Feature Documentation](TTS_FEATURE_DOCUMENTATION.md)

### Getting Help

If you encounter issues:

1. Check this user guide first
2. Review the troubleshooting section
3. Check application logs for error details
4. Consult the project documentation
5. Report bugs through the project's issue tracker

### Feature Requests

The TTS feature is actively developed. Suggestions for improvements are welcome:

- Additional voice options
- Custom voice training
- Advanced audio controls
- Integration with other TTS providers

## Version History

- **v1.0**: Initial TTS integration with ElevenLabs
- **v1.1**: Added caching and performance optimizations
- **v1.2**: Enhanced error handling and user controls
- **v1.3**: Added visual feedback and animations