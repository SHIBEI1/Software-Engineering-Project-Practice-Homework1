"""CLI entry point for CodeExplain Agent."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from src.agent import CodeExplainAgent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="代码解释 Agent")
    parser.add_argument("--file", help="启动时关联的工作区内相对代码文件")
    parser.add_argument("--question", help="单次提问后退出")
    parser.add_argument("--show-steps", action="store_true", help="显示 Agent 执行轨迹")
    return parser.parse_args()


def print_response(answer: str, steps: list[str], show_steps: bool) -> None:
    print("\n[Agent]\n" + answer)
    if show_steps:
        print("\n[执行轨迹]")
        print("\n".join(steps))


def main() -> None:
    args = parse_args()
    workspace = Path(__file__).resolve().parent
    agent = CodeExplainAgent(workspace, args.file)
    if not (os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")):
        print("提示：未配置 LLM_API_KEY，当前使用仅供流程演示的离线回退模式。")

    if args.question:
        response = agent.run(args.question)
        print_response(response.answer, response.steps, args.show_steps)
        return

    print("代码解释 Agent 已启动。输入 exit 或 quit 结束。")
    print("示例：解释文件: examples/sort_numbers.py")
    while True:
        try:
            question = input("\n你> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n会话结束。")
            return
        if question.lower() in {"exit", "quit"}:
            print("会话结束。")
            return
        response = agent.run(question)
        print_response(response.answer, response.steps, args.show_steps)


if __name__ == "__main__":
    main()
