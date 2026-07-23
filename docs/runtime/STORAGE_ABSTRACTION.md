# STORAGE ABSTRACTION

**Status:** Foundational — Architecture Only, Not Implemented
**Authority:** Subordinate to [RUNTIME_ARCHITECTURE.md § 4.3](RUNTIME_ARCHITECTURE.md#43-storage_layoutmds-deferred-storage-product-choice). The interface layer beneath [`docs/crawler/STORAGE_LAYOUT.md`](../crawler/STORAGE_LAYOUT.md)'s logical zones, whose physical backend that document explicitly deferred.
**Scope:** A backend-agnostic adapter contract. No storage-product choice, no code.

---

## 1. Namespaces, Not Paths

Every module that persists or reads content addresses it by **logical namespace + key**, never by a filesystem path, an S3 bucket name, or a database table — `STORAGE_LAYOUT.md § 1`'s three zones (`raw`, `documents`, `cache`) *are* the namespaces this document formalizes as the abstraction's addressing scheme. A module calling `storage.write(namespace="raw", key=content_hash, bytes=...)` has no way to know, and no need to know, whether that resolves to a local disk, an S3 object, or a database blob column — resolution happens entirely inside the configured Adapter.

## 2. The Adapter Contract

Every Storage Adapter implements the same fixed operation set: `read(namespace, key)`, `write(namespace, key, bytes, metadata)`, `exists(namespace, key)`, `list(namespace, prefix)`, `delete(namespace, key)`, `content_hash(namespace, key)`. `write` is required to be idempotent for identical `(namespace, key, bytes)` — a second write of unchanged content is a no-op, per [`CRAWLER_PIPELINE.md § 8`](../crawler/CRAWLER_PIPELINE.md#8-persist-raw-document)'s existing idempotent-write requirement, now stated as an Adapter contract obligation rather than an assumption any given backend happens to satisfy.

**`delete` exists in the contract but is never called by any module specified so far** — every document in this project's architecture (Traceability, [`STORAGE_LAYOUT.md § 4`](../crawler/STORAGE_LAYOUT.md#4-retention)'s retention rule, [`PIPELINE_ENGINE.md § 6`](PIPELINE_ENGINE.md#6-rollback)'s rollback-never-deletes rule) treats `raw/` and `documents/` as permanent. `delete` is included only because [`STORAGE_LAYOUT.md § 1`](../crawler/STORAGE_LAYOUT.md#1-three-zones-three-different-durability-guarantees)'s `cache/` zone is explicitly expendable — the only namespace any module is expected to ever call `delete` against.

## 3. Adapter Selection Is Configuration

Which Adapter serves which namespace is a [`CONFIGURATION_SYSTEM.md § 2`](CONFIGURATION_SYSTEM.md#2-the-six-layers) Global-or-Environment-layer setting — e.g., `cache` on local disk everywhere, `raw`/`documents` on local disk in `dev` but on an object store in `production`, resolved once at [`RUNTIME_BOOT_SEQUENCE.md § 4`](RUNTIME_BOOT_SEQUENCE.md#4-configuration-loading) and injected into every module needing storage access via the [Dependency Injection Container](DEPENDENCY_INJECTION.md#1-the-one-rule), never chosen by a module's own code.

## 4. Content Addressing Survives Backend Changes

Because [`STORAGE_LAYOUT.md § 2`](../crawler/STORAGE_LAYOUT.md#2-path-structure)'s content-hash-based keys are backend-agnostic by construction (a hash is a hash regardless of what stores the bytes behind it), migrating a namespace from one Adapter to another — local disk to object storage, for a future cloud deployment — never requires renaming or re-deriving a single key; only the Adapter resolving that namespace changes, per [§3](#3-adapter-selection-is-configuration). This is the concrete mechanism behind [`RUNTIME_ARCHITECTURE.md § 7`](RUNTIME_ARCHITECTURE.md#7-non-functional-requirements-at-scale)'s "future cloud deployment... without redesign."

## 5. Multi-Backend Consistency

A single logical write (e.g., Persist writing a `Knowledge Document`'s envelope, normalized text, and structural metadata as related files under one `documents/<id>/` key prefix) may span multiple underlying objects at the Adapter level — the abstraction guarantees each individual `write` call is atomic, but a caller needing multiple related writes to succeed or fail together is responsible for sequencing them and handling partial-failure via [`PIPELINE_ENGINE.md § 6`](PIPELINE_ENGINE.md#6-rollback)'s compensating-action mechanism, not by expecting the Storage Abstraction itself to provide multi-object transactions no backend in [§3](#3-adapter-selection-is-configuration)'s candidate set (filesystem, S3, database, object storage) uniformly supports.

## 6. Testability

Per [`DEPENDENCY_INJECTION.md § 4`](DEPENDENCY_INJECTION.md#4-test-doubles): an in-memory Adapter satisfying the identical [§2](#2-the-adapter-contract) contract is a valid substitute for any real backend in tests — no module's own logic needs a different code path to be testable versus production-configured, since both look identical at the point the module calls `storage.read`/`storage.write`.
