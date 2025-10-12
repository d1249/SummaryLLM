# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- One-command installation scripts (install.sh, quick-install.sh)
- Comprehensive documentation restructure with organized docs/ directory
- Monitoring and observability guides
- Project structure cleanup with proper .gitignore and .editorconfig
- Detailed roadmap and planning documentation
- Quality metrics and KPI documentation
- Mattermost integration planning
- Development guides and code examples

### Changed
- Documentation organization: moved all docs to docs/ directory with logical structure
- README structure: minimized root README, added comprehensive documentation links
- Project structure: created scripts/ directory for utility scripts
- Enhanced troubleshooting documentation with EWS connection details

### Fixed
- Missing root .gitignore file
- Inconsistent documentation structure
- Lack of development and planning documentation

## [0.1.0] - 2024-01-15

### Added
- Initial release
- EWS integration with NTLM authentication
- LLM-powered digest generation
- Privacy-first design with PII masking via LLM Gateway
- Idempotent processing with T-48h rebuild window
- Dry-run mode for testing
- Prometheus metrics and health checks
- Structured JSON logs with automatic PII redaction
- Schema validation with Pydantic
- Docker support with non-root container
- Interactive setup wizard
- Comprehensive test suite
