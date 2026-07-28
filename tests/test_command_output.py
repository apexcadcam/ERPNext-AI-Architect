"""Tests for the CLI Output Contract (Evidence Platform CLI Architecture
Specification v1.1 §6).

The conformance assertions here -- all six sections present, in order, in
both modes, including empty ones and including on the failure path -- are
the ones every command added in Commits 3-5 must keep passing. They are
written once, here, against the contract itself rather than against any
one command, so a new command cannot quietly opt out of them.
"""

from __future__ import annotations

import json

import pytest
import typer
from pydantic import ValidationError
from typer.testing import CliRunner

from runtime.output import (
    EMPTY_SECTION_MARKER,
    SECTION_ORDER,
    CommandOutput,
    emit_command_output,
    render_human,
    render_json,
)

runner = CliRunner()


def _full_output() -> CommandOutput:
    """One output with every section populated -- the shape
    `architect evidence extract` will produce.
    """

    return CommandOutput(
        summary=(("files examined", "46296"), ("evidence extracted", "812")),
        artifacts_written=(
            "evidence-data/frappe-v15.103.1.evidence.jsonl",
            "evidence-data/frappe-v15.103.1.meta.json",
        ),
        warnings=("2 files exceeded the size limit and were truncated",),
        skipped=("controller_lifecycle_hook — no derivable population (237 records present)",),
        errors=(),
        exit_code=0,
    )


# -- Section presence and order, in both modes ---------------------------------------------------------


def test_section_order_is_the_specified_six() -> None:
    assert SECTION_ORDER == ("summary", "artifacts_written", "warnings", "skipped", "errors")


def test_human_render_emits_every_section_even_when_all_are_empty() -> None:
    render = render_human(CommandOutput(exit_code=0))
    for section in SECTION_ORDER:
        assert section.upper().replace("_", " ") in render
    # Empty is rendered, not omitted -- one marker per section.
    assert render.count(EMPTY_SECTION_MARKER) == len(SECTION_ORDER)


def test_human_render_keeps_sections_in_the_contract_order() -> None:
    render = render_human(_full_output())
    positions = [render.index(section.upper().replace("_", " ")) for section in SECTION_ORDER]
    assert positions == sorted(positions)


def test_json_render_emits_every_key_even_when_all_are_empty() -> None:
    payload = render_json(CommandOutput(exit_code=0))
    assert list(payload) == [*SECTION_ORDER, "exit_code"]
    assert payload["summary"] == {}
    for section in SECTION_ORDER[1:]:
        assert payload[section] == []


def test_json_render_keys_are_ordered_exactly_like_the_human_sections() -> None:
    payload = render_json(_full_output())
    assert list(payload)[:-1] == list(SECTION_ORDER)


def test_json_render_never_omits_an_empty_section_from_a_populated_output() -> None:
    # `errors` is empty while everything else is populated: the key must
    # still be there, so a consumer can read it unconditionally.
    payload = render_json(_full_output())
    assert payload["errors"] == []
    assert payload["warnings"] != []


# -- The two modes carry the same facts ------------------------------------------------------------------


def test_both_modes_report_the_same_underlying_values() -> None:
    output = _full_output()
    human = render_human(output)
    payload = render_json(output)

    assert payload["summary"] == {"files examined": "46296", "evidence extracted": "812"}
    for label, value in output.summary:
        assert label in human
        assert value in human
    for section in SECTION_ORDER[1:]:
        rendered = payload[section]
        assert isinstance(rendered, list)
        for entry in getattr(output, section):
            assert entry in human
            assert entry in rendered


def test_exit_code_appears_in_both_modes() -> None:
    output = _full_output().model_copy(update={"exit_code": 1})
    assert render_human(output).endswith("exit: 1")
    assert render_json(output)["exit_code"] == 1


# -- The failure path still emits the full contract -------------------------------------------------------


def test_a_failing_output_still_emits_all_six_sections_in_both_modes() -> None:
    failure = CommandOutput(
        errors=("Source root does not exist: /nope",),
        exit_code=1,
    )

    human = render_human(failure)
    for section in SECTION_ORDER:
        assert section.upper().replace("_", " ") in human
    assert "Source root does not exist: /nope" in human
    assert human.endswith("exit: 1")

    payload = render_json(failure)
    assert list(payload) == [*SECTION_ORDER, "exit_code"]
    assert payload["errors"] == ["Source root does not exist: /nope"]
    assert payload["summary"] == {}
    assert payload["exit_code"] == 1


# -- Skipped is a first-class section ----------------------------------------------------------------------


def test_skipped_entries_are_rendered_not_hidden() -> None:
    skip = "controller_lifecycle_hook — no derivable population (237 records present)"
    output = CommandOutput(skipped=(skip,), exit_code=0)
    assert skip in render_human(output)
    assert render_json(output)["skipped"] == [skip]


