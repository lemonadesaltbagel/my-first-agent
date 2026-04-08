from pathlib import Path
from typing import TypeVar

import anthropic
import instructor

from models import ToolResult
from tools import TOOL_REGISTRY, get_tool_definitions

T = TypeVar("T")

SYSTEM_PROMPT = f"""\
You are a coding agent that helps users work with codebases. You can read, write, \
and edit files, run shell commands, search code, and analyze code structure.

Working directory: {Path.cwd()}

Capabilities:
- read_file: Read file contents
- write_file: Create or overwrite files
- edit_file: Make targeted edits (find & replace)
- list_directory: List files and directories
- run_command: Execute shell commands
- search_code: Search for patterns in code
- get_code_structure: Analyze code structure (functions, classes, methods)

Guidelines:
- Always read a file before editing it.
- Explain what you're doing and why.
- For destructive operations (deleting files, overwriting), confirm with the user first.
- Keep shell commands safe — avoid rm -rf, force pushes, etc. unless explicitly asked.
- When showing code changes, be specific about what changed and where.
"""

MODEL = "claude-sonnet-4-20250514"


class Agent:
    def __init__(self) -> None:
        self.client = anthropic.AsyncAnthropic()
        self.instructor_client = instructor.from_anthropic(anthropic.AsyncAnthropic())
        self.messages: list[dict] = []
        self.tools = get_tool_definitions()

    async def chat(self, user_message: str) -> str:
        """Run the agentic loop: send message, execute tools, repeat until done."""
        self.messages.append({"role": "user", "content": user_message})

        while True:
            response = await self.client.messages.create(
                model=MODEL,
                max_tokens=8096,
                system=SYSTEM_PROMPT,
                tools=self.tools,
                messages=self.messages,
            )

            # Append assistant response to history
            self.messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason == "end_turn":
                return self._extract_text(response.content)

            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        print(f"  [tool] {block.name}: {self._summarize_input(block.name, block.input)}")
                        result = await self._execute_tool(block.name, block.input)
                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": result.output if result.success else f"ERROR: {result.error}",
                                "is_error": not result.success,
                            }
                        )

                self.messages.append({"role": "user", "content": tool_results})

    async def structured_query(self, prompt: str, response_model: type[T]) -> T:
        """Use instructor to get a validated structured response from Claude."""
        return await self.instructor_client.messages.create(
            model=MODEL,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
            response_model=response_model,
        )

    async def _execute_tool(self, name: str, input_data: dict) -> ToolResult:
        """Validate input and execute a tool by name."""
        if name not in TOOL_REGISTRY:
            return ToolResult(success=False, output="", error=f"Unknown tool: {name}")

        func, model_class = TOOL_REGISTRY[name]
        try:
            parsed = model_class.model_validate(input_data)
            return await func(parsed)
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

    @staticmethod
    def _extract_text(content: list) -> str:
        """Extract text blocks from an API response."""
        parts = []
        for block in content:
            if block.type == "text":
                parts.append(block.text)
        return "\n".join(parts)

    @staticmethod
    def _summarize_input(tool_name: str, input_data: dict) -> str:
        """Create a short summary of tool input for terminal display."""
        if "path" in input_data:
            return input_data["path"]
        if "command" in input_data:
            cmd = input_data["command"]
            return cmd if len(cmd) < 60 else cmd[:57] + "..."
        if "pattern" in input_data:
            return input_data["pattern"]
        return ""
