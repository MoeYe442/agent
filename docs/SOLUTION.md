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

## 9. 增强方向（科研深度）

当前方案实现了基本的 Agent 流水线，但更偏向 Demo 工程。以下 8 个增强方向旨在提升项目的科研属性与研究复现价值。

### 9.1 评测闭环

**现状：** 缺少系统化评测，无法定量衡量输出质量和系统鲁棒性。

**方案：** 新增 `evaluation/` 模块，设计固定评测基准仓库集（含 ground-truth 标注），支撑 4 个核心指标：

| 指标 | 说明 | 计算方式 |
|------|------|----------|
| 仓库理解准确率 (Repo-ACC) | 架构、模块职责、核心抽象是否正确 | 与 ground-truth 对比的关键实体匹配率 |
| 证据引用命中率 (Citation-P) | 结论引用的代码位置/文档是否精确 | 引用的 file:line 在标注集合中的召回+精确 |
| 报告可读性 (Readability) | 结构完整性、逻辑连贯性、术语一致性 | LLM-as-judge 评分（1-5 分量表） |
| 工具失败恢复率 (Recovery-Rate) | 工具调用失败后系统能否自动修复 | 失败后成功重试 / 总失败次数 |

**数据模型：**
```python
class EvalResult(BaseModel):
    repo_name: str
    repo_acc: float
    citation_precision: float
    citation_recall: float
    readability_score: float
    recovery_rate: float
    execution_trace: list[AgentStep]
```

---

### 9.2 Agent 角色契约

**现状：** Agent 之间通过隐式的 LangGraph State 传递数据，缺少结构化契约，边界模糊。

**方案：** 为每个 Agent 定义显式契约 `AgentContract`，明确 5 要素：

```python
class AgentContract(BaseModel):
    agent_role: AgentRole
    input_schema: type[BaseModel]      # 入口数据结构
    output_schema: type[BaseModel]     # 出口数据结构
    failure_conditions: list[str]      # 声明式失败条件
    allowed_tools: list[str]           # 白名单工具集
    quality_gate: dict[str, float]     # 最低通过阈值
```

各 Agent 契约约束如下：

| Agent | 输入 | 输出 | 失败条件 | 专属工具 |
|-------|------|------|----------|----------|
| Planner | 原始 query + repo 元信息 | `PlanStep[]` | 计划为空、步骤不可执行、token 超限 | `read_file`, `list_directory` |
| Researcher | plan + 已有 findings | `Finding[]` + `EvidenceItem[]` | 关键信息缺失、来源不可靠 | `scrape_page`, `RAG.search` |
| CodeReader | plan + 代码索引 | `ProjectIndex` + `EvidenceItem[]` | 符号解析失败率 > 30% | `search_code`, `analyze_call_chain` |
| Executor | plan + 待验证假设 | `ToolCallRecord[]` + 输出 | 命令超时、非零退出码 | `run_command`, `run_python` |
| Reviewer | 完整 AgentState | `ReviewResult` + 回退/通过 | — (始终输出) | 全部只读工具 |
| Reporter | 审核通过的 AgentState | `AnalysisReport` | 必要章节缺失 | `render_markdown`, `export_html` |

---

### 9.3 证据可信度评分

**现状：** `EvidenceItem` 只记录来源路径，缺少可信度维度，报告无法解释"为什么这个结论是可靠的"。

**方案：** 扩展 `EvidenceItem` 模型，增加可信度五元组：

```python
class EvidenceItem(BaseModel):
    # 现有字段
    content: str
    source_path: str
    # 新增：可信度五元组
    confidence_score: float        # 0.0-1.0，综合可信度
    source_type: SourceType        # CODE_FILE | DOC_PAGE | WEB_ARTICLE | TOOL_OUTPUT | AGENT_INFERENCE
    freshness: str                 # "git:commit_hash:2025-01-15" 或 "web:crawl:2025-01-15"
    citation_span: CitationSpan    # {"file": "...", "line_start": 10, "line_end": 25}
    corroboration_count: int       # 被其他独立证据线交叉验证的次数
```

**置信度计算规则：**
- 静态代码分析结果：0.9（高置信，机器可验证）
- 官方文档引用：0.85
- 社区 Wiki/Blog：0.5
- LLM 推理结论：0.4（需交叉验证）
- 过期来源（> 2 年未更新）：置信度 × 0.7 衰减

报告 `Evidence Citations` 章节按置信度排序，标记高风险结论供人工复核。

---

### 9.4 沙箱安全模型

**现状：** `exec_tools` 对可执行命令无限制，存在潜在安全风险。

**方案：** 将命令执行工具按危险等级分级管控：

**L0 — 只读分析命令（默认，无限制）：**
```
ls, find, stat, file, cat, head, tail, wc,
rg, grep, git log, git show, git diff, git status,
pytest --collect-only, python -c "ast.parse(...)"
```

**L1 — 需要用户确认的命令：**
```
pip list, pip show, python script_under_review.py,
git blame, git branch -a
```

**L2 — 需要安全审批的命令（默认禁止）：**
```
pip install, rm, mv, chmod, sudo, docker, curl | sh,
任何涉及网络写入的操作
```

**实现：**
```python
class CommandSafetyGate:
    L0_ALLOWLIST: set[str]   # 自动放行
    L1_CONFIRM: set[str]     # API 确认后放行
    L2_DENY: set[str]        # 全局拒绝

    def classify(self, command: str) -> SafetyLevel
```

所有命令执行前必须通过 `classify()` 分级检查，L2 命令一律拦截并记录审计日志。

---

### 9.5 上下文压缩策略

