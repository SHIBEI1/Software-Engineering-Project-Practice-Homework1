"""Offline planning and explanation so the project remains demoable without an API key."""

from __future__ import annotations

import re


def choose_action(question: str, active_file: str | None) -> tuple[str, str | None]:
    """Select a safe tool when no remote LLM is configured."""

    file_match = re.search(r"(?:文件|file)\s*[:：]?\s*([\w./\\-]+)", question, re.I)
    if file_match:
        return "read_file", file_match.group(1).replace("\\", "/")
    if active_file and any(word in question for word in ("代码", "文件", "这段", "它", "解释", "分析")):
        return "read_file", active_file
    return "answer", None


def summarize_code(source: str, filename: str, question: str, structure: str | None) -> str:
    """Give a concise rule-based answer when remote LLM access is unavailable."""

    nonempty = [line for line in source.splitlines() if line.strip()]
    preview = "\n".join(nonempty[:8])
    parts = [f"我已读取 `{filename}`。"]
    if structure:
        parts.append(structure)
    parts.append(
        "离线说明：该回答由本地规则生成。已识别到的代码开头如下：\n"
        f"```python\n{preview or '# 空文件'}\n```"
    )
    if "注释" in question:
        parts.append("可以继续指定函数名，我会为该函数生成逐段中文注释。")
    else:
        parts.append("如需更深入的逐行解释，请配置 OpenAI 兼容接口后再次提问。")
    return "\n\n".join(parts)


def simple_answer(question: str) -> str:
    return (
        "当前没有可分析的代码文件。请使用 `--file examples/sort_numbers.py` 启动，"
        "或在对话中输入 `解释文件: examples/sort_numbers.py`。\n\n"
        f"你刚才的问题是：{question}"
    )
