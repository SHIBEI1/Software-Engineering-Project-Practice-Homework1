# CodeExplain Agent

软件开发与项目实践 Homework 1。项目选择“代码解释 Agent”方向：用户可以在命令行提出代码问题，Agent 按“输入 → 推理/规划 → 工具调用 → 输出”的流程，读取工作区内的代码并给出中文解释。

本项目的在线 LLM 接口使用 DeepSeek API，示例模型为 `deepseek-v4-pro`。

## 功能

- 解释工作区内的代码文件，读取结果附带行号。
- 对 Python 文件调用 AST 工具，提取导入、类和函数等确定性结构信息。
- 支持 OpenAI Chat Completions 兼容接口，可配置 DeepSeek、OpenAI 或其他兼容服务。
- 未配置 API Key 时可展示本地工具流程；真实的代码语义解释由在线 LLM 提供。
- 保存最近 4 轮问答作为短期上下文记忆。
- 网络请求超时、异常响应时自动重试两次，并降级到本地规划或给出可操作的错误提示。
- 文件工具限制在项目工作区，拒绝目录外路径、二进制文件和大于 100KB 的文件。

## 环境

- Python 3.10 或更高版本
- 不依赖第三方 Python 包

## 快速开始

在 PowerShell 中运行：

```powershell
Set-Location 'E:\软件工程与项目实践\Homework_1'
python -X utf8 main.py --file examples/sort_numbers.py --question '解释这段代码' --show-steps
```

未配置密钥时会显示“离线回退模式”，用于展示文件读取和 AST 分析流程；该模式不调用大模型，不能替代在线代码解释。

交互式使用：

```powershell
python -X utf8 main.py --file examples/sort_numbers.py --show-steps
```

然后输入：

```text
解释这段代码
解释文件: examples/sort_numbers.py
这个函数为什么要使用 set？
```

输入 `exit` 或 `quit` 结束会话。

## 配置 LLM

本项目使用 Python 标准库调用 OpenAI Chat Completions 兼容接口。项目的在线接口配置与测试使用 DeepSeek API。请先把 `.env.example` 中的变量配置到当前 PowerShell 会话。项目不会自动加载 `.env` 文件，避免引入额外依赖，也避免将密钥写入代码库。

```powershell
$env:LLM_API_KEY = '你的 DeepSeek API Key'
$env:LLM_BASE_URL = 'https://api.deepseek.com'
$env:LLM_MODEL = 'deepseek-v4-pro'
python -X utf8 main.py --file examples/sort_numbers.py --show-steps
```

配置密钥后，Agent 会先让 LLM 选择动作，再执行本地工具，最后让 LLM 依据工具结果回答。`deepseek-v4-pro` 适合追求解释质量；需要较低成本和较快响应时，可使用 `deepseek-flash`。DeepSeek 的接口根地址为 `https://api.deepseek.com`，模型标识见 [DeepSeek 官方模型文档](https://api-docs.deepseek.com/quick_start/pricing/?tab=case-studies)。

### 兼容范围

客户端向 `{LLM_BASE_URL}/chat/completions` 发送请求，并使用 Bearer API Key 认证。因此，它支持所有同时提供 OpenAI Chat Completions 兼容接口、兼容 `model`、`messages` 和 `response_format` 字段的模型服务。

Anthropic Messages API、Gemini 原生 API 等非兼容接口不能仅替换 API Key 直接使用，需要新增专用客户端适配器，或使用服务商提供的 OpenAI 兼容端点。

推荐使用通用的 `LLM_API_KEY`、`LLM_BASE_URL` 和 `LLM_MODEL` 环境变量。项目同时兼容已有的 `OPENAI_API_KEY`、`OPENAI_BASE_URL` 和 `OPENAI_MODEL` 变量。

## Agent 工作流

```text
用户问题
  ↓
规划器（LLM JSON 决策；不可用时使用本地规则）
  ↓
read_file 工具（路径、体积、文本编码安全检查）
  ↓
analyze_python 工具（仅 .py，AST 结构分析）
  ↓
回答器（LLM 依据工具证据回答；不可用时离线说明）
  ↓
短期记忆 + 命令行输出
```

## 命令行参数

| 参数 | 说明 |
| --- | --- |
| `--file PATH` | 启动时关联的项目内代码文件，例如 `examples/sort_numbers.py` |
| `--question TEXT` | 单次提问后退出，适用于演示和脚本调用 |
| `--show-steps` | 输出本次 Agent 的规划和工具调用轨迹 |

文件路径必须相对于项目根目录。工具不会读取项目目录外文件。

## 测试

```powershell
python -X utf8 -m unittest discover -s tests -v
```

测试覆盖文件工具的正常读取、越界阻止、Python AST 解析、离线 Agent 的工具调用路径和通用 LLM 配置读取。单元测试不发送真实 API 请求；项目的在线接口配置使用 DeepSeek API。

## 项目结构

```text
Homework_1/
├── main.py                 # 命令行入口
├── src/
│   ├── agent.py            # Agent 编排与短期记忆
│   ├── llm.py              # Chat Completions 兼容客户端和重试
│   ├── tools.py            # 文件读取与 Python AST 工具
│   ├── fallback.py         # 无密钥时的规划与回答回退
│   └── models.py           # 领域数据模型
├── examples/sort_numbers.py
├── tests/test_tools.py
└── Design.md               # 设计文档
```

详细架构、接口设计和安全边界见 [Design.md](Design.md)。

## 演示建议

1. 运行带 `--show-steps` 的单次命令，展示完整 Agent 轨迹。
2. 在交互模式先问“解释这段代码”，再追问“这个函数为什么要使用 set？”，展示上下文记忆。
3. 输入 `解释文件: ../secret.py`，展示工具对目录越界访问的拒绝。
4. 需要展示 LLM 能力时，配置 API Key 后复现第 1 步，轨迹将显示“LLM 规划”。

## 已知限制

- AST 分析当前仅支持 Python，其他文本代码仍可读取并交给 LLM 解释。
- 离线模式只提供确定性结构说明；高质量逐行语义解释需要配置在线 LLM。
- 本项目不执行用户代码，避免在本地运行不可信代码。
