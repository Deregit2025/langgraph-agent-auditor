from typing import Callable, List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from src.state import AgentState, Evidence, JudicialOpinion

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

        while pending:
            # Execute all nodes at the current level in parallel
            results = {}
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_node = {executor.submit(node.run, state): node for node in pending}
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