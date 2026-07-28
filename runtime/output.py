"""The `architect` CLI's Output Contract.

Implements Evidence Platform CLI Architecture Specification v1.1 §6: every
command emits the same six sections, in the same order, always -- including
the empty ones. A reader never has to wonder whether a section was omitted
or genuinely empty, and a script never has to branch on a key's presence.

Two properties are structural here rather than conventional:

1. **Both output modes come from one object.** `render_human` and
   `render_json` are two views of the same `CommandOutput`, so
   CLI_ARCHITECTURE.md §4's rule that `--json` never diverges from the
   human render stops being something an author has to remember and
   becomes something the type makes true.
2. **A failing command still emits all six sections.** An error populates
   `errors` and sets `exit_code`; it does not replace the output with a
   bare message. Tooling parses success and failure identically.

**This module carries strings only.** It imports nothing from `evidence`,
`aggregation`, or any other engine -- deliberately, so the Output Contract
can live inside the Runtime package without creating a dependency on a
leaf capability. Commands convert their engine types to strings; this
module never learns what those types are.
"""

from __future__ import annotations

import json as json_module

import typer
from pydantic import BaseModel, ConfigDict, Field, field_validator

#: The six sections, in the one order every command emits them (§6). Both
#: renderers iterate this, so neither can grow, drop, or reorder a section
#: without the other doing the same.
SECTION_ORDER = (
    "summary",
    "artifacts_written",
    "warnings",
    "skipped",
    "errors",
)

#: Rendered in place of an empty section, so "absent" and "empty" are
#: never confusable in the human view.
EMPTY_SECTION_MARKER = "(none)"


class CommandOutput(BaseModel):
    """One command invocation's complete output, mode-independent.

    Frozen and `extra="forbid"`, like every other contract in this project
    (`evidence.contract.EvidenceSet`, `aggregation.contract.PatternSet`,
    ...). A command builds exactly one of these and renders it; it never
    prints directly.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    #: Ordered label/value pairs. A tuple of pairs rather than a mapping
    #: because display order is part of the contract and must survive a
    #: round trip through the model unchanged.
    summary: tuple[tuple[str, str], ...] = ()
    artifacts_written: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    #: Where `aggregation.contract.SkippedAggregation` surfaces. A
    #: first-class section, not an afterthought: the platform's declared
    #: gaps stay visible at the terminal, matching the decision that made
    #: them a persisted result rather than a log line.
    skipped: tuple[str, ...] = ()

    errors: tuple[str, ...] = ()

    #: `runtime.cli.EXIT_OK` / `EXIT_VALIDATION_FAILED` /
    #: `EXIT_INTERNAL_ERROR`. Bounded by what a POSIX shell can actually
    #: report, not left as an unconstrained int.
    exit_code: int = Field(ge=0, le=255)

    @field_validator("summary")
    @classmethod
    def _summary_labels_are_present_and_unique(
        cls, value: tuple[tuple[str, str], ...]
    ) -> tuple[tuple[str, str], ...]:
        # Uniqueness is not cosmetic: `render_json` keys the summary by
        # label, so a duplicate label would silently drop a row from the
        # JSON view while the human view still showed both -- exactly the
        # divergence between modes this contract exists to prevent.
        labels = [label for label, _ in value]
        if any(not label.strip() for label in labels):
            raise ValueError("every summary label must be non-empty")
        if len(set(labels)) != len(labels):
            duplicates = sorted({label for label in labels if labels.count(label) > 1})
            raise ValueError(f"summary labels must be unique; duplicated: {', '.join(duplicates)}")
        return value

    @field_validator("artifacts_written", "warnings", "skipped", "errors")
    @classmethod
    def _entries_are_non_empty(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not entry.strip() for entry in value):
            raise ValueError("a section entry must be non-empty; omit it instead of emitting a blank line")
        return value


def _render_summary_lines(summary: tuple[tuple[str, str], ...]) -> list[str]:
    if not summary:
        return [f"  {EMPTY_SECTION_MARKER}"]
    label_width = max(len(label) for label, _ in summary)
    value_width = max(len(value) for _, value in summary)
    return [f"  {label.ljust(label_width)}  {value.rjust(value_width)}" for label, value in summary]


def _render_entry_lines(entries: tuple[str, ...]) -> list[str]:
    if not entries:
        return [f"  {EMPTY_SECTION_MARKER}"]
    return [f"  {entry}" for entry in entries]


def render_human(output: CommandOutput) -> str:
    """The human-readable render: every section, always, in `SECTION_ORDER`.

    Section headings are uppercase and unindented; entries are indented two
    spaces. Summary values are right-aligned into a common column so digits
    line up when a reader scans them.
    """

    lines: list[str] = []
    for section in SECTION_ORDER:
        lines.append(section.upper().replace("_", " "))
        if section == "summary":
            lines.extend(_render_summary_lines(output.summary))
        else:
            lines.extend(_render_entry_lines(getattr(output, section)))
        lines.append("")
    lines.append(f"exit: {output.exit_code}")
    return "\n".join(lines)


def render_json(output: CommandOutput) -> dict[str, object]:
    """The machine-readable render: the same six keys plus `exit_code`,
    always present, never conditionally omitted.

    Built from the same `CommandOutput` the human render reads, which is
    what keeps the two from diverging.
    """

    payload: dict[str, object] = {"summary": {label: value for label, value in output.summary}}
    for section in SECTION_ORDER[1:]:
        payload[section] = list(getattr(output, section))
    payload["exit_code"] = output.exit_code
    return payload


def emit_command_output(output: CommandOutput, *, as_json: bool) -> None:
    """Write `output` to stdout in the requested mode.

    The single place a command's result reaches the terminal. Commands call
    this and then exit with `output.exit_code`; they never call
    `typer.echo` with their own formatting.
    """

    if as_json:
        typer.echo(json_module.dumps(render_json(output), indent=2))
    else:
        typer.echo(render_human(output))
