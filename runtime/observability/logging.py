"""Structured logging with correlation context.

Implements docs/runtime/LOGGING_AND_OBSERVABILITY.md §§1–2: every log entry
carries `correlation_id`, `pipeline_run_id`, and `module_id` where known, no
literal credential value or full document/response body is ever logged, and
the three correlation IDs are propagated via context variables rather than
threaded explicitly through every function call — the same mechanism that
lets a trace be followed across stage and module boundaries without each
one needing to know about the others.
"""

from __future__ import annotations

import contextvars
import json
import logging
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

from runtime.config.schema import is_credential_shaped_key

_correlation_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("correlation_id", default=None)
_pipeline_run_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("pipeline_run_id", default=None)
_module_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("module_id", default=None)

#: Never emitted, even if present as a logging `extra=` field — the same
#: credential-shape heuristic the Configuration System applies to config
#: keys (CONFIGURATION_SYSTEM.md §6), applied here to log fields too, per
#: LOGGING_AND_OBSERVABILITY.md §1's "no literal credential value" rule.
_REDACTED = "***REDACTED***"

#: Standard LogRecord attributes — everything else on a record is a
#: caller-supplied `extra=` field and belongs in the structured payload.
_STANDARD_RECORD_ATTRS = frozenset(logging.LogRecord("", 0, "", 0, "", None, None).__dict__.keys())


@contextmanager
def bind_correlation(
    *,
    correlation_id: str | None = None,
    pipeline_run_id: str | None = None,
    module_id: str | None = None,
) -> Iterator[None]:
    """Bind one or more correlation IDs for the duration of the `with` block.

    Per LOGGING_AND_OBSERVABILITY.md §2, these are three different questions:
    correlation_id identifies one unit of work, pipeline_run_id identifies
    one Pipeline Definition execution, and module_id identifies which module
    is currently doing the logging. Any not passed here keep whatever value
    (possibly None) an outer scope already bound — nesting narrows, it never
    clears an outer binding by omission.
    """

    tokens = []
    if correlation_id is not None:
        tokens.append((_correlation_id, _correlation_id.set(correlation_id)))
    if pipeline_run_id is not None:
        tokens.append((_pipeline_run_id, _pipeline_run_id.set(pipeline_run_id)))
    if module_id is not None:
        tokens.append((_module_id, _module_id.set(module_id)))
    try:
        yield
    finally:
        for var, token in tokens:
            var.reset(token)


def current_correlation_id() -> str | None:
    return _correlation_id.get()


def current_pipeline_run_id() -> str | None:
    return _pipeline_run_id.get()


def current_module_id() -> str | None:
    return _module_id.get()


class JSONLogFormatter(logging.Formatter):
    """Renders one log record as one JSON object per line.

    Automatically attaches the currently-bound correlation IDs and redacts
    any extra field whose name looks credential-shaped, so a caller cannot
    accidentally leak a secret into logs even if the Configuration System's
    own layer-level check (which only covers *configuration*, not arbitrary
    runtime log calls) never saw it.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        correlation_id = current_correlation_id()
        pipeline_run_id = current_pipeline_run_id()
        module_id = current_module_id()
        if correlation_id is not None:
            payload["correlation_id"] = correlation_id
        if pipeline_run_id is not None:
            payload["pipeline_run_id"] = pipeline_run_id
        if module_id is not None:
            payload["module_id"] = module_id

        for key, value in record.__dict__.items():
            if key in _STANDARD_RECORD_ATTRS or key in payload:
                continue
            payload[key] = _REDACTED if is_credential_shaped_key(key) else value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)


class TextLogFormatter(logging.Formatter):
    """A human-readable formatter for local/interactive use (`log_format: text`)."""

    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        context_bits = []
        if (cid := current_correlation_id()) is not None:
            context_bits.append(f"correlation_id={cid}")
        if (mid := current_module_id()) is not None:
            context_bits.append(f"module_id={mid}")
        if context_bits:
            return f"{base} [{' '.join(context_bits)}]"
        return base


def configure_logging(*, level: str = "INFO", log_format: str = "json") -> None:
    """Configure the root logger once, at Runtime boot.

    Idempotent: calling this more than once replaces the handler rather than
    accumulating duplicate handlers, so re-running boot in tests never
    produces duplicated log lines.
    """

    root = logging.getLogger()
    root.setLevel(level)
    for existing in list(root.handlers):
        root.removeHandler(existing)

    handler = logging.StreamHandler(stream=sys.stderr)
    if log_format == "json":
        handler.setFormatter(JSONLogFormatter())
    else:
        handler.setFormatter(TextLogFormatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
