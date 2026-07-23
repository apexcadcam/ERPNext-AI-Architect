# RETRY POLICY

**Status:** Foundational — Architecture Only, Not Implemented
**Authority:** Subordinate to [CRAWLER_ARCHITECTURE.md](CRAWLER_ARCHITECTURE.md). Governs recovery from failures at [`CRAWLER_PIPELINE.md § 3`](CRAWLER_PIPELINE.md#3-download), before a failure is classified into [`ERROR_HANDLING.md`](ERROR_HANDLING.md)'s permanent categories.
**Scope:** What is retried, how many times, with what backoff — for exactly the six failure modes the task names. No code.

---

## 1. Failure Mode → Retry Behavior

| Failure mode | Retryable? | Max attempts | Backoff |
|---|---|---|---|
| **Network failure** (DNS resolution, connection refused) | Yes | 3 | Exponential, base 1s, jitter ±20% |
| **`429` (Too Many Requests)** | Yes | Unbounded by attempt count — bounded instead by [`RATE_LIMITING.md § 6`](RATE_LIMITING.md#6-interaction-with-retry)'s `Retry-After`-driven wait; this is a scheduling delay, not a failure being retried against the odds | Exactly the platform's declared `Retry-After`, never a guessed value when one is provided |
| **`500`/`502`/`503` (server error)** | Yes | 3 | Exponential, base 2s, jitter ±20% — longer base than network failure, since a server-side error is less likely to clear in the first second than a transient network blip |
| **Timeout** (connect or transfer, per [`DOWNLOAD_POLICY.md § 2`](DOWNLOAD_POLICY.md#2-timeout-policy)) | Yes | 3 | Exponential, base 1s |
| **Connection reset** | Yes | 3 | Exponential, base 1s |
| **Temporary ban** (sustained `403`/`429` beyond normal rate-limit recovery, or an explicit block signal) | Yes, but escalated | 1 immediate retry, then routed to a **connector-level circuit breaker** ([§3](#3-circuit-breaker)) rather than continued per-request retry | N/A past the first attempt — repeatedly retrying into an active ban is indistinguishable from ignoring it |

## 2. Exponential Backoff with Jitter

`delay = base_delay × 2^attempt_number × (1 ± jitter_fraction)`, capped at a maximum delay per failure mode — jitter exists specifically to prevent every worker retrying the same transiently-failed host from synchronizing into a new burst the instant the backoff window ends, a well-known failure mode of naive uniform backoff at any real concurrency level.

## 3. Circuit Breaker

Three consecutive failures against the same connector — regardless of failure mode — opens that connector's circuit: no further requests are attempted for a cooldown window, and every queued item for that connector is marked `deferred`, not `failed` (a deferred item re-enters the queue once the circuit closes; a failed item does not, per [`ERROR_HANDLING.md`](ERROR_HANDLING.md)'s categorization). This is the concrete mechanism behind [`KNOWLEDGE_PIPELINE.md § 2`](../knowledge-pipeline/KNOWLEDGE_PIPELINE.md#2-acquisition-stage-1-detail)'s previously-abstract "three consecutive failures... triggers a source-health flag" — this document is what actually implements that flag's trigger condition.

## 4. What Is Never Retried

Per [`ERROR_HANDLING.md § Permanent`](ERROR_HANDLING.md#2-permanent): a `404`, a `401`/`403` outside the temporary-ban pattern, a malformed request the framework itself constructed (a client-side bug, not a transient server condition), and anything already exhausted through [§1](#1-failure-mode--retry-behavior)'s max-attempts ceiling. Retrying a `404` on principle wastes budget on something no amount of waiting will fix — the retry policy's job is recovering from *transient* conditions, never masking a *permanent* one by trying again anyway.

## 5. Retry State Is Visible, Not Silent

Every retry attempt is logged with its attempt number and computed delay, per [`OBSERVABILITY.md`](OBSERVABILITY.md) — a connector silently retrying 3 times before eventually succeeding looks, from the outside, identical to one that succeeded on the first try, unless retry activity is itself an observable signal; a connector needing frequent retries against a source that's supposed to be healthy is exactly the kind of early warning [`KNOWLEDGE_REFRESH_POLICY.md § 5`](../knowledge-pipeline/KNOWLEDGE_REFRESH_POLICY.md#5-deprecation-and-retirement)'s "unreachable" flag should catch before three full consecutive-failure cycles are needed to notice.