def test_skipped_does_not_by_itself_make_a_command_fail() -> None:
    # A declared gap is a reported result, not an error -- the same
    # decision that made SkippedAggregation a persisted field.
    output = CommandOutput(skipped=("category — no derivable population",), exit_code=0)
    assert output.exit_code == 0
    assert render_json(output)["errors"] == []


# -- Human render formatting -------------------------------------------------------------------------------


def test_summary_labels_and_values_are_column_aligned() -> None:
    render = render_human(
        CommandOutput(summary=(("files examined", "46296"), ("evidence extracted", "812")), exit_code=0)
    )
    lines = [line for line in render.splitlines() if "examined" in line or "extracted" in line]
    assert len(lines) == 2
    # Values are right-aligned into one column: both lines end at the same width.
    assert len({len(line) for line in lines}) == 1


def test_a_long_text_value_does_not_push_the_numbers_out_of_their_column() -> None:
    # Found by rendering a real extraction: aligning every value to the
    # widest one sent the counts hundreds of columns right the moment a
    # filesystem path shared the section. Numbers align among themselves;
    # text starts where the label column ends.
    render = render_human(
        CommandOutput(
            summary=(
                ("source root", "/home/gaber/frappe-bench/apps/erpnext"),
                ("files examined", "2"),
                ("evidence extracted", "13"),
            ),
            exit_code=0,
        )
    )
    assert "  source root         /home/gaber/frappe-bench/apps/erpnext" in render
    assert "  files examined       2" in render
    assert "  evidence extracted  13" in render


def test_single_summary_row_renders_without_padding_error() -> None:
    render = render_human(CommandOutput(summary=(("patterns produced", "8"),), exit_code=0))
    assert "  patterns produced  8" in render


def test_section_headings_are_uppercase_and_unindented() -> None:
    render = render_human(_full_output())
    assert "ARTIFACTS WRITTEN" in render
    assert "\nSKIPPED\n" in render


# -- Contract shape ------------------------------------------------------------------------------------------


def test_command_output_is_frozen() -> None:
    output = _full_output()
    with pytest.raises(ValidationError):
        output.warnings = ()


def test_command_output_forbids_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        CommandOutput(exit_code=0, notes=("nope",))  # type: ignore[call-arg]


def test_every_section_defaults_to_empty_so_only_exit_code_is_required() -> None:
    output = CommandOutput(exit_code=0)
    assert output.summary == ()
    for section in SECTION_ORDER[1:]:
        assert getattr(output, section) == ()


def test_command_output_carries_no_engine_type() -> None:
    # §6: strings only. The moment a field is typed as an engine model,
    # `runtime` gains a dependency on a leaf capability.
    annotations = {name: str(field.annotation) for name, field in CommandOutput.model_fields.items()}
    for annotation in annotations.values():
        for package in ("evidence", "aggregation", "discovery", "synthesis", "evaluation", "recommendation"):
            assert package not in annotation


@pytest.mark.parametrize("exit_code", [-1, 256])
def test_exit_code_is_bounded_to_what_a_shell_can_report(exit_code: int) -> None:
    with pytest.raises(ValidationError):
        CommandOutput(exit_code=exit_code)


def test_duplicate_summary_labels_are_rejected() -> None:
    # A duplicate would survive the human render but collapse in the JSON
    # object -- the exact divergence between modes the contract prevents.
    with pytest.raises(ValidationError, match="unique"):
        CommandOutput(summary=(("files", "1"), ("files", "2")), exit_code=0)


def test_blank_summary_label_is_rejected() -> None:
    with pytest.raises(ValidationError, match="non-empty"):
        CommandOutput(summary=(("   ", "1"),), exit_code=0)


@pytest.mark.parametrize("section", ["artifacts_written", "warnings", "skipped", "errors"])
def test_blank_section_entry_is_rejected(section: str) -> None:
    with pytest.raises(ValidationError, match="non-empty"):
        CommandOutput.model_validate({section: ("",), "exit_code": 0})


# -- emit_command_output ----------------------------------------------------------------------------------


def _emitting_app(output: CommandOutput) -> typer.Typer:
    emitter = typer.Typer()

    @emitter.command()
    def run(json: bool = False) -> None:
        emit_command_output(output, as_json=json)
        raise typer.Exit(output.exit_code)

    return emitter


def test_emit_writes_the_human_render_by_default() -> None:
    result = runner.invoke(_emitting_app(_full_output()), [])
    assert result.exit_code == 0
    assert result.stdout.strip() == render_human(_full_output())


def test_emit_writes_parseable_json_on_stdout_when_asked() -> None:
    result = runner.invoke(_emitting_app(_full_output()), ["--json"])
    assert result.exit_code == 0
    assert json.loads(result.stdout) == render_json(_full_output())


def test_emit_carries_a_failing_exit_code_through_to_the_process() -> None:
    failure = CommandOutput(errors=("boom",), exit_code=1)
    result = runner.invoke(_emitting_app(failure), ["--json"])
    assert result.exit_code == 1
    assert json.loads(result.stdout)["errors"] == ["boom"]
