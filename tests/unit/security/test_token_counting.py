import sys
import importlib
import pytest

from security.prompt_injection_detector import (
    PromptInjectionDetector,
    TIKTOKEN_AVAILABLE,
)


@pytest.mark.asyncio
async def test_token_counting_with_tiktoken_available():
    detector = PromptInjectionDetector({"max_context_tokens": 8_192})

    text_cases = [
        "Hello world! This is a simple sentence.",
        "中文测试：你好世界！这是一个token计数测试。",
        (
            "def fib(n):\n"
            "    return 1 if n <= 2 else fib(n-1) + fib(n-2)\n"
            "# => lambda x: x * 2"
        ),
        'JSON-like: {"key": [1, 2, 3], "ok": true} --- ### delimiter',
    ]

    # Use public API for token counting
    counts = [detector.count_tokens(t) for t in text_cases]
    assert all(isinstance(c, int) and c >= 1 for c in counts)

    info = detector.get_detection_statistics()
    if TIKTOKEN_AVAILABLE:
        assert info["tokenizer_info"]["tokenizer_loaded"] is True
        assert info["tokenizer_info"]["fallback_method"] == "tiktoken"
    else:
        assert info["tokenizer_info"]["tokenizer_loaded"] is False
        assert (
            info["tokenizer_info"]["fallback_method"] == "character_based_approximation"
        )


@pytest.mark.asyncio
async def test_context_window_validation_boundary():
    detector = PromptInjectionDetector({"max_context_tokens": 64})

    short_text = "A" * 10
    res_ok = await detector.validate_context_window(short_text)
    assert res_ok.is_valid is True
    assert res_ok.recommended_action.name == "ALLOW"

    # enough to exceed 64 tokens in both paths
    long_text = " ".join(["token"] * 500)
    res_bad = await detector.validate_context_window(long_text)
    assert res_bad.is_valid is False
    assert any(
        v.violation_type == "context_window_exceeded" for v in res_bad.violations
    )


@pytest.mark.asyncio
async def test_fallback_simulation_when_tiktoken_unavailable():
    """
    Simulate absence of tiktoken to ensure the character-based
    fallback path remains robust.
    """
    # Skip test if tiktoken wasn't available to begin with
    if "tiktoken" not in sys.modules:
        pytest.skip("tiktoken not available in environment")

    saved = sys.modules.pop("tiktoken", None)
    try:
        mod_name = "security.prompt_injection_detector"
        if mod_name in sys.modules:
            sys.modules.pop(mod_name)
        pid_mod = importlib.import_module(mod_name)
        importlib.reload(pid_mod)

        detector = pid_mod.PromptInjectionDetector({"max_context_tokens": 8_192})

        info = detector.get_detection_statistics()
        assert info["tokenizer_info"]["tiktoken_available"] is False
        assert info["tokenizer_info"]["tokenizer_loaded"] is False
        assert (
            info["tokenizer_info"]["fallback_method"] == "character_based_approximation"
        )

        code_text = "function f(x){ return x===0 ? 1 : f(x-1)+f(x-2); } // => test"
        count = detector.count_tokens(code_text)
        assert isinstance(count, int) and count > 0
    finally:
        # Always restore tiktoken if it was originally present
        if saved is not None:
            sys.modules["tiktoken"] = saved
        # Clean up the reloaded module to avoid side effects
        if mod_name in sys.modules:
            sys.modules.pop(mod_name, None)
