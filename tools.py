import asyncio
import re
from collections.abc import Callable
from pathlib import Path

from pydantic import BaseModel
from tree_sitter import Language, Parser

from models import (
    MAX_OUTPUT_CHARS,
    EditFileInput,
    GetCodeStructureInput,
    ListDirectoryInput,
    ReadFileInput,
    RunCommandInput,
    SearchCodeInput,
    ToolResult,
    WriteFileInput,
)

# --- Tree-sitter language setup ---

LANGUAGE_MAP: dict[str, tuple[str, Language]] = {}

try:
    import tree_sitter_python as tspython

    LANGUAGE_MAP[".py"] = ("python", Language(tspython.language()))
except ImportError:
    pass

try:
    import tree_sitter_javascript as tsjavascript

    LANGUAGE_MAP[".js"] = ("javascript", Language(tsjavascript.language()))
    LANGUAGE_MAP[".jsx"] = ("javascript", Language(tsjavascript.language()))
except ImportError:
    pass

SKIP_DIRS = {".git", ".venv", "__pycache__", "node_modules", ".mypy_cache", ".pytest_cache"}


# --- Tool implementations ---


async def read_file(input: ReadFileInput) -> ToolResult:
    try:
        path = Path(input.path)
        content = path.read_text(encoding="utf-8")
        if len(content) > MAX_OUTPUT_CHARS:
            content = content[:MAX_OUTPUT_CHARS] + f"\n\n... [truncated, file is {len(content)} chars]"
        return ToolResult(success=True, output=content)
    except FileNotFoundError:
        return ToolResult(success=False, output="", error=f"File not found: {input.path}")
    except PermissionError:
        return ToolResult(success=False, output="", error=f"Permission denied: {input.path}")
    except Exception as e:
        return ToolResult(success=False, output="", error=str(e))


