# my-first-agent(written in Jan 2025)

A CLI coding agent powered by Claude. It can read, write, and edit files, run shell commands, search code, and analyze code structure using tree-sitter — all through a conversational interface.

This agent is inspired by the ReAct framework. After reading the paper, I dove into studying the idea and its surrounding libraries, and in this project I set out to implement its core concepts from scratch. The focus is on the most fundamental pieces—tool use and the agent loop—built up by hand rather than pulled from an existing library. The harness design also borrows from ReAct, including practical constraints such as capping the edit window at 100,000 tokens and providing a dedicated code-section search tool.

As a next step, I plan to learn other industrial-grade libraries: `tenacity` for handling unstable network conditions, `rich` for improved terminal output, and `prompt_toolkit` for a modern interactive experience. I also intend to explore higher-level agent design topics such as memory management and multi-agent orchestration.

## Next Steps
I'll analyze well-known open-source repositories to learn how they implement high-level features such as planning mode, memory management, multi-agent collaboration, and accident handling.

## Prerequisites

- Python 3.14+
- [uv](https://docs.astral.sh/uv/) package manager
- An Anthropic API key

## Setup

1. Clone the repository:

```bash
git clone <repo-url>
cd my-first-agent
```

2. Install dependencies:

```bash
uv sync
```

3. Create a `.env` file with your API key:

```bash
echo "ANTHROPIC_API_KEY=sk-ant-..." > .env
```

## Usage

Start the agent:

```bash
uv run python main.py
```

You'll see an interactive prompt:

```
Coding Agent (type 'exit' to quit, '/plan <query>' for structured planning)
Working directory: /path/to/my-first-agent

you>
```

Type natural language requests and the agent will use its tools to help you. Tool calls are printed to the terminal as they happen:

```
you> What files are in this project?
  [tool] list_directory: .

assistant> Here are the files in the project...
```

### Commands

| Command | Description |
|---|---|
| `/plan <query>` | Generate a structured plan with steps, files, and risk level |
| `exit` or `quit` | Exit the agent |
| `Ctrl+C` | Exit the agent |

### Example conversations

**Read and understand code:**

```
you> Read agent.py and explain how the agentic loop works
```

**Edit files:**

```
you> In models.py, change MAX_OUTPUT_CHARS from 100000 to 200000
```

**Run commands:**

```
you> Run the tests with pytest
```

**Search code:**

```
you> Find all usages of ToolResult across the project
```

**Analyze code structure:**

```
you> Show me the structure of tools.py — what functions and classes does it have?
```

**Structured planning:**

```
you> /plan Add a new tool that can read and summarize PDF files
```

Output:

```
  Summary: Add a PDF reading tool using PyPDF2
  Risk: low

  Steps:
    1. Add PyPDF2 to dependencies
    2. Create ReadPdfInput model in models.py
    3. Implement read_pdf function in tools.py
    4. Register the tool in TOOL_REGISTRY

  Files:
    - pyproject.toml
    - models.py
    - tools.py
```

## Available tools

The agent has access to 7 tools:

| Tool | Description |
|---|---|
| `read_file` | Read the contents of a file |
| `write_file` | Create or overwrite a file |
| `edit_file` | Replace specific text in a file (find & replace) |
| `list_directory` | List files and directories (with optional recursion) |
| `run_command` | Execute a shell command with timeout |
| `search_code` | Search for regex patterns in files via grep |
| `get_code_structure` | Parse a file with tree-sitter to extract functions, classes, and methods |

## Project structure

```
main.py        — Entry point: async CLI chat loop
agent.py       — Agent class: system prompt, tool dispatch, agentic loop
tools.py       — 7 tool implementations + registry
models.py      — Pydantic models for tool I/O + structured responses
pyproject.toml — Project config and dependencies
.env           — Anthropic API key (not tracked in git)
```

## Tech stack

- [Anthropic SDK](https://github.com/anthropics/anthropic-sdk-python) — Claude API with tool use
- [Pydantic](https://docs.pydantic.dev/) — Data validation for tool inputs/outputs
- [Instructor](https://github.com/jxnl/instructor) — Structured outputs from Claude
- [tree-sitter](https://tree-sitter.github.io/) — Code parsing and structure analysis
- asyncio, pathlib, subprocess — Python standard library
