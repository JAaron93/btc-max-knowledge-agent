import os
import sys
import importlib
import pytest

# Ensure src is on path
PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.append(SRC_DIR)

from security.prompt_injection_detector import (  # noqa: E402
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

    # intentionally using internal helper for precise count verification
    counts = [detector._count_tokens(t) for t in text_cases]
    assert all(isinstance(c, int) and c >= 1 for c in counts)

    info = detector.get_detection_statistics()
    if TIKTOKEN_AVAILABLE:
        assert info["tokenizer_info"]["tokenizer_loaded"] is True
        assert info["tokenizer_info"]["fallback_method"] == "tiktoken"
    else:
        assert info["tokenizer_info"]["tokenizer_loaded"] is False
        assert (
            info["tokenizer_info"]["fallback_method"]
            == "character_based_approximation"
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
async def test_fallback_simulation_when_tiktoken_unavailable(monkeypatch):
    """
    Simulate absence of tiktoken to ensure the character-based
    fallback path remains robust.
    """
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
            info["tokenizer_info"]["fallback_method"]
            == "character_based_approximation"
        )

        code_text = (
            "function f(x){ return x===0 ? 1 : f(x-1)+f(x-2); } "
            "// => test"
        )
        count = detector._count_tokens(code_text)
        assert isinstance(count, int) and count > 0
    finally:
        if saved is not None:
            sys.modules["tiktoken"] = saved