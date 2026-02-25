# LangGraph Auditor 🕵️‍♂️

A multi-agent forensic system designed to audit LangGraph implementations. It uses a sophisticated fan-out/fan-in architecture to collect evidence, evaluate it through a dialectical judicial process, and synthesize a final audit report.

## 🚀 Overview

The system orchestrates three types of agents:
1.  **Detectives (Forensic Layer)**: Parallel agents (`Repo`, `Doc`, `Vision`) that collect raw evidence from the codebase, git logs, and documentation.
2.  **Judges (Intelligence Layer)**: A dialectical panel consisting of a **Prosecutor**, a **Defense**, and a **Tech Lead** who evaluate the evidence based on a standardized rubric.
3.  **Justice (Synthesis Layer)**: The Chief Justice agent who consolidates all opinions into a final, professional audit report.

## 🛠 Installation

### Prerequisites
- Python 3.11+
- [Poetry](https://python-poetry.org/docs/#installation) (recommended) or `pip`

### Setup
1.  **Clone the repository**:
    ```bash
    git clone <repository_url>
    cd langgraph-auditor
    ```

2.  **Install dependencies**:
    Using Poetry:
    ```bash
    poetry install
    ```
    Using pip:
    ```bash
    pip install .
    ```

3.  **Configure Environment Variables**:
    Copy the example environment file and fill in your API keys:
    ```bash
    cp .env.example .env
    ```
    Edit `.env` to include your `OPENAI_API_KEY` or configure **Ollama** for local execution.

## 🔍 Running the Audit

To run the audit graph against a target repository or local project:

```bash
# Run in "self" mode to audit the current project
python main.py --mode self

# Run in "peer" mode to audit a remote repository (configured in .env)
python main.py --mode peer
```

### Advanced Usage
You can specify custom paths via `--metadata`:
```bash
python main.py --mode self --metadata '{"pdf_path": "report/MY_REPORT.md", "image_path": "assets/diagram.png"}'
```

## 🏗 Architecture

The system uses a **StateGraph** with the following topology:
- **Parallel Fan-Out**: Multiple detective nodes start simultaneously to collect evidence from different sources.
- **Evidence Aggregator**: A central node that consolidates findings and resolves conflicts.
- **Conditional Routing**: If the aggregate confidence of evidence is too low, the graph routes through a `LowConfidenceHandler` before reaching the judges.
- **Dialectical Evaluation**: Three judges provide adversarial and technical perspectives to ensure a balanced audit.

## 📂 Project Structure

- `src/graph.py`: The core StateGraph orchestrator.
- `src/state.py`: Typed Pydantic models for AgentState and Evidence.
- `src/nodes/`: Implementation of Detectives, Judges, and Aggregators.
- `src/tools/`: Forensic tools for PDF analysis, Git history, and AST parsing.
- `rubric/`: The standardized evaluation criteria used by the judges.
- `audit/`: Generated audit reports and execution trace logs.

## 🛡 Security
- No secrets are stored in the codebase.
- API keys are managed exclusively via `.env` files.
- Use `.env.example` as a template for new deployments.
