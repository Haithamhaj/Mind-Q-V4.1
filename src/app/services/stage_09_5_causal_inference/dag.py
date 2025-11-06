from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, Tuple

from .config_loader import CausalConfig

try:  # pragma: no cover - optional dependency
    import graphviz  # type: ignore
except Exception:  # pragma: no cover - defensive
    graphviz = None  # type: ignore

try:  # pragma: no cover - optional dependency
    import networkx as nx  # type: ignore
except Exception:  # pragma: no cover - defensive
    nx = None  # type: ignore

try:  # pragma: no cover - optional dependency
    import matplotlib.pyplot as plt  # type: ignore
except Exception:  # pragma: no cover - defensive
    plt = None  # type: ignore


def _build_edges(config: CausalConfig) -> List[Tuple[str, str]]:
    edges: List[Tuple[str, str]] = []

    def _add_edges(pairs: Iterable[Tuple[str, str]]) -> None:
        for src, dst in pairs:
            if not src or not dst:
                continue
            edges.append((src, dst))

    common = config.common_causes or []
    if common:
        _add_edges((cause, config.treatment) for cause in common)
        _add_edges((cause, config.outcome) for cause in common)

    modifiers = config.effect_modifiers or []
    if modifiers:
        _add_edges((modifier, config.outcome) for modifier in modifiers)

    instruments = config.instrumental_variables or []
    if instruments:
        _add_edges((instrument, config.treatment) for instrument in instruments)

    frontdoor = config.frontdoor_variables or []
    if frontdoor:
        _add_edges((config.treatment, mediator) for mediator in frontdoor)
        _add_edges((mediator, config.outcome) for mediator in frontdoor)

    _add_edges([(config.treatment, config.outcome)])
    return edges


def build_and_export(config: CausalConfig, output_dir: Path) -> Dict[str, str]:
    """Render the causal DAG to disk using Graphviz when available, otherwise networkx."""
    output_dir.mkdir(parents=True, exist_ok=True)
    edges = _build_edges(config)
    artifact_paths: Dict[str, str] = {}

    if graphviz is not None:  # pragma: no cover - rendering verified in integration tests
        try:
            dot = graphviz.Digraph(name="causal_dag", format="png")
            dot.attr(rankdir="LR")
            nodes = {config.treatment, config.outcome, *config.common_causes, *config.effect_modifiers}
            nodes.update(config.instrumental_variables)
            nodes.update(config.frontdoor_variables)
            for node in nodes:
                dot.node(node)
            for src, dst in edges:
                dot.edge(src, dst)

            render_base = output_dir / "causal_dag"
            png_path = dot.render(filename=str(render_base), cleanup=True)
            artifact_paths["png"] = png_path

            dot.format = "svg"
            svg_path = dot.render(filename=str(render_base), cleanup=True)
            artifact_paths["svg"] = svg_path
            dot.format = "png"
            return artifact_paths
        except Exception:
            pass  # fallback to networkx

    if nx is None or plt is None:
        raise RuntimeError("Graphviz and networkx/matplotlib are unavailable for DAG rendering")

    graph = nx.DiGraph()
    graph.add_nodes_from(
        {config.treatment, config.outcome, *config.common_causes, *config.effect_modifiers}
    )
    graph.add_nodes_from(config.instrumental_variables)
    graph.add_nodes_from(config.frontdoor_variables)
    graph.add_edges_from(edges)

    plt.figure(figsize=(8, 5))
    pos = nx.spring_layout(graph, seed=42)
    nx.draw_networkx(graph, pos, with_labels=True, node_color="#f0f4ff", node_size=1500, arrowsize=20)
    png_path = output_dir / "causal_dag.png"
    plt.tight_layout()
    plt.savefig(png_path.as_posix(), format="png")
    plt.close()
    artifact_paths["png"] = png_path.as_posix()
    return artifact_paths
