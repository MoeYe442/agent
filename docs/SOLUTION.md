# CodeResearch Agent — 方案文档

## 1. 项目概述

CodeResearch Agent 是一个面向大型开源项目代码仓库与网页情报的多智能体分析平台（科研演示版）。用户提交研究问题 + 仓库地址后，系统自动调度多个 AI Agent 协作完成：仓库解析 → 网页采集 → 代码深度分析 → 证据整理 → 审核 → 报告生成。

## 2. 系统架构

```
┌──────────────────────────────────────────────────────────┐
│                      FastAPI 网关层                       │
│  POST /tasks  GET /tasks/:id  GET /events  GET /reports  │
├──────────────────────────────────────────────────────────┤
│                     LangGraph 编排层                      │
│  Planner → Researcher → CodeReader → Executor → Reviewer │
│                                    ↑          ↓          │
│                              (低分回环)    Reporter       │
├──────────────┬──────────────┬────────────────────────────┤
│  Agent 节点   │   RAG 管道    │      工具层 (MCP)          │
│  - planner   │  - chunker   │  - 文件读写 / 代码搜索     │
│  - researcher│  - BM25索引  │  - Playwright 网页抓取     │
│  - code_reader│ - 向量检索  │  - GitHub 仓库克隆         │
│  - executor  │  - 混合搜索  │  - 命令执行 (沙箱)         │
│  - reviewer  │  - rerank    │  - 报告渲染                │
│  - reporter  │              │                            │
├──────────────┴──────────────┴────────────────────────────┤
│                    基础设施层                              │
│  Redis (状态/队列)  Milvus (向量库)  SQLite (Checkpoint) │
│  etcd (协调)        MinIO (对象存储)                      │
└──────────────────────────────────────────────────────────┘
```

## 3. 技术栈

| 层级 | 技术 | 用途 |
|------|------|------|
| Web 框架 | FastAPI + Uvicorn | HTTP API + SSE |
| Agent 编排 | LangGraph (StateGraph) | 多 Agent 状态机 + Checkpoint |
| LLM 接入 | httpx + tenacity | OpenAI 兼容 API (可切换) |
| 任务队列 | Redis (lists + pub/sub) | 任务调度 + 事件推送 |
| 向量数据库 | Milvus (etcd + MinIO) | 代码片段稠密向量存储 |
| 网页采集 | Playwright | 无头浏览器抓取 SPA 页面 |
| 代码分析 | Jedi | Python 静态分析 (符号/调用链) |
| 嵌入模型 | sentence-transformers | 本地/API 文本向量化 |
| 混合检索 | rank-bm25 + Milvus | BM25 + 向量 + cross-encoder rerank |
| 容器化 | Docker Compose | 基础设施一键部署 |
| Python | >= 3.12 | 类型提示 + async/await |

## 4. Agent 角色定义

| 角色 | 职责 | 可用工具 |
|------|------|----------|
| Planner | 解析研究问题，制定分步计划 | read_file, list_directory |
| Researcher | 搜集背景信息、网页资料 | scrape_page, RAG.search, read_file |
| CodeReader | 深度代码分析、调用链追踪 | read_file, search_code, analyze_call_chain |
| Executor | 执行验证命令、运行代码片段 | run_command, run_python |
| Reviewer | 质量审核，评分，决定是否回退 | 全部只读工具 |
| Reporter | 组装结构化分析报告 | render_markdown, export_html |

## 5. 数据流

```
TaskSpec (用户提交)
  → TaskRecord (Redis 持久化)
    → AgentState (LangGraph 状态机)
      → Planner: 产出 plan[]
        → Researcher: 搜集 findings[] + evidence[]
          → CodeReader: 构建 ProjectIndex + evidence[]
            → Executor: 执行验证 tool_log[]
              → Reviewer: review_score + 通过/回退决策
                → Reporter: AnalysisReport (7章节 + citations)
                  → Redis/文件存储
                    → API 返回 (JSON/Markdown/HTML)
```

## 6. 报告结构

`AnalysisReport` 包含以下标准章节：
1. **Project Overview** — 从 README + 目录结构提取
2. **Tech Stack Identification** — 从配置文件识别
3. **Core Architecture** — 模块划分 + 核心抽象
4. **Key Code Paths** — 关键函数调用链
5. **Business Logic / Data Flow** — 业务流程梳理
6. **Dependencies and Risks** — 依赖分析 + 风险点
7. **Evidence Citations** — 所有结论的证据回溯

## 7. API 接口

| 方法 | 路径 | 输入 | 输出 |
|------|------|------|------|
| `POST` | `/tasks` | `TaskSpec` | `{task_id, status}` |
| `GET` | `/tasks/{task_id}` | — | `TaskRecord` |
| `GET` | `/tasks/{task_id}/events` | — | SSE 事件流 |
| `GET` | `/reports/{task_id}?format=` | — | JSON/Markdown/HTML |
| `GET` | `/evidence/{task_id}?source_type=` | — | `EvidenceChain` |
| `POST` | `/tools/register` | MCP 工具定义 | `{tool_name, status}` |
| `GET` | `/health` | — | `{status: "ok"}` |

## 8. 配置项

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `REDIS_URL` | `redis://localhost:6379/0` | Redis 连接 |
| `MILVUS_HOST` | `localhost` | Milvus 地址 |
| `MILVUS_PORT` | `19530` | Milvus 端口 |
| `MILVUS_COLLECTION_NAME` | `code_research` | 向量集合名 |
| `LLM_API_BASE` | `https://api.openai.com/v1` | LLM API 端点 |
| `LLM_API_KEY` | — | API Key |
| `LLM_MODEL` | `gpt-4o` | 模型名称 |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | 嵌入模型 |
| `EMBEDDING_DIM` | `384` | 嵌入维度 |
| `CONTEXT_COMPRESS_THRESHOLD` | `32000` | 上下文压缩阈值 (tokens) |
| `TASK_TIMEOUT_SECONDS` | `3600` | 单任务超时 (秒) |
| `MAX_RETRIES` | `2` | LLM API 最大重试 |
