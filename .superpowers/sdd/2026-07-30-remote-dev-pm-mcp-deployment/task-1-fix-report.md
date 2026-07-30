# Task 1 Fix Report

## Fixes

- Normalized generator allowlists to sets at construction, so the Dev PM list-valued tag allowlist intersects safely.
- Removed the obsolete policy-only runtime template and duplicate invalid manifest write. Generation now copies the complete shared runtime once and writes one manifest with the source hash and endpoint counts.
- Added an explicit `allowed_methods` profile/runtime policy. The Dev PM profile configures `GET` only; inventory, manifest, `.env.example`, MCP config, and runtime enforcement agree, including rejecting `HEAD` and `OPTIONS`.

## Verification

- `uv run pytest tests/test_devpm_profile.py tests/test_generated_artifact.py tests/test_generator.py tests/test_runtime.py -q` — 42 passed.
- `uv run python ops/generate_devpm_profile.py --spec specs/trello-openapi.yaml --output /tmp/devpm-cli-check` — succeeded; generated server and copied runtime compiled successfully.

## Concerns

- The smoke spec has no Dev PM tags, so it intentionally generated zero tools; the focused fixture covers the GET/HEAD/OPTIONS filtering behavior.
