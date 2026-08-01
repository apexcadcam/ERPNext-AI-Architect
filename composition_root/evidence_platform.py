"""The Evidence Platform's Composition Root — Evidence Platform CLI
Architecture Specification v1.1 §5.

Three thin functions that wire pieces which already exist: an engine's own
public entry point, plus the matching persistence function. No new
orchestration concept, no state, no logic of its own. Every arithmetic
decision stays inside `evidence` and `aggregation` where it is already
tested; this module only decides *what to call in what order*.

**Why this is a separate module from `root.py`.** `root.py` is Sprint 13's
Requirements -> Execution composition and is untouched by this Sprint. The
Evidence Platform is a different lineage with a different chain
(Extraction -> Aggregation), so it gets its own file rather than accreting
onto an unrelated one.

**Why `composition_root/__init__.py` does not re-export these.** If it
did, `import composition_root` — which `runtime/cli.py` already does at
module scope for `run_goal` — would transitively import `evidence` and
`aggregation` on *every* invocation, including `architect doctor`. The
Runtime would then load two leaf capabilities it has no use for, and the
"importing a frozen package never transitively imports evidence" boundary
test would stop being true. Instead, `runtime/cli.py` imports this module
lazily inside the three commands that need it — the same pattern
`plugins list` and `config validate` already use for `PluginRegistry` and
`ConfigLoader`. The boundary exception is therefore confined to this one
file, and confined to import-time-on-demand.

**The sanctioned-consumer exception this file creates, stated plainly.**
`composition_root` is listed in `_FROZEN_PACKAGE_DIRS` in both
`tests/evidence/test_architecture_boundaries.py` and
`tests/aggregation/test_architecture_boundaries.py`, each asserting that
no frozen package imports the engine. This file is a named, disclosed,
narrow exception to those two assertions — exactly what Sprint 14 did when
it made `runtime/cli.py` a sanctioned consumer of `composition_root`. Both
test files are updated in place to name this file specifically; neither
assertion is weakened for any other file.

**What does not change.** `evidence` and `aggregation` still import
nothing from each other's engines, still import no Repository Intelligence
package, and still import nothing from `composition_root`. The chain stays
one-directional: Extraction -> Aggregation.
"""

from __future__ import annotations

from pathlib import Path

from aggregation.contract import AggregationRequest, PatternSet
from aggregation.engine import MIN_OCCURRENCES_THRESHOLD, aggregate_patterns
from aggregation.errors import AggregationError_
from aggregation.persistence import read_pattern_set, write_pattern_set

from evidence.contract import CanonicalRepository, EvidenceExtractionRequest, EvidenceSet
from evidence.engine import extract_evidence
from evidence.errors import EvidenceError_
from evidence.persistence import read_evidence_set, write_evidence_set

#: The canonical repository names a caller may pass, as plain strings.
#:
#: Exposed here so `runtime/cli.py` can name the valid choices in its own
#: `--help` and error text without importing `evidence.contract` to reach
#: the enum -- §2's boundary decision, honoured literally: the CLI holds
#: no engine import at all.
CANONICAL_REPOSITORY_NAMES: tuple[str, ...] = tuple(repository.value for repository in CanonicalRepository)

#: The two exception types a caller must be prepared to catch, exposed for
#: the same reason as the names above: `runtime/cli.py` maps them to an
#: exit code (§7) and cannot import `evidence.errors` or
#: `aggregation.errors` to name them.
EVIDENCE_PLATFORM_ERRORS: tuple[type[Exception], ...] = (EvidenceError_, AggregationError_)

#: The registered minimum-occurrence threshold, as a plain int.
#:
#: Exposed so `architect patterns aggregate` defaults to the *registry's*
#: value rather than repeating `2` in the CLI. The registry entry carries
#: its own justification and `calibration_status`; a number copied into a
#: command's signature would carry neither, and would silently stop
#: tracking the registry the day it is recalibrated.
DEFAULT_MIN_OCCURRENCES: int = MIN_OCCURRENCES_THRESHOLD.value


def extract_repository_evidence(
    *,
    repository: str,
    source_root: str,
    version: str,
    commit: str,
    correlation_id: str,
    requested_by: str,
    max_files: int,
    timeout_seconds: float,
    evidence_path: Path,
    meta_path: Path,
) -> EvidenceSet:
    """Run Evidence Extraction for one repository and persist the result.

    **Takes primitives, not an `EvidenceExtractionRequest`.** §5 specified
    a request-shaped parameter, but that would oblige the caller to build
    the request -- which means importing `evidence.contract` -- and
    `runtime/cli.py` is precisely the caller. §2 already settled that the
    CLI reaches the platform *only* through this module, so the request is
    constructed here instead. `CanonicalRepository(repository)` raises
    `ValueError` on an unknown name, which the CLI reports as a validation
    failure.

    Returns the `EvidenceSet` as well as writing it, so a caller renders
    exactly the object that was persisted rather than re-reading it and
    hoping the two agree.
    """

    request = EvidenceExtractionRequest(
        repository=CanonicalRepository(repository),
        source_root=source_root,
        version=version,
        commit=commit,
        correlation_id=correlation_id,
        requested_by=requested_by,
        max_files=max_files,
        timeout_seconds=timeout_seconds,
    )
    evidence_set = extract_evidence(request)
    write_evidence_set(evidence_set, evidence_path, meta_path)
    return evidence_set


def aggregate_repository_patterns(
    *,
    evidence_path: Path,
    meta_path: Path,
    patterns_path: Path,
    pattern_meta_path: Path,
    min_occurrences: int,
    correlation_id: str,
    requested_by: str,
    supporting_paths: tuple[tuple[Path, Path], ...] = (),
) -> PatternSet:
    """Read a persisted `EvidenceSet`, aggregate it, and persist the
    resulting `PatternSet`.

    Extraction is never re-run here: the Aggregation Engine consumes
    persisted Evidence only, and this function honours that by reading the
    artifact rather than reaching for a source tree.

    `supporting_paths` carries `(evidence_path, meta_path)` pairs for
    corpora that supply **inheritance-resolution context only** — never an
    occurrence, never population membership, never a `Pattern` of their
    own (Inheritance Resolution §5.2). They are taken as *paths* rather
    than `EvidenceSet`s for the same reason the subject is: reading them
    is this layer's job, so `runtime/cli.py` never handles an engine type.

    Defaults to empty, so a single-corpus call is byte-for-byte what it
    was before this parameter existed.
    """

    evidence_set = read_evidence_set(evidence_path, meta_path)
    request = AggregationRequest(
        evidence_set=evidence_set,
        supporting_evidence_sets=tuple(
            read_evidence_set(supporting_evidence, supporting_meta)
            for supporting_evidence, supporting_meta in supporting_paths
        ),
        min_occurrences=min_occurrences,
        correlation_id=correlation_id,
        requested_by=requested_by,
    )
    pattern_set = aggregate_patterns(request)
    write_pattern_set(pattern_set, patterns_path, pattern_meta_path)
    return pattern_set


def read_repository_patterns(*, patterns_path: Path, pattern_meta_path: Path) -> PatternSet:
    """Read an already-persisted `PatternSet`. Runs no engine.

    **A third function where §5 specified two.** `architect patterns report`
    is read-only, but §2's boundary decision says `runtime/cli.py` reaches
    the Evidence Platform *only* through the Composition Root. Without this
    function the report command would have to import
    `aggregation.persistence` directly, which is precisely the coupling §2
    rejected. Adding one more thin pass-through here is the smaller cost.
    """

    return read_pattern_set(patterns_path, pattern_meta_path)
