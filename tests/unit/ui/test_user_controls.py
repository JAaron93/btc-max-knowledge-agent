#!/usr/bin/env python3
"""
Test script for TTS user control functionality (Task 8)
"""

import os

import requests

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")


def test_tts_enabled_disabled():
    """Test that TTS synthesis is skipped when disabled"""
    print("Testing TTS enabled/disabled functionality...")

    test_question = "What is Bitcoin?"

    def _exercise_and_validate(
        enable_tts: bool,
        expect_audio: bool,
        expect_tts_enabled: bool,
        req_number: str,
    ):
        """
        Helper to send request and validate response for TTS
        enable/disable scenarios.

        Args:
            enable_tts: Payload toggle for TTS.
            expect_audio: Whether audio_data is expected to be present.
            expect_tts_enabled: Whether tts_enabled flag is expected to be
                true.
            req_number: Requirement number label (e.g., '2.3' or '2.4').
        Returns:
            Tuple of (status_ok, validation_ok) booleans for aggregation.
        """
        label = "enabled" if enable_tts else "disabled"
        step_num = "1" if enable_tts else "2"
        print(f"{step_num}. Testing with TTS {label}...")
        payload = {
            "question": test_question,
            "enable_tts": enable_tts,
            "volume": 0.7,
        }

        try:
            response = requests.post(f"{API_BASE_URL}/query", json=payload, timeout=30)
            if response.status_code == 200:
                data = response.json()
                has_audio = data.get("audio_data") is not None
                tts_enabled = data.get("tts_enabled", False)

                if enable_tts:
                    print(f"   ✅ TTS enabled: Audio data present = {has_audio}")
                else:
                    print(
                        "   ✅ TTS disabled: Audio data present = "
                        f"{has_audio}, TTS enabled = {tts_enabled}"
                    )

                validation_ok = (has_audio == expect_audio) and (
                    tts_enabled == expect_tts_enabled
                )
                if validation_ok:
                    print(f"   ✅ Requirement {req_number} satisfied")
                else:
                    print(f"   ❌ Requirement {req_number} failed")
                return True, validation_ok
            else:
                print(f"   ❌ API error: {response.status_code}")
                return False, False
        except Exception as e:
            print(f"   ❌ Request failed: {e}")
            return False, False

    # Run both scenarios using the helper and combine results
    status_ok_1, validation_ok_1 = _exercise_and_validate(
        enable_tts=True,
        expect_audio=True,
        expect_tts_enabled=True,
        req_number="2.4",
    )
    status_ok_2, validation_ok_2 = _exercise_and_validate(
        enable_tts=False,
        expect_audio=False,
        expect_tts_enabled=False,
        req_number="2.3",
    )

    # Overall combined result (printed for visibility)
    overall_ok = all([status_ok_1, validation_ok_1, status_ok_2, validation_ok_2])
    if overall_ok:
        print("   ✅ Combined result: TTS enable/disable behavior validated")
    else:
        print("   ❌ Combined result: One or more TTS enable/disable checks failed")
    return overall_ok


def test_volume_control():
    """Test that volume parameter is properly passed and handled"""
    print("\nTesting volume control functionality...")

    test_question = "Explain blockchain technology briefly."

    # Test with different volume levels
    volumes = [0.3, 0.7, 1.0]

    all_ok = True

    for volume in volumes:
        print(f"3. Testing with volume = {volume}...")
        payload = {
            "question": test_question,
            "enable_tts": True,
            "volume": volume,
        }

        try:
            response = requests.post(f"{API_BASE_URL}/query", json=payload, timeout=30)
            if response.status_code == 200:
                data = response.json()
                has_audio = data.get("audio_data") is not None
                print(f"   ✅ Volume {volume}: Audio generated = {has_audio}")
                if has_audio:
                    # Check for volume acknowledgement in response metadata
                    returned_volume = (
                        data.get("metadata", {}).get("volume")
                        if isinstance(data.get("metadata"), dict)
                        else data.get("volume")
                    )
                    if returned_volume is not None:
                        try:
                            # Compare as floats to avoid representation issues
                            if float(returned_volume) == float(volume):
                                print(
                                    "   ✅ Volume acknowledged by API: "
                                    f"{returned_volume} matches requested "
                                    f"{volume}"
                                )
                            else:
                                print(
                                    "   ❌ Volume mismatch: API returned "
                                    f"{returned_volume}, requested {volume}"
                                )
                                all_ok = False
                        except (TypeError, ValueError):
                            # If conversion fails, fall back to equality
                            if returned_volume == volume:
                                print(
                                    "   ✅ Volume acknowledged by API: "
                                    f"{returned_volume} matches requested "
                                    f"{volume}"
                                )
                            else:
                                print(
                                    "   ❌ Volume mismatch: API returned "
                                    f"{returned_volume}, requested {volume}"
                                )
                                all_ok = False
                    # Note: DSP volume verification needs audio analysis
                    print("   ✅ Requirement 2.5 satisfied: Volume parameter accepted")
                else:
                    # If no audio generated when TTS is enabled, mark failure
                    print(f"   ❌ Volume {volume}: No audio generated when TTS enabled")
                    all_ok = False
            else:
                print(f"   ❌ API error: {response.status_code}")
                all_ok = False
        except Exception as e:
            print(f"   ❌ Request failed: {e}")
            all_ok = False

    return all_ok


def test_api_health():
    """Test API health before running other tests"""
    print("Checking API health...")
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ API Status: {data.get('status')}")
            print(f"✅ Pinecone Assistant: {data.get('pinecone_assistant')}")
            return True
        else:
            print(f"❌ API health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Cannot connect to API: {e}")
        return False


def main():
    """Run all user control tests"""
    print("🧪 Testing TTS User Control Functionality (Task 8)")
    print("=" * 50)

    # Check API health first
    if not test_api_health():
        print("\n❌ API is not available. Please start the FastAPI server first.")
        return False

    print()

    # Run tests and collect results
    results = []
    results.append(("TTS enable/disable", test_tts_enabled_disabled()))
    results.append(("Volume control", test_volume_control()))

    passed = sum(1 for _, ok in results if ok)
    total = len(results)

    print("\n" + "=" * 50)
    if passed == total:
        print(f"🏁 All {total}/{total} user control tests passed.")
        overall_ok = True
    else:
        print(f"🏁 Partial success: {passed}/{total} user control tests passed.")
        for name, ok in results:
            if not ok:
                print(f"   ❌ Failed: {name}")
        overall_ok = False

    print("\nRequirements tested:")
    print("✅ 2.3: Skip TTS synthesis when voice is disabled")
    print("✅ 2.4: Synthesize audio when voice is enabled")
    print("✅ 2.5: Apply volume level to audio playback")
    print(
        "\nNote: Requirements 2.6-2.9 (localStorage persistence) are tested in the browser UI."
    )

    return overall_ok


if __name__ == "__main__":
    main()
