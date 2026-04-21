# visualisation/graph_view.py

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import networkx as nx
from core.models import Task, Status


# ------------------------------------------------------------------
# Colour scheme — one colour per task status
# ------------------------------------------------------------------

STATUS_COLOURS = {
    Status.PENDING:     "#B4B2A9",   # gray       — blocked, waiting on deps
    Status.READY:       "#378ADD",   # blue       — in queue, ready to run
    Status.IN_PROGRESS: "#EF9F27",   # amber      — currently being worked on
    Status.DONE:        "#1D9E75",   # teal/green — completed successfully
    Status.DELAYED:     "#D85A30",   # coral      — past deadline
    Status.CANCELLED:   "#E24B4A",   # red        — killed via admin API
}

STATUS_LABELS = {
    Status.PENDING:     "Pending",
    Status.READY:       "Ready",
    Status.IN_PROGRESS: "In progress",
    Status.DONE:        "Done",
    Status.DELAYED:     "Delayed",
    Status.CANCELLED:   "Cancelled",
}


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------

def _build_nx_graph(tasks: list, edges: list) -> nx.DiGraph:
    """
    Convert the scheduler's task list and edge list into a
    NetworkX DiGraph for layout and rendering.
    """
    G = nx.DiGraph()

    for task in tasks:
        G.add_node(
            task.task_id,
            label=_node_label(task),
            status=task.status,
            priority=task.priority,
            department=task.department,
        )

    for from_id, to_id in edges:
        G.add_edge(from_id, to_id)

    return G


def _node_label(task: Task) -> str:
    """
    Multi-line label shown inside each node.
    Keeps it short so the graph stays readable.
    """
    lines = [
        task.task_id,
        f"P:{task.priority}",
    ]
    if task.assigned_to:
        lines.append(task.assigned_to)
    return "\n".join(lines)


def _node_colours(G: nx.DiGraph) -> list:
    """Return a colour for each node in G.nodes() order."""
    return [
        STATUS_COLOURS.get(G.nodes[n]["status"], "#B4B2A9")
        for n in G.nodes()
    ]


def _legend_patches() -> list:
    """Build legend handles for every status colour."""
    return [
        mpatches.Patch(color=colour, label=STATUS_LABELS[status])
        for status, colour in STATUS_COLOURS.items()
    ]


def _hierarchical_layout(G: nx.DiGraph) -> dict:
    """
    Top-down layout that respects dependency order.
    Assigns each node a y-level equal to its longest path from any root,
    then spaces nodes evenly within each level.

    Falls back to spring layout if the graph has cycles
    (should not happen in a valid DAG but guards against bad state).
    """
    try:
        # Compute level for each node (longest path from any source)
        levels = {}
        for node in nx.topological_sort(G):
            preds = list(G.predecessors(node))
            if not preds:
                levels[node] = 0
            else:
                levels[node] = max(levels[p] for p in preds) + 1

        # Group nodes by level
        level_groups: dict[int, list] = {}
        for node, level in levels.items():
            level_groups.setdefault(level, []).append(node)

        # Assign (x, y) coordinates
        pos = {}
        max_level = max(level_groups.keys()) if level_groups else 0

        for level, nodes in level_groups.items():
            n = len(nodes)
            for i, node in enumerate(sorted(nodes)):
                x = (i - (n - 1) / 2.0)   # centre the row
                y = -(level / max(max_level, 1))  # top = 0, deeper = more negative
                pos[node] = (x, y)

        return pos

    except nx.NetworkXUnfeasible:
        # Cycle detected — fall back gracefully
        return nx.spring_layout(G, seed=42)


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

