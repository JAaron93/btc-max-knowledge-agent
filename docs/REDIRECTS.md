# Legacy Documentation Redirects

This mapping preserves backward compatibility for links and references after the docs/test reorganization. Update external references where possible; this file documents canonical new locations.

Format:
- Old Path -> New Path

Core docs
- README.dev.md -> docs/guides/development.md
- CHANGELOG.md -> docs/changelogs/CHANGELOG.md

Guides
- docs/ADMIN_SETUP.md -> docs/ADMIN_SETUP.md
- docs/TTS_USER_GUIDE.md -> docs/TTS_USER_GUIDE.md
- docs/TTS_LOGGING_GUIDE.md -> docs/TTS_LOGGING_GUIDE.md
- docs/logging_optimization_migration.md -> docs/logging_optimization_migration.md
- docs/MULTI_TIER_CACHE.md -> docs/MULTI_TIER_CACHE.md
- docs/guides/installation.md -> docs/guides/installation.md

Security
- docs/SECURITY_ENHANCEMENTS.md -> docs/SECURITY_ENHANCEMENTS.md
- docs/security/SECURITY_POLICY.md -> docs/security/SECURITY_POLICY.md
- src/security/README.md -> docs/ADMIN_SECURITY_SUMMARY.md

Architecture
- docs/architecture/audio_streaming.md -> docs/architecture/audio_streaming.md
- docs/architecture/circuit_breaker.md -> docs/architecture/circuit_breaker.md
- docs/architecture/tts_ui.md -> docs/architecture/tts_ui.md
- docs/architecture/visual_feedback.md -> docs/architecture/visual_feedback.md

Migrations
- docs/migration/argon2_upgrade_notes.md -> docs/migration/argon2_upgrade_notes.md
- docs/migrations/sys-path-hack-replacement.md -> docs/migrations/sys-path-hack-replacement.md

Testing
- tests/README_fixtures.md -> docs/testing/test_configuration_summary.md
- tests/README_PATH_SETUP.md -> docs/migrations/sys-path-hack-replacement.md
- docs/testing/tts_testing_guide.md -> docs/testing/tts_testing_guide.md
- docs/testing/MOVE_PLAN.md -> docs/testing/MOVE_PLAN.md
- tests/TEST_UTILS_ENV_VARS.md -> docs/testing/test_configuration_summary.md

Summaries
- test_improvements_summary.md -> docs/summaries/recent_improvements.md
- docs/summaries/auto_setup_improvements.md -> docs/summaries/auto_setup_improvements.md
- docs/summaries/ci_linting_optimization.md -> docs/summaries/ci_linting_optimization.md
- docs/summaries/is_module_available_improvements.md -> docs/summaries/is_module_available_improvements.md
- docs/summaries/logging_optimization_summary.md -> docs/summaries/logging_optimization_summary.md
- docs/summaries/path_handling_improvements_summary.md -> docs/summaries/path_handling_improvements_summary.md
- docs/summaries/path_setup_fix_summary.md -> docs/summaries/path_setup_fix_summary.md
- docs/summaries/recent_improvements.md -> docs/summaries/recent_improvements.md
- docs/summaries/severity_function_improvements.md -> docs/summaries/severity_function_improvements.md
- docs/summaries/success_events_logic_fix.md -> docs/summaries/success_events_logic_fix.md
- docs/summaries/task_7_error_handling_summary.md -> docs/summaries/task_7_error_handling_summary.md
- docs/summaries/test_assertion_fix.md -> docs/summaries/test_assertion_fix.md
- docs/summaries/thread_safety_fix_summary.md -> docs/summaries/thread_safety_fix_summary.md

Examples (unchanged, documented for reference)
- examples/ADMIN_AUTH_REFACTOR.md -> examples/ADMIN_AUTH_REFACTOR.md
- examples/FUNCTION_COUPLING_REDUCTION.md -> examples/FUNCTION_COUPLING_REDUCTION.md

Notes
- Many docs were already under docs/ with final structure; mappings above include both moved files and confirmation of canonical locations.
- Tests have been consolidated under tests/ with pytest.ini pointing testpaths=tests; no redirection required for test paths beyond the docs references above.

Maintenance
- When relocating or renaming future documents, append a new entry Old -> New and consider updating inbound links in README.md and related docs.