async def write_file(input: WriteFileInput) -> ToolResult:
    try:
        path = Path(input.path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(input.content, encoding="utf-8")
        return ToolResult(success=True, output=f"Wrote {len(input.content)} bytes to {input.path}")
    except Exception as e:
        return ToolResult(success=False, output="", error=str(e))


async def edit_file(input: EditFileInput) -> ToolResult:
    try:
        path = Path(input.path)
        content = path.read_text(encoding="utf-8")

        count = content.count(input.old_text)
        if count == 0:
            return ToolResult(success=False, output="", error="old_text not found in file")
        if count > 1:
            return ToolResult(
                success=False,
                output="",
                error=f"old_text found {count} times — must be unique. Provide more context.",
            )

        new_content = content.replace(input.old_text, input.new_text, 1)
        path.write_text(new_content, encoding="utf-8")

        # Show context around the edit
        edit_pos = new_content.find(input.new_text)
        start = max(0, new_content.rfind("\n", 0, edit_pos - 50) + 1) if edit_pos > 50 else 0
        end = min(len(new_content), new_content.find("\n", edit_pos + len(input.new_text) + 50))
        if end == -1:
            end = len(new_content)
        context = new_content[start:end]

        return ToolResult(success=True, output=f"Edit applied. Context:\n{context}")
    except FileNotFoundError:
        return ToolResult(success=False, output="", error=f"File not found: {input.path}")
    except Exception as e:
        return ToolResult(success=False, output="", error=str(e))


async def list_directory(input: ListDirectoryInput) -> ToolResult:
    try:
        root = Path(input.path)
        if not root.is_dir():
            return ToolResult(success=False, output="", error=f"Not a directory: {input.path}")

        lines: list[str] = []

        def _walk(dir_path: Path, prefix: str, depth: int) -> None:
            if depth > input.max_depth:
                return
            try:
                entries = sorted(dir_path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
            except PermissionError:
                return

            for entry in entries:
                if entry.name in SKIP_DIRS:
                    continue
                if entry.is_dir():
                    lines.append(f"{prefix}{entry.name}/")
                    if input.recursive:
                        _walk(entry, prefix + "  ", depth + 1)
                else:
                    lines.append(f"{prefix}{entry.name}")

        _walk(root, "", 0)
        output = "\n".join(lines) if lines else "(empty directory)"
        return ToolResult(success=True, output=output)
    except Exception as e:
        return ToolResult(success=False, output="", error=str(e))


async def run_command(input: RunCommandInput) -> ToolResult:
    try:
        proc = await asyncio.create_subprocess_shell(
            input.command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=input.timeout)
        except asyncio.TimeoutError:
            proc.kill()
            return ToolResult(success=False, output="", error=f"Command timed out after {input.timeout}s")

        output = ""
        if stdout:
            output += stdout.decode(errors="replace")
        if stderr:
            output += ("\n--- stderr ---\n" if output else "") + stderr.decode(errors="replace")

        if len(output) > MAX_OUTPUT_CHARS:
            output = output[:MAX_OUTPUT_CHARS] + "\n\n... [truncated]"

        return ToolResult(
            success=proc.returncode == 0,
            output=output,
            error=f"Exit code: {proc.returncode}" if proc.returncode != 0 else None,
        )
    except Exception as e:
        return ToolResult(success=False, output="", error=str(e))


async def search_code(input: SearchCodeInput) -> ToolResult:
    try:
        cmd = f'grep -rn --include="{input.file_glob}" "{input.pattern}" "{input.path}"'
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)

        output = stdout.decode(errors="replace") if stdout else ""
        lines = output.strip().split("\n") if output.strip() else []

        if len(lines) > 50:
            lines = lines[:50]
            lines.append(f"\n... [showing 50 of {len(output.strip().splitlines())} matches]")

        result = "\n".join(lines) if lines else "No matches found."
        return ToolResult(success=True, output=result)
    except asyncio.TimeoutError:
        return ToolResult(success=False, output="", error="Search timed out")
    except Exception as e:
        return ToolResult(success=False, output="", error=str(e))


async def get_code_structure(input: GetCodeStructureInput) -> ToolResult:
    try:
        path = Path(input.path)
        content = path.read_text(encoding="utf-8")
        suffix = path.suffix

        if suffix in LANGUAGE_MAP:
            return _parse_with_tree_sitter(content, suffix)
        else:
            return _parse_with_regex(content, suffix)
    except FileNotFoundError:
        return ToolResult(success=False, output="", error=f"File not found: {input.path}")
    except Exception as e:
        return ToolResult(success=False, output="", error=str(e))


def _parse_with_tree_sitter(content: str, suffix: str) -> ToolResult:
    lang_name, language = LANGUAGE_MAP[suffix]
    parser = Parser(language)
    tree = parser.parse(content.encode())

    lines: list[str] = []
    _walk_tree(tree.root_node, lines, lang_name, depth=0)

    output = "\n".join(lines) if lines else "(no structure found)"
    return ToolResult(success=True, output=output)


def _walk_tree(node, lines: list[str], lang: str, depth: int) -> None:
    indent = "  " * depth

    if lang == "python":
        if node.type == "function_definition":
            name = _get_child_text(node, "name")
            lines.append(f"{indent}def {name} (line {node.start_point.row + 1})")
        elif node.type == "class_definition":
            name = _get_child_text(node, "name")
            lines.append(f"{indent}class {name} (line {node.start_point.row + 1})")
            for child in node.children:
                if child.type == "block":
                    _walk_tree(child, lines, lang, depth + 1)
            return
    elif lang == "javascript":
        if node.type == "function_declaration":
            name = _get_child_text(node, "name")
            lines.append(f"{indent}function {name} (line {node.start_point.row + 1})")
        elif node.type == "class_declaration":
            name = _get_child_text(node, "name")
            lines.append(f"{indent}class {name} (line {node.start_point.row + 1})")
            for child in node.children:
                if child.type == "class_body":
                    _walk_tree(child, lines, lang, depth + 1)
            return
        elif node.type == "method_definition":
            name = _get_child_text(node, "name")
            lines.append(f"{indent}method {name} (line {node.start_point.row + 1})")

    for child in node.children:
        _walk_tree(child, lines, lang, depth)


def _get_child_text(node, field_name: str) -> str:
    child = node.child_by_field_name(field_name)
    return child.text.decode() if child else "<unknown>"


def _parse_with_regex(content: str, suffix: str) -> ToolResult:
    lines: list[str] = []
    for i, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()
        if re.match(r"^(def |class |function |export function |export class )", stripped):
            indent = len(line) - len(line.lstrip())
            prefix = "  " * (indent // 4)
            lines.append(f"{prefix}{stripped.rstrip(':')} (line {i})")

    output = "\n".join(lines) if lines else "(no structure found)"
    return ToolResult(success=True, output=output)


# --- Tool Registry ---

TOOL_REGISTRY: dict[str, tuple[Callable, type[BaseModel]]] = {
    "read_file": (read_file, ReadFileInput),
    "write_file": (write_file, WriteFileInput),
    "edit_file": (edit_file, EditFileInput),
    "list_directory": (list_directory, ListDirectoryInput),
    "run_command": (run_command, RunCommandInput),
    "search_code": (search_code, SearchCodeInput),
    "get_code_structure": (get_code_structure, GetCodeStructureInput),
}


def get_tool_definitions() -> list[dict]:
    """Convert the tool registry into Anthropic API tool definitions."""
    definitions = []
    for name, (_, model_class) in TOOL_REGISTRY.items():
        definitions.append(
            {
                "name": name,
                "description": model_class.__doc__ or "",
                "input_schema": model_class.model_json_schema(),
            }
        )
    return definitions
