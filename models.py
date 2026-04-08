from typing import Literal

from pydantic import BaseModel, Field


# --- Constants ---

MAX_OUTPUT_CHARS = 100_000


# --- Tool Input Models ---


class ReadFileInput(BaseModel):
    """Read the contents of a file at the given path."""

    path: str = Field(description="The file path to read")


class WriteFileInput(BaseModel):
    """Create or overwrite a file with the given content."""

    path: str = Field(description="The file path to write to")
    content: str = Field(description="The content to write")


class EditFileInput(BaseModel):
    """Edit a file by replacing an exact text match with new text."""

    path: str = Field(description="The file path to edit")
    old_text: str = Field(description="The exact text to find and replace")
    new_text: str = Field(description="The replacement text")


class ListDirectoryInput(BaseModel):
    """List files and directories at the given path."""

    path: str = Field(default=".", description="The directory path to list")
    recursive: bool = Field(default=False, description="Whether to list recursively")
    max_depth: int = Field(default=3, description="Maximum depth for recursive listing")


class RunCommandInput(BaseModel):
    """Run a shell command and return its output."""

    command: str = Field(description="The shell command to execute")
    timeout: int = Field(default=30, description="Timeout in seconds")


class SearchCodeInput(BaseModel):
    """Search for a pattern in files using grep."""

    pattern: str = Field(description="The regex pattern to search for")
    path: str = Field(default=".", description="The directory to search in")
    file_glob: str = Field(default="*", description="File glob pattern to filter files")


class GetCodeStructureInput(BaseModel):
    """Parse a source file and return its structure (functions, classes, methods)."""

    path: str = Field(description="The file path to analyze")


# --- Tool Result Model ---


class ToolResult(BaseModel):
    success: bool
    output: str
    error: str | None = None


# --- Structured Output Models (for instructor) ---


class AgentPlan(BaseModel):
    """A structured plan produced by the agent."""

    summary: str = Field(description="Brief summary of the plan")
    steps: list[str] = Field(description="Ordered list of implementation steps")
    files_involved: list[str] = Field(description="File paths that will be created or modified")
    risk_level: Literal["low", "medium", "high"] = Field(
        description="Risk level of the proposed changes"
    )
