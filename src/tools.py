"""Safe, small local tools exposed to the code-explanation agent."""

from __future__ import annotations

import ast
from pathlib import Path

from .models import ToolResult


class FileReadTool:
    """Read a text file under one approved workspace with line numbers."""

    name = "read_file"
    _MAX_BYTES = 100 * 1024

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace.resolve()

    def run(self, requested_path: str) -> ToolResult:
        try:
            path = Path(requested_path)
            if not path.is_absolute():
                path = self.workspace / path
            path = path.resolve()
            path.relative_to(self.workspace)
        except ValueError:
            return ToolResult(self.name, False, "拒绝读取工作区以外的文件。")

        if not path.exists() or not path.is_file():
            return ToolResult(self.name, False, f"文件不存在或不是普通文件：{requested_path}")
        if path.stat().st_size > self._MAX_BYTES:
            return ToolResult(self.name, False, "文件超过 100KB，拒绝读取以避免上下文过长。")

        raw = path.read_bytes()
        if b"\x00" in raw:
            return ToolResult(self.name, False, "检测到二进制内容，无法作为源代码文本读取。")
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            try:
                text = raw.decode("gb18030")
            except UnicodeDecodeError:
                return ToolResult(self.name, False, "文件不是 UTF-8 或 GB18030 文本。")

        numbered = "\n".join(
            f"{line_no:>4}: {line}" for line_no, line in enumerate(text.splitlines(), 1)
        )
        relative = path.relative_to(self.workspace)
        return ToolResult(self.name, True, f"文件：{relative}\n{numbered or '(空文件)'}")


class PythonStructureTool:
    """Use Python AST to produce deterministic structural facts for .py files."""

    name = "analyze_python"

    def run(self, source: str, filename: str = "代码片段") -> ToolResult:
        try:
            tree = ast.parse(source, filename=filename)
        except SyntaxError as exc:
            return ToolResult(
                self.name,
                False,
                f"Python 语法解析失败：第 {exc.lineno} 行，第 {exc.offset} 列：{exc.msg}",
            )

        imports: list[str] = []
        functions: list[str] = []
        classes: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or "."
                imports.extend(f"{module}.{alias.name}" for alias in node.names)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                prefix = "async " if isinstance(node, ast.AsyncFunctionDef) else ""
                functions.append(f"{prefix}{node.name}() (第 {node.lineno} 行)")
            elif isinstance(node, ast.ClassDef):
                classes.append(f"{node.name} (第 {node.lineno} 行)")

        lines = [f"{filename} 的 AST 结构："]
        lines.append("导入：" + ("、".join(imports) if imports else "无"))
        lines.append("类：" + ("、".join(classes) if classes else "无"))
        lines.append("函数：" + ("、".join(functions) if functions else "无"))
        return ToolResult(self.name, True, "\n".join(lines))
