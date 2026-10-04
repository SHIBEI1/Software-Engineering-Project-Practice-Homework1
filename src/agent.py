"""The Agent loop: input -> reasoning -> tool call -> answer."""

from __future__ import annotations

import json
from pathlib import Path

from .fallback import choose_action, simple_answer, summarize_code
from .llm import LLMError, OpenAICompatibleClient
from .models import AgentResponse, ChatMessage
from .tools import FileReadTool, PythonStructureTool


PLANNER_PROMPT = """你是代码解释 Agent 的规划器。根据用户问题，从以下动作中选择一个：
answer：不需要工具；read_file：读取工作区内代码；analyze_python：分析已提供的 Python 代码。
只能返回 JSON，格式为 {\"action\": \"answer|read_file|analyze_python\", \"argument\": \"可选的相对路径\"}。
严禁要求读取工作区之外的文件。"""

ANSWER_PROMPT = """你是中文代码解释助手。基于用户问题和工具结果，准确解释代码，不虚构未看到的实现。
先说明结论，再按需解释流程、关键变量和风险。内容简洁，并引用相关行号。"""


class CodeExplainAgent:
    """Stateful agent with local file and AST tools plus optional LLM reasoning."""

    def __init__(self, workspace: Path, active_file: str | None = None) -> None:
        self.workspace = workspace.resolve()
        self.active_file = active_file
        self.history: list[ChatMessage] = []
        self.file_tool = FileReadTool(self.workspace)
        self.ast_tool = PythonStructureTool()
        self.llm = OpenAICompatibleClient()

    def run(self, user_input: str) -> AgentResponse:
        """Run one visible agent turn and retain a compact conversation memory."""

        clean_input = user_input.strip()
        if not clean_input:
            return AgentResponse("请输入一个关于代码的问题。")
        steps = ["1. 接收问题"]
        action, argument = self._plan(clean_input, steps)
        context = ""
        filename = argument or self.active_file or ""

        if action == "read_file" and argument:
            result = self.file_tool.run(argument)
            steps.append(f"3. 调用工具 read_file：{'成功' if result.ok else '失败'}")
            context = result.content
            if result.ok and argument.endswith(".py"):
                source = "\n".join(line.split(": ", 1)[1] if ": " in line else line for line in context.splitlines()[1:])
                ast_result = self.ast_tool.run(source, argument)
                steps.append(f"4. 调用工具 analyze_python：{'成功' if ast_result.ok else '失败'}")
                context = f"{context}\n\n{ast_result.content}"
                if self.llm.available:
                    answer = self._answer_with_llm(clean_input, context, steps)
                else:
                    answer = summarize_code(source, argument, clean_input, ast_result.content if ast_result.ok else None)
            elif result.ok:
                answer = self._answer_with_llm(clean_input, context, steps) if self.llm.available else context
            else:
                answer = result.content
        elif action == "analyze_python" and (argument or self.active_file):
            target = argument or self.active_file
            result = self.file_tool.run(target)
            steps.append(f"3. 调用工具 read_file：{'成功' if result.ok else '失败'}")
            if not result.ok:
                answer = result.content
            else:
                source = "\n".join(
                    line.split(": ", 1)[1] if ": " in line else line
                    for line in result.content.splitlines()[1:]
                )
                ast_result = self.ast_tool.run(source, target)
                steps.append(f"4. 调用工具 analyze_python：{'成功' if ast_result.ok else '失败'}")
                context = f"{result.content}\n\n{ast_result.content}"
                answer = (
                    self._answer_with_llm(clean_input, context, steps)
                    if self.llm.available
                    else summarize_code(source, target, clean_input, ast_result.content if ast_result.ok else None)
                )
        else:
            answer = self._answer_with_llm(clean_input, "", steps) if self.llm.available else simple_answer(clean_input)

        steps.append("5. 生成回答")
        self._remember(clean_input, answer)
        return AgentResponse(answer=answer, steps=steps)

    def _plan(self, question: str, steps: list[str]) -> tuple[str, str | None]:
        if not self.llm.available:
            action, argument = choose_action(question, self.active_file)
            steps.append(f"2. 离线规划：{action}")
            return action, argument
        try:
            raw = self.llm.chat(
                PLANNER_PROMPT,
                self.history + [ChatMessage("user", question)],
                response_format={"type": "json_object"},
            )
            decision = json.loads(raw)
            action = decision.get("action", "answer")
            argument = decision.get("argument") or self.active_file
            if action not in {"answer", "read_file", "analyze_python"}:
                raise ValueError("动作不在允许列表")
            steps.append(f"2. LLM 规划：{action}")
            return action, argument
        except (LLMError, ValueError, json.JSONDecodeError) as exc:
            action, argument = choose_action(question, self.active_file)
            steps.append(f"2. LLM 规划失败，回退至本地规划：{exc}")
            return action, argument

    def _answer_with_llm(self, question: str, context: str, steps: list[str]) -> str:
        prompt = f"用户问题：{question}\n\n工具结果：\n{context or '无'}"
        try:
            return self.llm.chat(ANSWER_PROMPT, self.history + [ChatMessage("user", prompt)])
        except LLMError as exc:
            steps.append(f"LLM 回答失败：{exc}")
            return "LLM 暂时不可用。请检查 API 地址、模型名称和密钥后重试。"

    def _remember(self, question: str, answer: str) -> None:
        self.history.extend([ChatMessage("user", question), ChatMessage("assistant", answer)])
        self.history = self.history[-8:]
