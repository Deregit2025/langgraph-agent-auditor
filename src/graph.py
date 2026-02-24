from typing import Callable, List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from src.state import AgentState, Evidence, JudicialOpinion
import os
import datetime
from langchain_core.callbacks import FileCallbackHandler
from langchain_core.tracers.log_stream import LogStreamCallbackHandler

# ------------------------------
# Node representation
# ------------------------------
class Node:
    """Represents a node in the LangGraph."""
    def __init__(self, name: str, func: Callable[[AgentState], Any]):
        self.name = name
        self.func = func
        self.next_nodes: List["Node"] = []

    def add_edge(self, node: "Node"):
        self.next_nodes.append(node)

    def run(self, state: AgentState):
        """Execute the node function and return updated state."""
        result = self.func(state)
        return result


# ------------------------------
# StateGraph Orchestrator
# ------------------------------
class StateGraph:
    """Orchestrates execution of nodes with fan-out and fan-in support."""
    def __init__(self):
        self.nodes: Dict[str, Node] = {}
        self.start_nodes: List[Node] = []

    def add_node(self, node: Node, start: bool = False):
        self.nodes[node.name] = node
        if start:
            self.start_nodes.append(node)

    def add_edge(self, from_node: str, to_node: str):
        self.nodes[from_node].add_edge(self.nodes[to_node])

    def run(self, state: AgentState, max_workers: int = 4) -> AgentState:
        """Run the graph starting from start nodes using parallel execution for fan-out."""
        visited = set()
        pending = list(self.start_nodes)
        
        # Setup Tracing if requested
        log_dir = "audit/langsmith_logs"
        os.makedirs(log_dir, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = os.path.join(log_dir, f"trace_{timestamp}.log")
        handler = FileCallbackHandler(log_file)

        print(f"[*] Graph execution tracing enabled: {log_file}")

        while pending:
            # Execute all nodes at the current level in parallel
            results = {}
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # For now, we simulate the 'trace' by logging start/end
                future_to_node = {executor.submit(self._run_node, node, state, log_file): node for node in pending}
                for future in as_completed(future_to_node):
                    node = future_to_node[future]
                    results[node.name] = future.result()
                    visited.add(node.name)

            # Prepare next level nodes (fan-in handled by only adding unvisited nodes)
            next_level = []
            for node in pending:
                for next_node in node.next_nodes:
                    if next_node.name not in visited and next_node not in next_level:
                        next_level.append(next_node)

            pending = next_level

        return state

    def _run_node(self, node: Node, state: AgentState, log_file: str):
        """Internal helper to run node with logging."""
        timestamp = datetime.datetime.now().isoformat()
        with open(log_file, "a") as f:
            f.write(f"[{timestamp}] Starting Node: {node.name}\n")
        
        result = node.run(state)
        
        timestamp = datetime.datetime.now().isoformat()
        with open(log_file, "a") as f:
            f.write(f"[{timestamp}] Completed Node: {node.name}\n")
        
        return result