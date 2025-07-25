# Requirements Document

## Introduction

This feature integrates real-time text-to-speech functionality into the existing Gradio interface for the BTC Max Knowledge Agent. The system will convert Pinecone Assistant responses to audio using ElevenLabs API, providing users with an enhanced interactive experience through voice output. The implementation includes audio caching, user controls, visual feedback, and robust error handling.

## Requirements

### Requirement 1

**User Story:** As a user of the BTC Max Knowledge Agent, I want to hear the assistant's responses spoken aloud, so that I can consume information through audio while multitasking or for accessibility purposes.

#### Acceptance Criteria

1. WHEN the Pinecone Assistant returns a text response THEN the system SHALL send the text to the ElevenLabs API for speech synthesis within 100 milliseconds of receiving the response
2. WHEN the ElevenLabs API returns audio data THEN the system SHALL stream the generated audio back to the UI for playback with a maximum buffering delay of 200 milliseconds
3. WHEN audio synthesis is in progress THEN the system SHALL display a waveform animation with the following specifications:
   - Animation height: 24 pixels maximum
   - Animation width: 120 pixels maximum  
   - Frame rate: 30 FPS
   - Duration: Continuous until synthesis completes or fails
   - Visual style: Animated bars or wave pattern indicating active processing
4. WHEN the audio synthesis completes successfully AND the "Enable Voice" toggle is enabled THEN the system SHALL automatically initiate audio playback within 50 milliseconds of synthesis completion
5. WHEN the audio synthesis completes successfully BUT the "Enable Voice" toggle has been disabled during synthesis THEN the system SHALL NOT play the audio and SHALL cache it for potential future use
6. WHEN audio synthesis fails or times out (after 30 seconds) THEN the system SHALL stop the waveform animation and display an error indicator without interrupting the text display

### Requirement 2

**User Story:** As a user, I want to control whether voice output is enabled and adjust the volume, so that I can customize my experience based on my preferences and environment.

#### Acceptance Criteria

1. WHEN viewing the Gradio interface THEN the system SHALL display a toggle switch labeled "Enable Voice" directly beneath the chatbot window
2. WHEN viewing the Gradio interface THEN the system SHALL display a volume slider labeled "Voice Volume" directly beneath the chatbot window
3. WHEN the "Enable Voice" toggle is disabled THEN the system SHALL NOT synthesize or play audio for responses
4. WHEN the "Enable Voice" toggle is enabled THEN the system SHALL synthesize and play audio for new responses
5. WHEN the volume slider is adjusted THEN the system SHALL apply the new volume level to audio playback
6. WHEN the user modifies the "Enable Voice" toggle state THEN the system SHALL persist this setting in browser local storage to maintain the preference across browser sessions
7. WHEN the user adjusts the "Voice Volume" slider THEN the system SHALL persist this setting in browser local storage to maintain the preference across browser sessions
8. WHEN the interface loads for the first time (no previous settings stored) THEN the system SHALL initialize with default values: "Enable Voice" toggle set to enabled (true) and "Voice Volume" slider set to 70%
9. WHEN the interface loads and previous settings exist in local storage THEN the system SHALL restore the user's last saved preferences for both "Enable Voice" toggle state and "Voice Volume" level

### Requirement 3

**User Story:** As a user, I want previously generated audio to be cached and replayed instantly, so that I don't have to wait for re-synthesis of the same content.

#### Acceptance Criteria

1. WHEN a unique response is synthesized for the first time THEN the system SHALL cache the generated audio data using the following specifications:
   - **Cache Key:** SHA-256 hash of the cleaned response text (after applying Requirement 7 text-cleaning algorithm)
   - **Storage Medium:** In-memory LRU (Least Recently Used) cache with a maximum capacity of 100 entries OR 50MB total size, whichever limit is reached first
   - **Cache Entry Data:** Audio bytes, timestamp of creation, access count, and original text hash
   - **Persistence:** Optional on-disk cache per user session stored in temporary directory, cleared on application restart

2. WHEN the same response text is encountered again THEN the system SHALL generate the SHA-256 hash of the cleaned text and retrieve cached audio without calling the ElevenLabs API, updating the entry's access count and last-accessed timestamp

3. WHEN the cache reaches its size limit (100 entries or 50MB) THEN the system SHALL evict the least recently used entries until the cache is within limits

4. WHEN a cached entry exceeds the TTL (Time To Live) of 24 hours THEN the system SHALL automatically remove the entry from the cache during the next cleanup cycle

