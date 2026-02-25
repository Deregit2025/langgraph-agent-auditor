"""
graph.py — StateGraph orchestrator for the LangGraph Auditor.

Orchestration topology
-----------------------
The graph implements a proper fan-out / fan-in pattern:

    [Start]
      ├── RepoDetective  ─┐
      ├── DocDetective   ─┤─► [EvidenceAggregator] ──►  [Judges] ──► [Justice]
      └── VisionDetective┘
                              ↑ conditional edges:
                              if aggregated confidence < threshold → [LowConfidenceHandler]
                              else → [Judges]

Key design decisions
--------------------
* Detective nodes run in **parallel** via ThreadPoolExecutor (fan-out).
* Each detective node receives a **deep copy** of the shared state so there are
  no concurrent write races while detectives are collecting.  After all futures
  complete, the EvidenceAggregator merges the collected evidence lists using the
  ``operator.add`` reducer semantics defined in ``AgentState``.
* ``add_conditional_edge`` lets the graph route to different downstream nodes
  based on a condition function evaluated on the post-aggregation state.
* Trace logs are written to ``audit/langsmith_logs/`` as append-only JSONL
  entries (one per node execution) for post-mortem forensic reconstruction.
"""

import copy
import datetime
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Dict, List, Optional, Tuple

from src.state import AgentState


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------

class Node:
    """
    Represents a single computation unit in the StateGraph.

    Attributes
    ----------
    name       : Unique node identifier used when registering edges.
    func       : The node's execution function ``(AgentState) -> AgentState``.
    next_nodes : Static next-hop nodes added via ``add_edge``.
    """

    def __init__(self, name: str, func: Callable[[AgentState], Any]):
        self.name = name
        self.func = func
        self.next_nodes: List["Node"] = []

    def add_edge(self, node: "Node") -> None:
        if node not in self.next_nodes:
            self.next_nodes.append(node)

    def run(self, state: AgentState) -> AgentState:
        """Execute the node function and return the updated state."""
        result = self.func(state)
        return result if result is not None else state


# ---------------------------------------------------------------------------
# ConditionalEdge
# ---------------------------------------------------------------------------

class ConditionalEdge:
    """
    A routing rule evaluated after a specific node completes.

    Parameters
    ----------
    from_node  : Name of the node this edge originates from.
    condition  : ``(AgentState) -> str`` — returns a routing key.
    target_map : ``{routing_key: node_name}`` — maps keys to downstream nodes.
    """

    def __init__(
        self,
        from_node: str,
        condition: Callable[[AgentState], str],
        target_map: Dict[str, str],
    ):
        self.from_node = from_node
        self.condition = condition
        self.target_map = target_map


# ---------------------------------------------------------------------------
# StateGraph
# ---------------------------------------------------------------------------

