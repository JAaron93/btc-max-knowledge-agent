#!/usr/bin/env python3
"""
Security-aware prompt processor with session termination capabilities.

This module implements prompt processing logic that handles multiple prompts
and terminates sessions after high-confidence security violations are detected.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from ..web.session_manager import SessionManager
from .interfaces import IPromptInjectionDetector

logger = logging.getLogger(__name__)


@dataclass
class PromptProcessingResult:
    """Result of processing multiple prompts with security evaluation."""

    high_confidence_detected: bool
    detection_index: int
    session_terminated: bool
    total_prompts_processed: int
    detection_results: List[Dict[str, Any]]


class SecurePromptProcessor:
    """
    Secure prompt processor with session termination capabilities.

    This processor handles batches of prompts and implements security measures:
    - Detects prompt injection attempts
    - Terminates sessions after high-confidence detections
    - Guards against processing additional prompts after session termination
    """

    def __init__(
        self,
        injection_detector: IPromptInjectionDetector,
        session_manager: SessionManager,
        high_confidence_threshold: float = 0.9,
    ):
        """
        Initialize secure prompt processor.

        Args:
            injection_detector: Prompt injection detector implementation
            session_manager: Session manager for session operations
            high_confidence_threshold: Threshold for high-confidence detections
        """
        self.injection_detector = injection_detector
        self.session_manager = session_manager
        self.high_confidence_threshold = high_confidence_threshold

    async def process_prompts_with_security(
        self,
        prompts: List[str],
        session_id: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> PromptProcessingResult:
        """
        Process multiple prompts with security evaluation and session termination.

        This method implements the core security logic:
        1. Process prompts sequentially
        2. Evaluate each prompt for injection attempts
        3. Terminate session after first high-confidence detection
        4. Guard subsequent iterations when session is None

        Args:
            prompts: List of prompts to process
            session_id: Session ID for context
            context: Additional context for detection

        Returns:
            PromptProcessingResult with processing details
        """
        if not prompts:
            return PromptProcessingResult(
                high_confidence_detected=False,
                detection_index=-1,
                session_terminated=False,
                total_prompts_processed=0,
                detection_results=[],
            )

        # Initialize processing state
        high_confidence_detected = False
        detection_index = -1
        session_terminated = False
        detection_results = []
        session = self.session_manager.get_session(session_id)

        # Prepare context for detection
        if context is None:
            context = {}
        context.update(
            {
                "session_id": session_id,
                "source_ip": context.get("source_ip", "unknown"),
                "user_agent": context.get("user_agent", "unknown"),
            }
        )

        # Process prompts in the malicious prompt loop
        for i, prompt in enumerate(prompts):
            logger.debug(f"Processing prompt {i+1}/{len(prompts)}: {prompt[:50]}...")

            # Guard: Check if session is None (terminated in previous iteration)
            if session is None:
                logger.info(
                    f"Session {session_id} is None, breaking prompt processing loop at index {i}"
                )
                break

            try:
                # Detect injection in the current prompt
                result = await self.injection_detector.detect_injection(prompt, context)

                detection_results.append(
                    {
                        "prompt_index": i,
                        "prompt": prompt,
                        "injection_detected": result.injection_detected,
                        "confidence_score": result.confidence_score,
                        "injection_type": result.injection_type,
                        "risk_level": (
                            result.risk_level.value if result.risk_level else None
                        ),
                        "recommended_action": (
                            result.recommended_action.value
                            if result.recommended_action
                            else None
                        ),
                    }
                )

                # Check for high-confidence detection
                if result.confidence_score >= self.high_confidence_threshold:
                    high_confidence_detected = True
                    detection_index = i

                    logger.warning(
                        f"High-confidence injection detected at prompt {i}: "
                        f"'{prompt}' (confidence: {result.confidence_score:.3f})"
                    )

                    # Terminate session by removing it from the session manager
                    # (This would normally be done by the application logic)
                    removed = self.session_manager.remove_session(session_id)
                    session_terminated = removed

                    if removed:
                        logger.info(
                            f"Session {session_id} terminated after high-confidence detection"
                        )
                        # Set session to None to trigger guard in next iteration
                        session = None
                    else:
                        logger.warning(
                            f"Failed to remove session {session_id} from session manager"
                        )

                    # Break out of the loop (no further prompts will have a session)
                    break
                else:
                    # For low-confidence or benign prompts, session should still exist
                    # Verify session still exists
                    session = self.session_manager.get_session(session_id)
                    if session is None:
                        logger.warning(
                            f"Session {session_id} unexpectedly None for benign prompt {i}"
                        )
                        session_terminated = True
                        break

            except Exception as e:
                logger.error(f"Error processing prompt {i}: {e}")
                detection_results.append(
                    {
                        "prompt_index": i,
                        "prompt": prompt,
                        "error": str(e),
                        "injection_detected": False,
                        "confidence_score": 0.0,
                    }
                )

        return PromptProcessingResult(
            high_confidence_detected=high_confidence_detected,
            detection_index=detection_index,
            session_terminated=session_terminated,
            total_prompts_processed=len(detection_results),
            detection_results=detection_results,
        )

    def validate_session_termination(self, session_id: str) -> bool:
        """
        Validate that a session has been properly terminated.

        Args:
            session_id: Session ID to validate

        Returns:
            True if session is terminated (None), False if still exists
        """
        session = self.session_manager.get_session(session_id)
        return session is None

    async def process_single_prompt_with_guard(
        self, prompt: str, session_id: str, context: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Process a single prompt with session guard.

        This method implements the guard logic for individual prompt processing:
        - Check if session exists before processing
        - Return early if session is None
        - Process prompt only if session is valid

        Args:
            prompt: Single prompt to process
            session_id: Session ID for context
            context: Additional context for detection

        Returns:
            Tuple of (should_continue, detection_result)
            should_continue is False if session is None
        """
        # Guard: Check if session is None before processing
        session = self.session_manager.get_session(session_id)
        if session is None:
            logger.info(f"Session {session_id} is None, skipping prompt processing")
            return False, None

        # Process the prompt normally
        if context is None:
            context = {}
        context.update(
            {
                "session_id": session_id,
                "source_ip": context.get("source_ip", "unknown"),
                "user_agent": context.get("user_agent", "unknown"),
            }
        )

        try:
            result = await self.injection_detector.detect_injection(prompt, context)

            detection_result = {
                "prompt": prompt,
                "injection_detected": result.injection_detected,
                "confidence_score": result.confidence_score,
                "injection_type": result.injection_type,
                "risk_level": result.risk_level.value if result.risk_level else None,
                "recommended_action": (
                    result.recommended_action.value
                    if result.recommended_action
                    else None
                ),
            }

            return True, detection_result

        except Exception as e:
            logger.error(f"Error processing single prompt: {e}")
            return True, {
                "prompt": prompt,
                "error": str(e),
                "injection_detected": False,
                "confidence_score": 0.0,
            }