**现状：** `CONTEXT_COMPRESS_THRESHOLD` 仅设置阈值触发压缩，策略笼统。

**方案：** 将上下文压缩细化为 4 类结构化摘要，Checkpoint 时持久化，恢复时直接注入，而非简单截断：

```python
class ContextSummary(BaseModel):
    task_summary: str                  # 任务目标 + 当前进度 (max 300 tokens)
    key_evidence_summary: list[str]    # 每条 ≤ 80 tokens，最多保留 10 条
    failure_summary: list[str]         # 最近 5 次失败原因 + 修复措施
    next_plan_summary: list[str]       # 下一步待执行步骤 (max 5 步)
    compression_round: int             # 已压缩轮次，防止累积信息丢失
```

压缩时机：
1. 每个 Agent 完成后，压缩其产出摘要
2. 上下文总 token 超过阈值时，触发全局压缩
3. Reviewer 回退时，保留失败摘要，丢弃低分 Agent 的中间推理

---

### 9.6 前端演示控制台

**现状：** 仅通过 API + curl 交互，科研展示缺乏直观的说服力。

**方案：** 新增 `console/` 前端模块，单页 SPA（React + Tailwind CSS），三栏布局：

```
┌────────────┬──────────────────────┬──────────────────┐
│  任务列表   │    Agent 执行时间线    │   证据链 + 报告    │
│            │                      │                  │
│  ● task-1  │  Planner     ████    │  Evidence #1     │
│  ○ task-2  │  Researcher  ██████  │  Evidence #2     │
│  ✓ task-3  │  CodeReader  ███     │  Evidence #3     │
│            │  Executor    ██      │  ...             │
│            │  Reviewer    ███     │                  │
│            │  Reporter    ████    │  [Markdown 报告]  │
│            │                      │                  │
└────────────┴──────────────────────┴──────────────────┘
```

**左侧：** 任务列表，可筛选状态（running / done / failed），每个任务显示进度条
**中间：** 选中任务的 Agent 执行时间线，甘特图风格，显示每个 Agent 的耗时和状态
**右侧：** 两栏切换 — 证据链视图（按可信度排序）和最终 Markdown/HTML 报告视图

通过 SSE 事件流实时更新中间时间线和右侧证据面板。

---

### 9.7 模型路由与降级

**现状：** 全部节点共用 `LLM_MODEL` 单一模型，成本高且缺少容错。

**方案：** 引入 `ModelRouter`，按 Agent 角色和任务难度动态分配模型：

```python
class ModelProfile(str, Enum):
    FAST = "fast"        # 便宜模型，用于简单扫描
    BALANCED = "balanced"  # 中等模型，用于常规推理
    POWERFUL = "powerful"  # 强模型，用于规划和审核
    LONGCTX = "longctx"    # 长上下文模型，用于报告生成

MODEL_ROUTING = {
    AgentRole.PLANNER:    ModelProfile.POWERFUL,   # 任务分解需要强推理
    AgentRole.RESEARCHER: ModelProfile.BALANCED,   # 搜索引擎调用 + 综合
    AgentRole.CODE_READER: ModelProfile.FAST,      # 大量文件扫描
    AgentRole.EXECUTOR:   ModelProfile.FAST,       # 命令执行结果分析
    AgentRole.REVIEWER:   ModelProfile.POWERFUL,   # 质量审核需要强模型
    AgentRole.REPORTER:   ModelProfile.LONGCTX,    # 组装长报告
}
```

**降级策略：**
```
POWERFUL 超时/失败 → BALANCED 重试
BALANCED 超时/失败 → FAST 重试
FAST 超时/失败 → 标记任务为 degraded，人工介入
```

---

### 9.8 可复现实验配置

**现状：** 任务执行依赖隐式环境状态（模型版本、Prompt 模板、工具代码），实验结果不可复现。

**方案：** 引入 `ExperimentManifest`，每次任务执行时冻结全部变量并随报告一起保存：

```python
class ExperimentManifest(BaseModel):
    task_id: str
    started_at: datetime
    model_profiles: dict[str, str]       # AgentRole → model_name
    prompt_versions: dict[str, str]      # AgentRole → prompt git hash
    tool_versions: dict[str, str]        # tool_name → code git hash
    retrieval_params: RetrievalConfig    # BM25 k1/b, vector nprobe, rerank threshold
    repo_snapshots: dict[str, str]       # repo_url → commit_hash
    embedding_model: str
    settings_snapshot: dict[str, str]    # 关键环境变量值（脱敏后）
    seed: int                            # 全局随机种子
```

**输出格式：** 在每个 `AnalysisReport` 的 metadata 中嵌入 `experiment_manifest`，支持：

```bash
# 命令行复现
python scripts/reproduce.py --manifest report_abc123_manifest.json
```

---

### 9.9 实施建议：Vertical Slice 优先

建议不要 8 个方向同时铺开，而是先做一个最小闭环 Vertical Slice：

```
提交本地仓库路径
  → 多 Agent 顺序执行（全部使用简化版 Prompt）
    → 建立代码索引（Jedi AST + BM25）
      → 生成带证据引用的 Markdown 报告（至少 3 个章节）
        → API 查询状态 + 拉取报告
```

这个最小闭环跑通后，再依次补充：
1. Playwright 网页抓取
2. Milvus 向量库切换
3. Redis 队列替换内存队列
4. 前端演示控制台
5. 评测模块 + 实验清单

每个阶段产出可演示成果，避免陷入基础设施集成。上述 9.1-9.8 的增强方向在 Vertical Slice 阶段以"数据模型预留 + 最小实现"方式嵌入，后续逐步深化。
