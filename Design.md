# CodeExplain Agent 设计文档

## 1. 设计目标

本项目实现一个可运行、可解释、便于课堂演示的代码解释 Agent。它选择 Homework 1 的“代码解释 Agent”方向，重点验证以下能力：

1. 调用 LLM 进行工具选择和回答生成。
2. 使用清晰的 Agent 循环组织输入、推理、工具调用和输出。
3. 将文件读取和 Python AST 分析封装为独立工具。
4. 在 API Key 缺失或网络异常时提供可追踪的错误处理和本地工具流程展示。

## 2. 架构

```text
CLI(main.py)
    │ 用户问题
    ▼
CodeExplainAgent
    ├── 对话记忆：最近 4 轮问答
    ├── Planner
    │     ├── OpenAICompatibleClient：输出 JSON 动作
    │     └── Rule Planner：LLM 不可用时回退
    ├── Tool Router
    │     ├── FileReadTool：安全读取文本文件
    │     └── PythonStructureTool：AST 解析 Python 结构
    └── Answerer
          ├── LLM：根据工具证据生成解释
          └── Offline fallback：生成确定性说明
```

### Agent 循环

每次 `run(user_input)` 调用按照下列步骤执行：

1. 清理并校验用户输入。
2. Planner 选择 `answer`、`read_file` 或 `analyze_python`。
3. 调用批准的本地工具。读取 Python 文件后自动补充 AST 分析。
4. Answerer 仅依据用户问题、短期记忆和工具返回内容组织回答。
5. 将本轮用户消息和回答写入短期记忆，并保留最近 8 条消息。

这种设计把模型的非确定性限制在“选择动作”和“组织自然语言”两个位置，把文件边界检查、行号和语法结构交给确定性工具完成。

## 3. 工具设计

| 工具 | 输入 | 输出 | 安全策略 |
| --- | --- | --- | --- |
| `read_file` | 项目内相对路径 | 带行号的文本内容 | 路径解析后必须仍位于项目根目录；拒绝目录、二进制、超过 100KB 的文件 |
| `analyze_python` | Python 源码、文件名 | 导入、类、函数及其行号 | 使用标准库 `ast.parse`；返回语法错误而不执行代码 |

`FileReadTool` 兼容 UTF-8 和 GB18030 文本，以便读取常见中文 Windows 环境下的源文件。该 Agent 不提供执行代码工具，因此不会执行用户传入的未知代码。

## 4. LLM 集成

`OpenAICompatibleClient` 使用标准库 `urllib.request` 发送 `POST {LLM_BASE_URL}/chat/completions` 请求。客户端实现 OpenAI Chat Completions 兼容协议，本项目的在线接口配置和测试使用 DeepSeek API。

客户端按下表优先级读取配置：

| 优先级 | API Key | 接口根地址 | 模型名 |
| --- | --- | --- | --- |
| 推荐变量 | `LLM_API_KEY` | `LLM_BASE_URL` | `LLM_MODEL` |
| 兼容变量 | `OPENAI_API_KEY` | `OPENAI_BASE_URL` | `OPENAI_MODEL` |
| 默认值 | 无 | `https://api.openai.com/v1` | `gpt-4o-mini` |

服务必须提供 `/chat/completions` 接口、接受 `model`、`messages` 和 `response_format` 等 OpenAI 兼容字段，并采用 Bearer API Key 认证。符合这些条件的模型服务可以直接接入。

Anthropic Messages API、Gemini 原生 API 等不同协议不属于当前客户端的直接支持范围。若服务商提供 OpenAI 兼容端点，可使用本项目配置；否则需要实现专用客户端适配器。

规划阶段要求模型只输出 JSON。例如：

```json
{"action": "read_file", "argument": "examples/sort_numbers.py"}
```

代码校验动作白名单，拒绝任何不在 `answer`、`read_file`、`analyze_python` 中的值。LLM 请求失败后会以 0.5 秒、1 秒的退避间隔自动重试两次；规划请求最终失败时，改用本地规则选择动作。

DeepSeek 是本项目使用的 LLM API 服务。DeepSeek V4 Pro 的配置如下：

```powershell
$env:LLM_API_KEY = '你的 DeepSeek API Key'
$env:LLM_BASE_URL = 'https://api.deepseek.com'
$env:LLM_MODEL = 'deepseek-v4-pro'
```

客户端直接按给定地址请求 `/chat/completions`，因此 DeepSeek 地址不额外添加 `/v1`。需要降低响应时间和费用时可将模型改为 `deepseek-flash`。

## 5. 上下文记忆

Agent 将用户问句和最终回答保存为 `ChatMessage`，最多保留最近 8 条消息，即 4 轮对话。后续 LLM 调用携带这些消息，使用户可以对刚才解释的代码继续追问，而不会无限增长上下文。

## 6. 边界与错误处理

| 场景 | 系统行为 |
| --- | --- |
| 空问题 | 直接提示输入问题，不调用工具 |
| `../` 或绝对路径逃离项目目录 | `read_file` 返回拒绝信息 |
| 文件不存在、目录或大文件 | 返回明确错误，不崩溃 |
| 非文本文件 | 检测 NUL 字节或解码错误后拒绝 |
| Python 语法错误 | AST 工具返回行号和错误原因 |
| 无 API Key | 自动离线模式 |
| LLM 网络/API 错误 | 有限重试后回退或提示检查配置 |

## 7. 可测试性

项目不依赖真实 API 进行单元测试。`tests/test_tools.py` 使用临时工作区，验证：

- 文件读取结果包含行号。
- 文件工具无法越界。
- AST 工具能提取导入、类和函数。
- 离线 Agent 能依次调用文件读取工具并返回说明。
- 通用 `LLM_*` 环境变量能正确加载。

运行：

```powershell
python -X utf8 -m unittest discover -s tests -v
```

单元测试不发送真实 API 请求。在线运行时使用 DeepSeek API，通过命令行执行轨迹确认 LLM 规划、工具调用和回答生成。

## 8. 后续扩展

- 增加 JavaScript、Java 的语法分析工具。
- 允许模型在设定的最大步数内多次调用工具。
- 增加 Web 界面和对话历史持久化。
- 接入代码检索工具，支持跨文件调用链解释。
