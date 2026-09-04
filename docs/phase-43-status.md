# Phase 43 — AWS credential manager canonicalization

Status: ready for review.

The AWS credential manager now has one maintained implementation path. The historical `*_upgraded.py` module is compatibility-only, migration-era AWS credential tests and the upgrade report are retired, and maintained regression coverage lives under the top-level `tests/` boundary.

## Preserved behavior

- Boto3's standard credential provider chain remains the source of AWS credentials.
- Environment variables retain precedence for application secrets.
- AWS Secrets Manager remains the fallback for configured secrets.
- The historical upgraded import path remains available through a re-export shim.

## Hardened behavior retained from the migration implementation

- Explicit credential-resolution validation.
- Normalized Secrets Manager errors without exposing provider error payloads.
- Configurable retry and network timeout settings.
- Optional in-process secret caching, disabled by default.
- Support for string and UTF-8 binary secret payloads.