def draw_dag(
    tasks: list,
    edges: list,
    title: str = "Task dependency graph",
    figsize: tuple = (14, 8),
    show: bool = True,
    save_path: str = None,
) -> None:
    """
    Render the full dependency graph.

    Parameters
    ----------
    tasks       : list of Task objects (from dag.all_tasks())
    edges       : list of (from_id, to_id) tuples (from dag.all_edges())
    title       : plot title string
    figsize     : matplotlib figure size tuple
    show        : if True, call plt.show() at the end
    save_path   : if provided, save the figure to this path before showing

    Usage
    -----
        from visualisation.graph_view import draw_dag
        draw_dag(scheduler.dag.all_tasks(), scheduler.dag.all_edges())
    """
    if not tasks:
        print("No tasks to display.")
        return

    G = _build_nx_graph(tasks, edges)
    pos = _hierarchical_layout(G)
    colours = _node_colours(G)
    labels = {n: G.nodes[n]["label"] for n in G.nodes()}

    fig, ax = plt.subplots(figsize=figsize)
    ax.set_title(title, fontsize=16, fontweight="bold", pad=20)
    ax.axis("off")

    # Draw edges first so they sit behind nodes
    nx.draw_networkx_edges(
        G, pos,
        ax=ax,
        arrows=True,
        arrowstyle="-|>",
        arrowsize=20,
        edge_color="#5F5E5A",
        width=1.5,
        connectionstyle="arc3,rad=0.05",   # slight curve avoids overlap
        min_source_margin=25,
        min_target_margin=25,
    )

    # Draw nodes
    nx.draw_networkx_nodes(
        G, pos,
        ax=ax,
        node_color=colours,
        node_size=2200,
        node_shape="o",
        linewidths=1.5,
        edgecolors="#2C2C2A",
    )

    # Draw labels inside nodes
    nx.draw_networkx_labels(
        G, pos,
        labels=labels,
        ax=ax,
        font_size=8,
        font_color="#2C2C2A",
        font_weight="bold",
    )

    # Legend
    ax.legend(
        handles=_legend_patches(),
        loc="upper left",
        framealpha=0.9,
        fontsize=9,
        title="Status",
        title_fontsize=10,
    )

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"Graph saved to {save_path}")

    if show:
        plt.show()

    plt.close(fig)


def draw_critical_path(
    tasks: list,
    edges: list,
    critical_path_ids: list,
    title: str = "Critical path highlighted",
    figsize: tuple = (14, 8),
    show: bool = True,
    save_path: str = None,
) -> None:
    """
    Same as draw_dag but highlights the critical path in gold
    with thicker edges and a stronger node border.

    Parameters
    ----------
    critical_path_ids : list of task_id strings on the critical path
                        (from dag.critical_path()[0])

    Usage
    -----
        path, duration = scheduler.dag.critical_path()
        draw_critical_path(
            scheduler.dag.all_tasks(),
            scheduler.dag.all_edges(),
            critical_path_ids=path,
            title=f"Critical path — total duration {duration:.1f}h"
        )
    """
    if not tasks:
        print("No tasks to display.")
        return

    G = _build_nx_graph(tasks, edges)
    pos = _hierarchical_layout(G)
    colours = _node_colours(G)
    labels = {n: G.nodes[n]["label"] for n in G.nodes()}

    # Separate critical path edges from normal edges
    critical_set = set(critical_path_ids)
    critical_edges = [
        (u, v) for u, v in G.edges()
        if u in critical_set and v in critical_set
    ]
    normal_edges = [
        (u, v) for u, v in G.edges()
        if (u, v) not in critical_edges
    ]

    # Border widths — thicker for critical path nodes
    border_widths = [
        4.0 if n in critical_set else 1.5
        for n in G.nodes()
    ]
    border_colours = [
        "#BA7517" if n in critical_set else "#2C2C2A"
        for n in G.nodes()
    ]

    fig, ax = plt.subplots(figsize=figsize)
    ax.set_title(title, fontsize=16, fontweight="bold", pad=20)
    ax.axis("off")

    # Normal edges — muted
    if normal_edges:
        nx.draw_networkx_edges(
            G, pos,
            edgelist=normal_edges,
            ax=ax,
            arrows=True,
            arrowstyle="-|>",
            arrowsize=18,
            edge_color="#B4B2A9",
            width=1.2,
            connectionstyle="arc3,rad=0.05",
            min_source_margin=25,
            min_target_margin=25,
        )

    # Critical path edges — gold and bold
    if critical_edges:
        nx.draw_networkx_edges(
            G, pos,
            edgelist=critical_edges,
            ax=ax,
            arrows=True,
            arrowstyle="-|>",
            arrowsize=24,
            edge_color="#BA7517",
            width=3.0,
            connectionstyle="arc3,rad=0.05",
            min_source_margin=25,
            min_target_margin=25,
        )

    # Nodes
    nx.draw_networkx_nodes(
        G, pos,
        ax=ax,
        node_color=colours,
        node_size=2200,
        node_shape="o",
        linewidths=border_widths,
        edgecolors=border_colours,
    )

    # Labels
    nx.draw_networkx_labels(
        G, pos,
        labels=labels,
        ax=ax,
        font_size=8,
        font_color="#2C2C2A",
        font_weight="bold",
    )

    # Legend: status colours + critical path marker
    legend_handles = _legend_patches()
    legend_handles.append(
        mpatches.Patch(
            color="#BA7517",
            label="Critical path",
            linewidth=2,
        )
    )
    ax.legend(
        handles=legend_handles,
        loc="upper left",
        framealpha=0.9,
        fontsize=9,
        title="Status / Path",
        title_fontsize=10,
    )

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"Graph saved to {save_path}")

    if show:
        plt.show()

    plt.close(fig)


