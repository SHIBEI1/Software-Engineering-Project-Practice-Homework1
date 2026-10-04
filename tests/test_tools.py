"""Unit tests for local tools and the offline agent loop."""

from __future__ import annotations

import tempfile
import unittest
from os import environ
from pathlib import Path
from unittest.mock import patch

from src.agent import CodeExplainAgent
from src.llm import LLMConfig, OpenAICompatibleClient
from src.tools import FileReadTool, PythonStructureTool


class ToolTests(unittest.TestCase):
    def test_reads_text_under_workspace_with_line_numbers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "demo.py").write_text("def hello():\n    return 'hi'\n", encoding="utf-8")
            result = FileReadTool(root).run("demo.py")
        self.assertTrue(result.ok)
        self.assertIn("1: def hello", result.content)

    def test_rejects_path_outside_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = FileReadTool(Path(directory)).run("../secret.txt")
        self.assertFalse(result.ok)
        self.assertIn("工作区以外", result.content)

    def test_parses_python_structure(self) -> None:
        result = PythonStructureTool().run("import os\nclass Box: pass\ndef f(): pass\n")
        self.assertTrue(result.ok)
        self.assertIn("os", result.content)
        self.assertIn("Box", result.content)
        self.assertIn("f()", result.content)

    def test_offline_agent_uses_file_tool(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "demo.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
            agent = CodeExplainAgent(root, "demo.py")
            agent.llm = OpenAICompatibleClient(
                LLMConfig(api_key=None, base_url="https://example.invalid/v1", model="test")
            )
            response = agent.run("解释这段代码")
        self.assertIn("demo.py", response.answer)
        self.assertTrue(any("read_file" in step for step in response.steps))

    def test_generic_llm_environment_variables_take_priority(self) -> None:
        with patch.dict(
            environ,
            {
                "LLM_API_KEY": "generic-key",
                "LLM_BASE_URL": "https://example.com/api",
                "LLM_MODEL": "example-model",
                "OPENAI_API_KEY": "legacy-key",
            },
            clear=True,
        ):
            config = LLMConfig.from_env()
        self.assertEqual(config.api_key, "generic-key")
        self.assertEqual(config.base_url, "https://example.com/api")
        self.assertEqual(config.model, "example-model")


if __name__ == "__main__":
    unittest.main()
