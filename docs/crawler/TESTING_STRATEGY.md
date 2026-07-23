# TESTING STRATEGY

**Status:** Foundational — Architecture Only, Not Implemented
**Authority:** Subordinate to [CRAWLER_ARCHITECTURE.md](CRAWLER_ARCHITECTURE.md). What makes the "Testable" non-functional requirement ([`CRAWLER_ARCHITECTURE.md § 3`](CRAWLER_ARCHITECTURE.md#3-non-functional-requirements-and-where-each-is-addressed)) concrete.
**Scope:** Five test types, what each verifies, and the fixture strategy that keeps all of them fast and independent of live sources. No code.

---

## 1. Connector Tests

**Verify:** a connector satisfies [`SOURCE_CONNECTOR_SPEC.md`](SOURCE_CONNECTOR_SPEC.md)'s ten required declarations — a contract-compliance check, not a check that the connector successfully crawls anything live.
**Fixture strategy:** none needed against live sources at all — this test type only inspects the connector's *declaration*, which is why it can run in milliseconds, in every CI run, for every one of what may eventually be hundreds of connectors.
**Fails the build when:** a required declaration is missing, or a declared value violates a hard rule (e.g., `respects_robots_txt: false` on a documentation-site-type connector, per [`SOURCE_CONNECTOR_SPEC.md § 1.5`](SOURCE_CONNECTOR_SPEC.md#15-crawling-policy)).

## 2. Parser Tests

**Verify:** [`PARSER_SPEC.md § 4`](PARSER_SPEC.md#4-determinism-requirement)'s determinism guarantee, via **golden-file testing** — a fixed set of representative input documents per content-type, each paired with its known-correct `structural_metadata` output, checked into the test suite once and re-verified byte-for-byte on every change to that parser.
**Fixture strategy:** recorded real documents (a real HTML page, a real API JSON payload), captured once, never re-fetched live during test runs — a parser test that hits the network is not a parser test, it's an accidental integration test, and this distinction is enforced structurally by fixture design, not by convention alone.
**Fails the build when:** any golden-file output changes without the change being an intentional, reviewed parser-version bump per [`VERSIONING_POLICY.md § 1`](VERSIONING_POLICY.md#1-component-versioning-the-frameworks-own) — an *unintentional* golden-file diff is exactly what this test type exists to catch before it reaches production and silently reshapes every document of that content-type.

## 3. Pipeline Tests

**Verify:** [`CRAWLER_PIPELINE.md § 0`](CRAWLER_PIPELINE.md#0-the-crawl-item--one-contract-nine-consumers)'s stage-contract discipline — that each stage reads only the fields it's entitled to and writes only the fields it owns, and that a Crawl Item failing at stage N is retained with the correct [`ERROR_HANDLING.md`](ERROR_HANDLING.md) category and never silently reaches stage N+1.
**Fixture strategy:** synthetic Crawl Items constructed directly at whatever stage boundary is under test (a Pipeline Test for the Persist stage does not need to run Discover through Parse first — it constructs a valid post-Parse item directly), keeping each stage's tests independent of every other stage's correctness, which is the whole point of the fixed-contract design in the first place.
**Fails the build when:** a stage reads a field it wasn't declared to depend on (a coupling violation, caught by contract inspection, not just by behavior) or mishandles a failure category incorrectly.

## 4. Integration Tests

**Verify:** an entire connector, end to end, against a **recorded** real interaction (a full HTTP/API session captured once from the real source and replayed deterministically) — this is the only test type permitted to exercise all nine [`CRAWLER_PIPELINE.md`](CRAWLER_PIPELINE.md) stages together, and even then, never against a live network call during normal test runs.
**Fixture strategy:** a per-connector recorded-session fixture ("cassette"), refreshed deliberately and infrequently (not on every run) against the real source to catch genuine upstream API/format drift — refreshing this fixture is itself a reviewed, deliberate action, distinct from ordinary test execution, so that a live source's transient unavailability never makes the test suite flaky.
**Fails the build when:** the recorded session, replayed, does not produce a valid, schema-compliant `Knowledge Document`.

## 5. Regression Tests

**Verify:** that a change to shared `core/` code ([`CRAWLER_PLUGIN_SYSTEM.md § 1`](CRAWLER_PLUGIN_SYSTEM.md#1-one-folder-one-source-zero-shared-code-edits)) does not silently alter the output of **every existing connector** — run as the full suite of every connector's [§4](#4-integration-tests) fixtures together, specifically triggered whenever `core/` changes (pipeline stages, shared Download/Retry/Cache logic), since that shared code is exactly where a change has blast radius across all connectors simultaneously, unlike a single connector's own, isolated change.
**Fails the build when:** any connector's previously-passing integration fixture now produces a different `Knowledge Document` shape or content than its own recorded baseline — the same "no silent reshaping" discipline as [§2](#2-parser-tests)'s golden files, applied at the whole-connector level instead of the single-parser level.

---

## 6. Why No Test Type Ever Hits a Live Source During Normal Runs

Every one of the five types above is deliberately designed to run against fixtures, not live network calls, for two compounding reasons: **determinism** (a test suite whose pass/fail depends on a real source's current uptime is not testing this framework, it's testing the internet), and **politeness** (a CI system running the test suite dozens of times a day must never itself become a load pattern indistinguishable from the abusive crawling behavior [`DOWNLOAD_POLICY.md`](DOWNLOAD_POLICY.md) and [`RATE_LIMITING.md`](RATE_LIMITING.md) exist to prevent). The only place a live call is ever deliberately made is [§4](#4-integration-tests)'s occasional, reviewed fixture-refresh — an explicit, rare, human-triggered action, never an automatic part of the regular test cycle.
