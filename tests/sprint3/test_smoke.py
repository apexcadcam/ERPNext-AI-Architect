"""End-to-end smoke tests for Sprint 3, Phase 6.

Lightweight, no planner, no ERPNext, no external APIs — proving the pieces
Sprint 3 actually shipped start up cleanly together.

One honest limitation, discovered during this validation and deliberately
*not* patched (see the Phase 6 deliverables report — fixing it would touch
`runtime/boot.py`, and would require either special-casing a module by name
there, which `docs/runtime/MODULE_SYSTEM.md §1` forbids, or the dependency-
injection seam the Architecture Audit already named as future work, C2):
`Runtime.boot()` has no mechanism to set `IntegrationModule.
connector_search_paths` before `init()` runs, so booting the real Runtime
against the real `plugins/` directory starts the Integration module
healthy but with zero connectors discovered — `connector_search_paths`
defaults to `[]` and nothing in `runtime/` ever populates it. The two
halves below are therefore proven separately, exactly as Phases 3/4's own
tests already do: `Runtime.boot()` for the generic module lifecycle, and
`IntegrationModule` constructed and wired directly (mirroring
`tests/integration/test_module.py`'s own established pattern) for the
connector-discovery half.
"""

from __future__ import annotations

from pathlib import Path

from knowledge.artifacts import DependencyEdge
from knowledge.graph import GraphBuilder, InMemoryGraphStore

from integration import CAPABILITY_CONNECTOR_REGISTRY, IntegrationModule
from runtime.boot import Runtime
from runtime.container.di import Container
from runtime.lifecycle import RuntimeState
from runtime.modules.manifest import ModuleManifest
from tests.sprint3.conftest import CONNECTORS_DIR, PLUGINS_DIR, disable_modules, make_validated_knowledge_api


def test_runtime_starts_and_integration_module_initializes_healthy(config_dir: Path) -> None:
    # The real plugins/ directory also contains Sprint 2's extractor/
    # validator modules, which need their own knowledge-domain provider
    # capabilities registered to boot — orthogonal to what this Sprint 3
    # smoke test is validating, so they're disabled via the Configuration
    # System's own supported module-enablement override, scoping this test
    # to Integration alone without coupling it to Sprint 2's providers.
    disable_modules(config_dir, "extractor", "validator")
    runtime = Runtime(config_dir=config_dir, plugin_search_paths=[PLUGINS_DIR])

    info = runtime.boot()

    assert info.state is RuntimeState.READY
    assert "integration" in info.module_health
    assert info.module_health["integration"].healthy is True
    assert runtime.all_healthy()

    runtime.shutdown()
    assert runtime.state is RuntimeState.STOPPED


def test_integration_module_discovers_and_registers_the_filesystem_connector() -> None:
    manifest = ModuleManifest(
        module_id="integration",
        display_name="Integration",
        maintained_by="test-suite",
        version="0.1.0",
        capabilities_provided=(CAPABILITY_CONNECTOR_REGISTRY,),
        entry_point="module:create",
    )
    module = IntegrationModule(manifest)
    module.connector_search_paths = [CONNECTORS_DIR]
    container = Container()

    module.init(container)
    health = module.health_check()

    assert health.healthy is True
    registered = container.resolve(CAPABILITY_CONNECTOR_REGISTRY)
    assert registered.get("filesystem") is not None


def test_knowledge_graph_builds_and_traverses_successfully() -> None:
    store = InMemoryGraphStore()
    builder = GraphBuilder(store)
    builder.project(
        make_validated_knowledge_api(
            "KA-0001", dependencies=(DependencyEdge(target_id="KA-0002", reason="x"),)
        )
    )

    result = store.traverse(["KA-0001"], max_depth=1)

    assert [node.wraps for node in result] == ["KA-0001", "KA-0002"]


def test_no_unexpected_failure_running_every_piece_in_one_process(config_dir: Path, tmp_path: Path) -> None:
    """Everything Sprint 3 shipped, exercised back to back in one process,
    with no exception anywhere along the way.
    """

    disable_modules(config_dir, "extractor", "validator")
    runtime = Runtime(config_dir=config_dir, plugin_search_paths=[PLUGINS_DIR])
    info = runtime.boot()
    assert info.state is RuntimeState.READY
    runtime.shutdown()

    manifest = ModuleManifest(
        module_id="integration",
        display_name="Integration",
        maintained_by="test-suite",
        version="0.1.0",
        capabilities_provided=(CAPABILITY_CONNECTOR_REGISTRY,),
        entry_point="module:create",
    )
    module = IntegrationModule(manifest)
    module.connector_search_paths = [CONNECTORS_DIR]
    module.init(Container())
    connector = module.registry.instantiate("filesystem")
    connector.manifest = connector.manifest.model_copy(update={"endpoint_reference": str(tmp_path)})
    connector.connect()
    connector.write_text("proof.txt", "sprint 3 is done")  # type: ignore[attr-defined]
    assert connector.read_text("proof.txt") == "sprint 3 is done"  # type: ignore[attr-defined]

    store = InMemoryGraphStore()
    builder = GraphBuilder(store)
    builder.project(
        make_validated_knowledge_api(
            "KA-0001", dependencies=(DependencyEdge(target_id="KA-0002", reason="x"),)
        )
    )
    result = store.traverse(["KA-0001"], max_depth=1)
    assert [node.wraps for node in result] == ["KA-0001", "KA-0002"]
