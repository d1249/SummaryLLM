# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.1.0] - 2024-10-15

### ⚠️ BREAKING CHANGES
- **Removed: PII detection and masking functionality** - All privacy-related code has been removed
- **Schema Migration: V2 → V3** - `EnhancedDigestV3` now uses plain text fields instead of masked fields
- **Removed fields:** `owners_masked`, all `*_masked` fields
- **Pipeline version bumped to 1.1.0** due to breaking changes

### Added
- `EnhancedDigestV3` schema with neutral fields (`owners`, `participants`)
- New prompt version `mvp.5` for V3 schema
- `MIGRATION.md` documenting schema migration from V2 to V3
- End-to-end tests for pipeline without PII handling (`test_end2end_no_pii.py`)
- Backward compatibility support for V2 schema rendering

### Changed
- **Prompt version: mvp.5** (default for new digests)
- **Schema version: 3.0** for EnhancedDigestV3
- Markdown renderer now displays plain names instead of masked tokens
- LLM Gateway dynamically uses V3 schema when `prompt_version="mvp.5"`
- Simplified JSON schema validation without PII checks

### Removed
- **PII detection and masking** - Complete removal of privacy module
- `digest_core/privacy/` directory (masking.py, detectors, regex patterns)
- PII-related metrics (`pii_violations_total`, `masking_violations`)
- `MaskingConfig` from configuration
- `enforce_input_masking` and `enforce_output_masking` options
- `[[REDACT:*]]` token handling in renderers
- `test_masking.py` and PII-related test assertions
- `owners_masked` field from all schemas

### Migration Guide
- See `MIGRATION.md` for detailed migration instructions
- Existing V2 digests will continue to render correctly
- New digests use V3 schema with plain text fields

---

### Previous Releases

### Added (Pre-1.1.0)
- One-command installation scripts (install.sh, quick-install.sh)
- Comprehensive documentation restructure with organized docs/ directory
- Monitoring and observability guides
- Project structure cleanup with proper .gitignore and .editorconfig
- Detailed roadmap and planning documentation
- Quality metrics and KPI documentation
- Mattermost integration planning
- Development guides and code examples

### Changed (Pre-1.1.0)
- Documentation organization: moved all docs to docs/ directory with logical structure
- README structure: minimized root README, added comprehensive documentation links
- Project structure: created scripts/ directory for utility scripts
- Enhanced troubleshooting documentation with EWS connection details

### Fixed (Pre-1.1.0)
- Missing root .gitignore file
- Inconsistent documentation structure
- Lack of development and planning documentation

## [0.1.0] - 2024-01-15

### Added
- Initial release
- EWS integration with NTLM authentication
- LLM-powered digest generation
- Privacy-first design with PII handling via LLM Gateway
- Idempotent processing with T-48h rebuild window
- Dry-run mode for testing
- Prometheus metrics and health checks
- Structured JSON logs with PII handling
- Schema validation with Pydantic
- Docker support with non-root container
- Interactive setup wizard
- Comprehensive test suite