def draw_live_snapshot(
    tasks: list,
    edges: list,
    in_progress_ids: list = None,
    title: str = "Scheduler live snapshot",
    figsize: tuple = (14, 8),
    show: bool = True,
    save_path: str = None,
) -> None:
    """
    Convenience wrapper for the demo — draws the graph and adds
    a subtitle showing counts per status so the audience can
    see the scheduler state at a glance.

    Parameters
    ----------
    in_progress_ids : list of task_ids currently being executed
                      (from scheduler._in_progress.keys())

    Usage
    -----
        draw_live_snapshot(
            scheduler.dag.all_tasks(),
            scheduler.dag.all_edges(),
            in_progress_ids=list(scheduler._in_progress.keys()),
        )
    """
    in_progress_ids = in_progress_ids or []

    # Build status summary for subtitle
    status_counts = {s: 0 for s in Status}
    for task in tasks:
        status_counts[task.status] += 1

    parts = [
        f"Ready: {status_counts[Status.READY]}",
        f"In progress: {status_counts[Status.IN_PROGRESS]}",
        f"Pending: {status_counts[Status.PENDING]}",
        f"Done: {status_counts[Status.DONE]}",
        f"Cancelled: {status_counts[Status.CANCELLED]}",
    ]
    subtitle = "   |   ".join(p for p in parts if not p.endswith(": 0"))

    G = _build_nx_graph(tasks, edges)
    pos = _hierarchical_layout(G)
    colours = _node_colours(G)
    labels = {n: G.nodes[n]["label"] for n in G.nodes()}

    # Pulse ring around in-progress nodes
    in_progress_set = set(in_progress_ids)
    border_widths = [
        4.0 if n in in_progress_set else 1.5
        for n in G.nodes()
    ]
    border_colours = [
        "#BA7517" if n in in_progress_set else "#2C2C2A"
        for n in G.nodes()
    ]

    fig, ax = plt.subplots(figsize=figsize)
    fig.suptitle(title, fontsize=16, fontweight="bold", y=0.98)
    ax.set_title(subtitle, fontsize=10, color="#5F5E5A", pad=8)
    ax.axis("off")

    nx.draw_networkx_edges(
        G, pos,
        ax=ax,
        arrows=True,
        arrowstyle="-|>",
        arrowsize=20,
        edge_color="#5F5E5A",
        width=1.5,
        connectionstyle="arc3,rad=0.05",
        min_source_margin=25,
        min_target_margin=25,
    )

    nx.draw_networkx_nodes(
        G, pos,
        ax=ax,
        node_color=colours,
        node_size=2200,
        node_shape="o",
        linewidths=border_widths,
        edgecolors=border_colours,
    )

    nx.draw_networkx_labels(
        G, pos,
        labels=labels,
        ax=ax,
        font_size=8,
        font_color="#2C2C2A",
        font_weight="bold",
    )

    ax.legend(
        handles=_legend_patches(),
        loc="upper left",
        framealpha=0.9,
        fontsize=9,
        title="Status",
        title_fontsize=10,
    )

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"Snapshot saved to {save_path}")

    if show:
        plt.show()

    plt.close(fig)