5. WHEN cached audio is played THEN the system SHALL NOT display the waveform animation and playback SHALL begin within 10 milliseconds (instant playback)

6. WHEN the application starts THEN the system SHALL initialize an empty cache and optionally attempt to load any valid session-based cache entries that have not exceeded their 24-hour TTL

### Requirement 4

**User Story:** As a user, I want the system to handle API errors gracefully, so that my experience isn't disrupted when the text-to-speech service is unavailable.

#### Acceptance Criteria

1. WHEN the ElevenLabs API is unavailable or returns an error THEN the system SHALL fall back to a muted state
2. WHEN in error fallback state THEN the system SHALL display an unobtrusive red error icon that meets the following specifications:
   - **Visual Design:** Red color with minimum contrast ratio of 4.5:1 against background (WCAG AA compliance)
   - **Accessibility:** ARIA label "Text-to-speech service unavailable" for screen reader compatibility
   - **Tooltip:** Hover/focus tooltip explaining "Voice synthesis temporarily unavailable - text will continue to display normally"
   - **Position:** Adjacent to voice controls without obscuring primary content
3. WHEN an API error occurs THEN the system SHALL NOT interrupt the text display or other functionality
4. WHEN in error fallback state THEN the system SHALL automatically check for API recovery every 30 seconds by attempting a lightweight health check request to the ElevenLabs API
5. WHEN the API recovery check succeeds (receives a successful response) THEN the system SHALL automatically resume normal voice synthesis operation and remove the error icon
6. WHEN API recovery checks continue to fail after 10 consecutive attempts (5 minutes) THEN the system SHALL reduce the recovery check frequency to every 2 minutes to minimize unnecessary API calls

### Requirement 5

**User Story:** As a user, I want only the main response content to be voiced, so that I'm not distracted by source citations and metadata being read aloud.

#### Acceptance Criteria

1. WHEN the Pinecone Assistant returns a response with sources THEN the system SHALL extract only the main response text for synthesis
2. WHEN the Pinecone Assistant returns a response with sources THEN the system SHALL NOT include source citations in the audio synthesis
3. WHEN the Pinecone Assistant returns a response with metadata THEN the system SHALL NOT include metadata in the audio synthesis
4. WHEN processing response text THEN the system SHALL apply the standardized text-cleaning algorithm as defined in Requirement 7

### Requirement 7

**User Story:** As a developer, I want a standardized text-cleaning algorithm for TTS processing, so that implementations are consistent and audio quality is optimized for speech synthesis.

#### Acceptance Criteria

1. WHEN processing text for TTS synthesis THEN the system SHALL apply the following text-cleaning steps in order:
   - Strip all markdown formatting including: bold (**text**), italic (*text*), headers (# text), code blocks (```code```), inline code (`code`), links ([text](url)), and blockquotes (> text)
   - Remove all HTML tags and entities (e.g., &lt;div&gt;, &amp;, &nbsp;)
   - Strip citation blocks and reference markers including: [^1], [1], (Source: ...), **Sources**, ## Sources, and similar patterns
   - Remove URLs and email addresses completely
   - Convert special characters to speech-friendly equivalents: & → "and", % → "percent", @ → "at"
   - Collapse multiple consecutive whitespace characters (spaces, tabs, newlines) into single spaces
   - Remove leading and trailing whitespace from the final result

2. WHEN the cleaned text exceeds the ElevenLabs API character limit THEN the system SHALL truncate the text to a maximum of 2,500 characters while preserving sentence boundaries when possible

3. WHEN text truncation occurs THEN the system SHALL log a warning message indicating the original and truncated character counts

4. WHEN the cleaned text is empty or contains only whitespace THEN the system SHALL return the fallback message: "No content available for synthesis."

5. WHEN text cleaning fails due to processing errors THEN the system SHALL log the error and return the original text with basic whitespace normalization only

### Requirement 6

**User Story:** As a developer, I want the system to use the ELEVEN_LABS_API_KEY environment variable for authentication, so that API credentials are managed securely.

#### Acceptance Criteria

1. WHEN the system initializes THEN it SHALL read the ELEVEN_LABS_API_KEY from environment variables  
2. WHEN making requests to ElevenLabs API THEN the system SHALL use the environment variable for authentication  
3. WHEN the ELEVEN_LABS_API_KEY is missing or invalid THEN the system SHALL log an appropriate error and disable voice functionality
4. WHEN the API key is present and valid THEN the system SHALL enable voice functionality automatically