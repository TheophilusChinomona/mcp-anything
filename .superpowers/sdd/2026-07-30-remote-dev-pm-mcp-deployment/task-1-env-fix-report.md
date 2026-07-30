# Task 1 Environment Policy Fix Report

## Status

Updated the Task 1 remote secret/environment template so the wrapper-sourced environment explicitly enforces the Dev PM profile's GET-only runtime policy.

## Change

Added this exact line to the `/etc/mcp-anything/speccon-devpm.env` template in `task-1-brief.md`, immediately after `SPECCON_DEVPM_ALLOW_WRITES=false`:

```dotenv
SPECCON_DEVPM_ALLOWED_METHODS=GET
```

The plan's existing Step 6 verification reference remains `methods = GET only`, consistent with the environment template and generated profile configuration.

## Verification

- Deterministic plan-contract assertion checks that the exact line `SPECCON_DEVPM_ALLOWED_METHODS=GET` appears in the Step 4 dotenv block immediately after `SPECCON_DEVPM_ALLOW_WRITES=false`.
- Targeted profile regression tests: `uv run pytest tests/test_devpm_profile.py -q`.

## Concerns

No focused test was added for the Markdown deployment plan; the exact-value assertion is documented above because the existing test suite covers generated profile configuration rather than deployment-plan text.
