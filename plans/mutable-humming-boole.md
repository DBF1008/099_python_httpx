# Fix Auth Flow Reuse Bug & Clean Up Auth Base Class

## Context

Custom Auth classes that read both request body and response body for signature refresh encounter issues when the same auth instance is reused across requests: DigestAuth-style cached challenge state (`_last_challenge`, `_nonce_count`) leaks between invocations, and the inner `auth_flow()` generator is never explicitly closed by the sync/async bridge wrappers. Additionally, `BasicAuth` and `NetRCAuth` duplicate the `_build_auth_header` method.

## Changes

### 1. `httpx/_auth.py` — Auth base class

**Add shared `_build_auth_header` to `Auth`:**
- Move the basic-auth header builder (`b64encode(user:pass)`) from `BasicAuth` and `NetRCAuth` onto the `Auth` base class as a static-like method.
- Both subclasses inherit it; remove the duplicate definitions.

**Fix generator lifecycle in `sync_auth_flow` / `async_auth_flow`:**
- Wrap the inner `self.auth_flow(request)` generator in `try/finally` so `flow.close()` is always called, even if the outer bridge generator is closed by the client (e.g. on error or early return).
- This ensures any `finally`/context-manager cleanup inside custom `auth_flow()` implementations runs deterministically, rather than relying on GC.
- Both sync and async bridges get identical structure.

### 2. `httpx/_auth.py` — DigestAuth

**Fix stale `_last_challenge` on 401:**
- At the top of `auth_flow()`, when a 401 is received, always clear `self._last_challenge = None` before checking for a new digest challenge.
- If a valid digest challenge is found, `_last_challenge` is re-set to the new value.
- If no digest challenge is found (non-digest 401), `_last_challenge` stays `None` — the next request starts fresh without a stale cached challenge.
- This prevents the scenario where a stale cached challenge is used on subsequent requests when the server has moved to a different auth scheme.

### 3. `tests/test_auth.py` — Unit tests

Add tests:
- `test_digest_auth_clears_challenge_on_non_digest_401`: After a successful digest auth exchange, simulate a 401 without a digest challenge. Verify `_last_challenge` is cleared and the next request has no auth header.
- `test_digest_auth_async_flow_equivalent`: Verify `async_auth_flow` produces the same sequence of requests/responses as `sync_auth_flow` for DigestAuth.

### 4. `tests/client/test_auth.py` — Integration tests

Add tests:
- `test_sync_digest_auth_unavailable_streaming_body`: Sync counterpart of the existing async test — sync generator body + DigestAuth + sync client → `StreamConsumed`.
- `test_sync_auth_reads_response_body`: Sync counterpart of the existing `test_async_auth_reads_response_body`.
- `test_auth_flow_reuse_clears_stale_challenge`: Use same DigestAuth instance across two requests where the second request's server-side challenge changes. Verify stale state is cleared.
- `test_auth_with_request_and_response_body`: Custom auth that sets both `requires_request_body=True` and `requires_response_body=True`, testing the "signature refresh" pattern the user described. Both sync and async.
- `test_sync_and_async_auth_flow_consistency`: Custom auth tested with both `Client` and `AsyncClient`, verifying identical behavior.

## Files Modified

| File | Change |
|---|---|
| `httpx/_auth.py` | Auth base class: shared `_build_auth_header`, generator lifecycle try/finally; DigestAuth: clear stale challenge |
| `tests/test_auth.py` | New unit tests for challenge clearing and async flow equivalence |
| `tests/client/test_auth.py` | New integration tests for sync streaming, response body auth, reuse, and consistency |