class StateGraph:
    """
    Orchestrates node execution with:

    * **Fan-out**: nodes at the same dependency level run in parallel threads.
    * **Fan-in**: results from parallel nodes are merged via ``operator.add``
      reducers defined on ``AgentState`` list fields.
    * **Conditional edges**: post-node routing based on state inspection.
    * **JSONL tracing**: every node execution is logged to disk.
    """

    def __init__(self):
        self.nodes: Dict[str, Node] = {}
        self.start_nodes: List[Node] = []
        self.conditional_edges: List[ConditionalEdge] = []

    # ------------------------------------------------------------------
    # Graph construction API
    # ------------------------------------------------------------------

    def add_node(self, node: Node, start: bool = False) -> None:
        """Register a node. Pass ``start=True`` for fan-out entry points."""
        self.nodes[node.name] = node
        if start:
            self.start_nodes.append(node)

    def add_edge(self, from_node: str, to_node: str) -> None:
        """Add a static directed edge from *from_node* to *to_node*."""
        if from_node not in self.nodes:
            raise KeyError(f"[StateGraph] Unknown source node: '{from_node}'")
        if to_node not in self.nodes:
            raise KeyError(f"[StateGraph] Unknown target node: '{to_node}'")
        self.nodes[from_node].add_edge(self.nodes[to_node])

    def add_conditional_edge(
        self,
        from_node: str,
        condition: Callable[[AgentState], str],
        target_map: Dict[str, str],
    ) -> None:
        """
        Add a conditional routing rule evaluated after *from_node* completes.

        Parameters
        ----------
        from_node  : Name of the source node.
        condition  : Function ``(AgentState) -> str`` returning a routing key.
        target_map : ``{key: node_name}`` — at minimum should include a
                     ``"default"`` key as a fallback route.

        Example
        -------
        >>> graph.add_conditional_edge(
        ...     "EvidenceAggregator",
        ...     lambda s: "low" if _avg_confidence(s) < 0.4 else "ok",
        ...     {"low": "LowConfidenceHandler", "ok": "Judges"},
        ... )
        """
        for node_name in target_map.values():
            if node_name not in self.nodes:
                raise KeyError(
                    f"[StateGraph] Conditional edge target '{node_name}' not registered."
                )
        self.conditional_edges.append(
            ConditionalEdge(from_node, condition, target_map)
        )

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def run(self, state: AgentState, max_workers: int = 4) -> AgentState:
        """
        Execute the graph from start nodes.

        Algorithm
        ---------
        1. All start nodes run in **parallel** (fan-out), each on a deep-copy
           of the current state.
        2. After all futures resolve, their evidence/opinions are **merged** back
           into the master state (fan-in via list concatenation).
        3. After each level resolves, conditional edges are evaluated to
           determine the next hop.
        4. Static edges determine the remaining downstream levels.
        """
        log_dir = "audit/langsmith_logs"
        os.makedirs(log_dir, exist_ok=True)
        run_ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = os.path.join(log_dir, f"trace_{run_ts}.jsonl")
        print(f"[StateGraph] Trace log: {log_file}")

        visited: set = set()
        pending: List[Node] = list(self.start_nodes)

        while pending:
            # ── Parallel execution of all nodes in this level ──────────
            partial_states: Dict[str, AgentState] = {}

            if len(pending) == 1:
                # Single node — run directly, no copy overhead
                node = pending[0]
                partial_states[node.name] = self._run_node(node, state, log_file)
                visited.add(node.name)
            else:
                # Multiple nodes — give each a snapshot to avoid race conditions
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    snapshot = copy.deepcopy(state)
                    future_to_node = {
                        executor.submit(self._run_node, node, copy.deepcopy(snapshot), log_file): node
                        for node in pending
                    }
                    for future in as_completed(future_to_node):
                        node = future_to_node[future]
                        try:
                            partial_states[node.name] = future.result()
                        except Exception as exc:
                            self._log(log_file, node.name, "ERROR", str(exc))
                        visited.add(node.name)

                # ── Fan-in: merge evidence and opinions from all partials ──
                for partial in partial_states.values():
                    state.evidence_collection = (
                        state.evidence_collection + partial.evidence_collection
                    )
                    state.judicial_opinions = (
                        state.judicial_opinions + partial.judicial_opinions
                    )

            # ── Determine next level ────────────────────────────────────
            next_nodes_set: Dict[str, Node] = {}

            # 1. Conditional edges take priority
            for ce in self.conditional_edges:
                if ce.from_node in visited:
                    routing_key = ce.condition(state)
                    target_name = ce.target_map.get(routing_key) or ce.target_map.get("default")
                    if target_name and target_name not in visited:
                        next_nodes_set[target_name] = self.nodes[target_name]
                        self._log(log_file, ce.from_node, "CONDITIONAL_ROUTE",
                                  f"{routing_key} → {target_name}")

            # 2. Static edges (only add nodes not already captured by conditionals)
            for node in pending:
                for nxt in node.next_nodes:
                    if nxt.name not in visited and nxt.name not in next_nodes_set:
                        next_nodes_set[nxt.name] = nxt

            pending = list(next_nodes_set.values())

        return state

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run_node(self, node: Node, state: AgentState, log_file: str) -> AgentState:
        """Run a node and write JSONL trace entries for start and completion."""
        start_ts = datetime.datetime.now().isoformat()
        self._log(log_file, node.name, "START", f"evidence_in={len(state.evidence_collection)}")

        result = node.run(state)

        end_ts = datetime.datetime.now().isoformat()
        ev_delta = len(result.evidence_collection) - len(state.evidence_collection)
        op_delta = len(result.judicial_opinions) - len(state.judicial_opinions)
        self._log(
            log_file, node.name, "COMPLETE",
            f"duration={end_ts} evidence_added={ev_delta} opinions_added={op_delta}",
        )
        return result

    def _log(self, log_file: str, node_name: str, event: str, detail: str) -> None:
        """Append a single JSONL trace entry to the log file."""
        entry = {
            "ts": datetime.datetime.now().isoformat(),
            "node": node_name,
            "event": event,
            "detail": detail,
        }
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except OSError:
            pass  # Never let logging crash the audit