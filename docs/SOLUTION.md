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

当前方案实现了基本的 Agent 流水线，但更偏向 Demo 工程。以下 8 个增强方向旨在把平台从"能跑的多 Agent 系统"升级为"有方法论、有实验指标、有可解释性的科研演示平台"，支撑答辩、项目展示或论文式汇报。

---

### 9.1 评测闭环

**研究动机：** 多 Agent 系统常见的问题是"跑通了但是没法证明好在哪里"。评测闭环是这个增强方案的核心——让平台不光"能做分析"，还能"说出做得多好"。

#### 评测集设计

评测集按项目规模和复杂度分为三个等级，每级包含 3-5 个代表性开源项目：

| 等级 | 典型项目 | 代码量 | 特殊挑战 |
|------|----------|--------|----------|
| **L1 — 小型工具库** | requests / flask / rich | 10K-50K 行 | 入口单一，测试基础覆盖 |
| **L2 — 中型应用** | fastapi / celery / sentry-sdk | 50K-200K 行 | 多模块协作，异步/插件体系 |
| **L3 — 大型复杂项目** | django / airflow / pandas | 200K+ 行 | 多层次抽象，C扩展，多语言 |

每个项目预先定义 15-25 个标准问题，覆盖 5 个分析维度：

```
标准问题维度：
  1. 入口与启动路径（2-4 题）
     例："项目的 main() 入口在哪里？启动时依次初始化了哪些组件？"
  2. 核心模块职责（3-6 题）
     例："请求处理管道如何实现？中间件链的顺序是什么？"
  3. 数据流与状态管理（3-5 题）
     例："用户 session 的完整生命周期是怎样的？"
  4. 外部依赖与风险（3-5 题）
     例："最关键的第三方依赖是什么？当前版本有哪些已知漏洞？"
  5. 设计模式与架构权衡（2-4 题）
     例："为什么选择这种抽象而非另一种？有哪些历史遗留问题？"
```

#### 评测指标体系

每位评估对象的评测指标分为 4 类共 8 项：

**A. 正确性指标：**
| 指标 | 含义 | 计算方式 |
|------|------|----------|
| 仓库结构识别准确率 | 关键模块、包、文件是否被正确识别 | 与 ground-truth 对比的关键实体匹配率 |
| 关键文件召回率 | 分析是否覆盖了所有关键源代码文件 | 报告中引用的关键文件 / 标注关键文件总数 |
| 证据引用命中率 | 报告的每个结论是否有精确的代码/文档引用 | 带正确 file:line 引用的结论 / 总结论数 |

**B. 可解释性指标：**
| 指标 | 含义 | 计算方式 |
|------|------|----------|
| 报告结论可追溯率 | 每个关键结论能否逆向追溯到原始证据 | 可追溯到 code/doc/web 来源的结论占比 |
| 幻觉检测 | 报告中出现的不存在于仓库中的文件名、函数名 | LLM-as-judge 对比报告与索引，统计幻觉数 |

**C. 鲁棒性指标：**
| 指标 | 含义 | 计算方式 |
|------|------|----------|
| Agent 执行成功率 | 单次任务中 6 个 Agent 全部正常完成的比率 | 全部完成的任务数 / 总任务数 |
| 工具失败恢复率 | 工具调用失败后系统是否能自动恢复 | 失败后成功重试次数 / 总失败次数 |

**D. 效率指标：**
| 指标 | 含义 | 计算方式 |
|------|------|----------|
| 平均任务耗时 | 从任务提交到报告生成的总时间 | 按仓库规模分组统计 |
| 上下文压缩 token 降幅 | 压缩后上下文长度 vs 压缩前的比例 | (压缩后 tokens / 压缩前 tokens) × 100% |

#### 数据模型

```python
class EvalQuestion(BaseModel):
    question_id: str
    dimension: str            # 入口路径 | 模块职责 | 数据流 | 依赖风险 | 设计模式
    text: str
    ground_truth: GroundTruth
    # GroundTruth 包含：期望的关键文件列表、关键函数/类名、
    # 预期引用位置 (file:line)、预期结论要点

class EvalResult(BaseModel):
    repo_name: str
    repo_level: str           # L1 | L2 | L3
    repo_commit: str
    # 正确性
    structure_accuracy: float
    key_file_recall: float
    citation_precision: float
    # 可解释性
    conclusion_traceability: float
    hallucination_count: int
    # 鲁棒性
    agent_success_rate: float
    tool_recovery_rate: float
    # 效率
    avg_task_duration_seconds: float
    context_compression_ratio: float
    # 轨迹
    execution_trace: list[AgentStep]
    model_token_usage: dict[str, int]
```

#### 目标基线

评测报告可以生成类似以下结论：

> 在 10 个开源项目（L1×3、L2×4、L3×3）的评测中，本平台平均：
> - 从代码仓库到结构化报告耗时 **8-15 分钟**（人工初步理解通常需 2-4 小时）
> - 证据可追溯率达到 **85%+**
> - 仓库结构识别准确率 **92%+**
> - 关键文件召回率 **78%+**
> - 工具失败后自动恢复成功率 **65%+**

---

### 9.2 Agent 角色契约

**研究动机：** 当前 Agent 之间通过隐式的 LangGraph State 传递数据，缺少结构化契约。多 Agent 系统中的"分工边界模糊"是最容易被质疑的点——凭什么这个结论是 Researcher 出的？CodeReader 为什么没看到那段关键代码？

角色契约的核心思想：**每个 Agent 是一个被约束的角色，不是自由的 AI**。通过显式契约实现可解释的、可审计的分工。

#### 契约定义

```python
class AgentContract(BaseModel):
    agent_role: AgentRole
    description: str                # 角色定位，一句话说清职责
    input_schema: type[BaseModel]   # 入口数据结构
    output_schema: type[BaseModel]  # 出口数据结构
    allowed_tools: list[str]        # 白名单工具集（不能调用白名单外工具）
    forbidden_actions: list[str]    # 明确禁止的操作
    failure_conditions: list[str]   # 声明式失败条件
    fallback_behavior: str          # 失败时的交接策略
    quality_gate: dict[str, float]  # 最低通过阈值
```

#### 各 Agent 契约约束

**Planner — 规划者**

| 维度 | 内容 |
|------|------|
| **定位** | 只负责拆解任务、制定路线，不直接分析代码，不下结论 |
| **输入** | 原始 query + repo 元信息（README、目录结构、语言/框架标识） |
| **输出** | `PlanStep[]` — 每步含目标、建议工具、预期产出、依赖关系（DAG） |
| **允许工具** | `read_file`（仅限 README/配置文件）、`list_directory` |
| **禁止行为** | 直接分析源代码逻辑；推断架构结论；调用搜索引擎 |
| **失败条件** | 计划为空；某步骤不可执行（缺少前置技能/工具）；token 超限 |
| **交接策略** | 输出计划 DAG，标记"待 Researcher 补充外部信息"和"待 CodeReader 深入分析" |
| **质量门禁** | 计划步骤数 ≥ 3；每步有明确的预期产出描述 |

**Researcher — 调研者**

| 维度 | 内容 |
|------|------|
| **定位** | 负责外部信息搜集：网页文档、GitHub Issues、官方文档、社区讨论，不分析私有代码逻辑 |
| **输入** | plan + 已有的 findings（支持增量调研） |
| **输出** | `Finding[]` + `EvidenceItem[]`（每条带来源和可信度初评） |
| **允许工具** | `scrape_page`, `RAG.search`, `read_file`（仅限文档类文件） |
| **禁止行为** | 对代码内部逻辑下结论（那是 CodeReader 的职责）；引用不可靠来源不标注 |
| **失败条件** | 关键外部信息完全缺失；所有来源被判定为不可靠 |
| **交接策略** | 输出 findings + evidence，标记"以下结论依赖外部来源，需 CodeReader 从代码侧交叉验证" |
| **质量门禁** | 每条 finding 至少关联 1 条 evidence；来源类型明确标注 |

**CodeReader — 代码分析者**

| 维度 | 内容 |
|------|------|
| **定位** | 深度代码分析：入口路径、模块结构、调用链、依赖关系、设计模式识别，这是系统的核心分析引擎 |
| **输入** | plan + 代码索引（Jedi AST 符号表）+ Researcher 的外部 findings |
| **输出** | `ProjectIndex` + `EvidenceItem[]`（含精确的 file:line 引用）+ 调用链图 |
| **允许工具** | `search_code`, `analyze_call_chain`, `read_file`（源代码文件） |
| **禁止行为** | 猜测不存在的代码路径；执行命令；浏览网页 |
| **失败条件** | 符号解析失败率 > 30%；无法定位核心入口模块 |
| **交接策略** | 对"无法从静态分析确认的运行时行为"标记为推测，交由 Executor 验证 |
| **质量门禁** | 每个关键结论至少引用 1 处代码位置（file:line）；入口模块必须被正确定位 |

**Executor — 验证执行者**

| 维度 | 内容 |
|------|------|
| **定位** | 只读验证：运行静态检查命令、执行只读分析脚本、收集中间结果 |
| **输入** | plan + 待验证假设 + CodeReader 标记的"需运行时确认"项 |
| **输出** | `ToolCallRecord[]` + 命令输出原文 + 执行是否成功 |
| **允许工具** | `run_command`（仅限白名单命令） |
| **禁止行为** | 修改仓库文件；安装依赖；运行未审查的代码 |
| **失败条件** | 命令超时（> 30s）；非零退出码；命令不在白名单中 |
| **交接策略** | 输出原始命令输出，不做推断（让 Reviewer 判断输出的含义） |
| **质量门禁** | 每个 tool call 有完整记录（命令原文 + stdout + stderr + 退出码） |

**Reviewer — 质量门禁**

| 维度 | 内容 |
|------|------|
| **定位** | 质量审核者：检查幻觉、证据覆盖不足、结论逻辑冲突、章节完整性。这是系统的质量保证核心 |
| **输入** | 完整的 AgentState（所有 Agent 的输入/输出 + 证据链） |
| **输出** | `ReviewResult`（通过/回退 + 评分 + 具体问题清单 + 建议修复方向） |
| **允许工具** | 全部只读工具（用于抽样验证证据真实性） |
| **禁止行为** | 生成新的分析结论；修改上游 Agent 的产出 |
| **失败条件** | —（始终输出审核结果，不允许自身失败） |
| **质量门禁** | 得分 ≥ 0.6 才放行到 Reporter |

Reviewer 的核心判断逻辑：

```
审核维度：
  1. 幻觉检测：报告中提到的文件名、函数名、类名是否真实存在于仓库
  2. 证据覆盖：每个关键结论是否有对应证据支撑
  3. 逻辑一致性：Plan 中的步骤是否都被覆盖、不同 Agent 的结论是否矛盾
  4. 完整性：所有必要的分析维度是否都有覆盖
  5. 标注质量：推测性结论是否明确标注为推测

放行规则：
  得分 ≥ 0.8 → 直接通过
  0.6 ≤ 得分 < 0.8 → 通过但标记改进点
  得分 < 0.6 → 回退（指定回退到的节点 + 具体问题 + 修复建议）
  连续回退 > 2 次 → 标记为 degraded 并生成简化报告
```

**Reporter — 报告生成者**

| 维度 | 内容 |
|------|------|
| **定位** | 报告组装者：将审核通过的 AgentState 组装为结构化报告。不允许生成任何无证据支撑的结论 |
| **输入** | 审核通过的 AgentState（证据链 + findings + 调用链 + 工具输出） |
| **输出** | `AnalysisReport`（7 章节 + 证据引用 + 推测标记） |
| **允许工具** | `render_markdown`, `export_html` |
| **禁止行为** | 生成任何无证据引用的结论；对 Reviewer 已标记问题的结论不加标注 |
| **失败条件** | 必要章节缺失（覆盖率 < 50%） |
| **质量门禁** | 每个章节 ≥ 1 条证据引用；推测性结论必须含有 "⚠️ 推测：" 前缀 |

---

### 9.3 证据链可信度

**研究动机：** 多 Agent 项目最容易被质疑的是"报告是不是编的"——如果每个结论都像凭空而来，就没有科研价值。证据链是这个平台可解释性的基石。

#### 证据数据结构

每条证据保存为可独立检索、可交叉验证的结构化记录：

```json
{
  "evidence_id": "ev_001",
  "source_type": "code | document | web | tool_call",
  "source_uri": "src/main.py",
  "line_range": {"start": 24, "end": 86},
  "content_excerpt": "app = FastAPI(title=\"CodeResearch\")...",
  "related_claim": "系统入口位于 FastAPI app 初始化逻辑",
  "confidence_score": 0.87,
  "collected_by": "CodeReader",
  "collected_at": "2026-06-26T10:30:45Z",
  "tool_call_id": "tool_123",
  "corroboration_count": 2,
  "cross_references": ["ev_005", "ev_012"]
}
```

#### 可信度计算规则

| 来源类型 | 基准置信度 | 说明 |
|----------|-----------|------|
| 静态代码分析（Jedi AST 直接解析） | 0.90 | 机器可验证，误判率极低 |
| 官方文档直引（readthedocs / docs.rs / pkg.go.dev） | 0.85 | 权威来源 |
| Git 提交记录 / 变更日志 | 0.80 | 历史事实 |
| 非官方文档 / 技术博客 | 0.50 | 可能有偏差 |
| 社区讨论（GitHub Issues / Stack Overflow） | 0.45 | 需要交叉验证 |
| LLM 推理结论（无直接代码/文档支撑） | 0.40 | 必须标记为推测 |

**衰减因子：**
- 来源超过 2 年未更新：× 0.7
- 来源被单次引用（无交叉验证）：× 0.85
- 引用位置不够精确（无行号）：× 0.90

**增强因子：**
- 被 2+ 条独立证据交叉验证：+ 0.10（上限 0.95）
- 代码分析 + 官方文档双重确认：+ 0.05

#### 报告中的证据呈现

最终报告中的每个关键结论都应能反查到证据。示例：

```
项目采用 FastAPI 作为 HTTP 服务入口 [ev_001]，
通过 Lifespan 管理 Redis 连接的生命周期 [ev_004]。
中间件栈包括 CORS、RequestID 和异常处理 [ev_007]。

⚠️ 推测：系统可能在高负载下存在 Redis 连接池耗尽风险 [ev_015]，
该推测基于默认连接池大小设置，未发现显式的连接池上限配置。
```

报告 `Evidence Citations` 章节按可信度从高到低排序，高风险结论（置信度 < 0.5）单独列出，供人工复核。

---

### 9.4 上下文压缩与长期记忆

**研究动机：** 多轮 Agent 执行中，最大问题是上下文膨胀——前一轮的完整思考链条在下一轮中大多无用，却占据大量 token。这不仅是成本问题，还会导致模型注意力分散。

#### 四类结构化记忆

多轮推理过程中，已有内容不再以大段原文进行，而是改为四种结构化的记忆摘要：

**Task Memory（任务记忆）：**
```
内容：任务目标 + 用户原始问题 + 当前执行阶段 + 已完成步骤
容量：≤ 300 tokens
更新频率：每个 Agent 完成后更新当前阶段
作用：确保所有 Agent 始终知道"我们要做什么、做到哪了"
```

**Evidence Memory（证据记忆）：**
```
内容：已确认的关键证据摘要（每条 ≤ 80 tokens，最多保留 15 条）
容量：≤ 1200 tokens
更新频率：每个 Agent 产出新证据时追加，被 Reviewer 驳回的证据删除
作用：避免后续 Agent 重新检索已找到的证据
排序规则：按可信度降序，低可信度证据在容量不足时优先淘汰
```

**Failure Memory（失败记忆）：**
```
内容：最近 5 次工具调用失败 / Agent 回退的原因 + 修复措施
容量：≤ 400 tokens
更新频率：每次失败时追加
作用：让后续 Agent 避免重复同样的错误
过期策略：保留最近 5 条，旧记录自动丢弃
```

**Plan Memory（计划记忆）：**
```
内容：下一步待执行步骤 + 待验证假设
容量：≤ 400 tokens
更新频率：每步完成后划掉已完成项
作用：跟踪计划的执行进度
```

#### 压缩触发策略

| 触发条件 | 操作 |
|----------|------|
| 每个 Agent 完成后 | 仅压缩该 Agent 的中间推理，保留产出（findings / evidence / tool outputs） |
| 上下文 token > 阈值的 80% | 触发全局压缩：将所有 Agent 的中间推理替换为上述 4 类摘要 |
| Reviewer 回退时 | 保留 Failure Memory，丢弃被回退 Agent 的中间推理 |

#### 量化效果

预期上下文管理效果：
- 上下文长度平均降低 **35%-50%**
- 关键证据保留率 **≥ 95%**（已写入 Evidence Memory 的不丢失）
- 计划跟踪准确率不受影响（Plan Memory 保持 DAG 结构）

---

### 9.5 工具安全与沙箱

**研究动机：** 平台涉及命令执行和仓库分析，不能"让 LLM 随便执行命令"。这个增强方向证明平台有工程安全意识，不是简单套壳。

#### 三级权限体系

```python
class ToolPermission(enum.Enum):
    READ_ONLY = "read_only"          # 默认开放
    NETWORK_READ = "network_read"    # 需确认
    RESTRICTED = "restricted"        # 默认禁止
```

**权限明细：**

| 权限级别 | 典型工具 | 策略 |
|----------|----------|------|
| **READ_ONLY** | `read_file`, `search_code`, `list_directory`, `git log/show/diff/status`, `rg`, `grep`, `cat`, `head`, `tail`, `wc` | 自动放行，不拦截 |
| **NETWORK_READ** | `scrape_page` (Playwright), `github_api (GET)`, `gh issue view`, `gh pr view` | 默认允许但限制频率（≤ 10 req/min），超出后冷却 60s |
| **RESTRICTED** | `run_command`, `pip install`, `rm`, `mv`, `chmod`, `sudo`, `docker`, 任何 `curl \| sh` 模式 | 默认拒绝，仅允许白名单内的只读分析命令 |

#### 命令白名单（Executor 专用）

```
允许的命令（只读分析范畴）：
  rg [pattern] [path]              — 代码搜索
  git grep [pattern]               — Git 搜索
  git log --oneline -n [N]         — 提交历史
  git diff [commit] [commit]       — 变更对比
  python -c "ast.parse(...)"       — AST 解析检查
  pytest --collect-only            — 测试收集（不执行）
  pip list                         — 列出已安装包
  pip show [package]               — 查询包信息
  tree -L [N]                      — 目录结构

拒绝的命令：
  任何包含 | sh / | bash / | python - 的管道执行
  pip install / npm install / cargo install
  rm / mv / chmod / chown / sudo / docker
  任何网络写入命令（curl POST / wget）
```

#### 安全架构

```python
class ToolSafetyGate:
    """工具调用安全门——所有工具调用必须经过此门"""

    L0_ALLOWLIST: set[str]    # READ_ONLY — 自动放行
    L1_RATELIMIT: set[str]    # NETWORK_READ — 频率限制
    L2_DENY: set[str]         # RESTRICTED 中明确拒绝的命令模式

    def audit(self, tool_name: str, params: dict) -> AuditResult:
        """
        返回：
          - ALLOWED: 放行
          - RATE_LIMITED: 频率限制触发，拒绝
          - DENIED: 命令不在白名单中，拒绝并记录审计日志
          - CONFIRM_REQUIRED: 需要人工/API 确认
        """
```

所有工具调用记录入审计日志（`audit_log`）：时间、工具名、参数、权限判断结果、执行结果。

---

### 9.6 模型路由与成本控制

**研究动机：** 所有 Agent 用同一个模型不仅成本高，也不符合实际——规划需要深度推理，代码扫描量大但不需要复杂推理。差异化模型分配是工程优化，不是炫技。

#### ModelRouter 设计

```python
class ModelProfile(str, Enum):
    FAST = "fast"            # 低成本模型（如 gpt-4o-mini），大量扫描
    BALANCED = "balanced"    # 中等模型（如 gpt-4o），常规推理
    POWERFUL = "powerful"    # 强推理模型（如 claude-sonnet-4-6），规划+审核
    LONGCTX = "longctx"      # 长上下文模型（128K+ tokens），报告生成

MODEL_ROUTING = {
    AgentRole.PLANNER:    ModelProfile.POWERFUL,   # 任务分解需强推理能力
    AgentRole.RESEARCHER: ModelProfile.BALANCED,   # 搜索+综合，平衡成本
    AgentRole.CODE_READER: ModelProfile.FAST,      # 大量文件扫描，量大于质
    AgentRole.EXECUTOR:   ModelProfile.FAST,       # 命令结果分析，简单任务
    AgentRole.REVIEWER:   ModelProfile.POWERFUL,   # 质量审核不可降级
    AgentRole.REPORTER:   ModelProfile.LONGCTX,    # 长报告组装
}
```

#### 降级链路

```
POWERFUL 调用失败/超时 → 自动降级为 BALANCED 重试（最多 1 次）
BALANCED 调用失败/超时 → 自动降级为 FAST 重试（最多 1 次）
FAST 调用失败/超时     → 标记当前 Agent 为 degraded，跳过并通知 Reviewer
连续 3 次降级           → 终止任务，生成 partial 报告
```

#### 成本追踪

每个任务结束后记录：

| 追踪项 | 字段 |
|--------|------|
| 按 Agent 分解 | 每个 Agent 使用的模型、token 消耗（prompt + completion）、耗时 |
| 按模型汇总 | 各模型的调用次数、总 token、总耗时 |
| 失败统计 | 降级次数、模型超时次数、接口错误次数 |

这些数据可生成成本分析报告，支撑后续的模型选型优化。

---

### 9.7 前端演示控制台

**研究动机：** 后端能力再强，展示时只有 API + curl 就不直观。"多 Agent 协作"在科研展示中需要可视化——让观众看到 Agent 一个一个在跑、证据一条一条在产出。

#### 布局设计

```
┌─────────────┬───────────────────────┬───────────────────────┐
│  任务面板    │   Agent 执行时间线      │   证据链查看器          │
│             │                       │                       │
│  新建任务    │  Planner     ████░░   │  [代码] [文档] [网页]  │
│  ─────────  │  Researcher  ██████   │                       │
│  ● running  │  CodeReader  ███░░░   │  ev_001  0.90        │
│  ○ queued   │  Executor    ██░░░░   │  src/main.py:24       │
│  ✓ done     │  Reviewer    ████░░   │  "app = FastAPI(..)"  │
│  ✗ failed   │  Reporter    ████░░   │                       │
│             │                       │  ev_002  0.85        │
│  ─────────  │                       │  docs/api.md:12       │
│  状态筛选:   │                       │  "POST /tasks ..."    │
│  全部       │                       │                       │
│  运行中     │                       │  ...                  │
│  已完成     │                       │                       │
│  失败       │                       │                       │
│             │                       │                       │
└─────────────┴───────────────────────┴───────────────────────┘
│                     最终报告视图                              │
│  [Markdown 渲染] [HTML 预览] [下载]                           │
│  ## Project Overview                                        │
│  CodeResearch Agent is a multi-agent platform...             │
│  [ev_001] [ev_003]                                          │
│  ## Core Architecture                                       │
│  ...                                                        │
└─────────────────────────────────────────────────────────────┘
```

#### 四大面板

| 面板 | 功能 | 交互 |
|------|------|------|
| **任务面板**（左上） | 创建新任务、查看任务列表、按状态筛选、显示进度百分比 | 点击任务切换到该任务的详情 |
| **时间线**（中上） | 6 个 Agent 的甘特图式时间线，实时展示当前执行到哪个 Agent、每个 Agent 耗时 | SSE 实时更新，已完成/运行中/等待中/失败用不同颜色 |
| **证据链**（右上） | 按来源类型分 tab（代码/文档/网页/工具输出），每条可展开查看详情 | 点击证据高亮报告中的对应引用 |
| **报告视图**（底部） | Markdown 渲染的报告全文，证据引用以链接形式展示，推测以黄色高亮 | 点击 `[ev_xxx]` 跳转到对应证据 |

#### 技术选型

- **框架：** React 18 + TypeScript
- **样式：** Tailwind CSS
- **状态管理：** React Query（SSE 事件流）
- **图表：** Recharts（时间线甘特图）
- **Markdown 渲染：** react-markdown + rehype-highlight

---

### 9.8 可复现实验配置

**研究动机：** 科研成果最怕不可复现——"上次能跑的有这个结论，这次怎么变了？"回答不了这个问题就不够科研。

#### Run Manifest 设计

每次任务执行时冻结全部变量，生成 `RunManifest` 并随报告一起持久化：

```json
{
  "task_id": "task_abc123",
  "repo_url": "https://github.com/psf/requests",
  "repo_commit": "abc123def456",
  "model_profile": "research-demo-v1",
  "model_assignments": {
    "planner": "claude-sonnet-4-6",
    "researcher": "gpt-4o",
    "code_reader": "gpt-4o-mini",
    "executor": "gpt-4o-mini",
    "reviewer": "claude-sonnet-4-6",
    "reporter": "claude-sonnet-4-6"
  },
  "prompt_versions": {
    "planner": "git:abc123:src/agents/planner.py",
    "researcher": "git:def456:src/agents/researcher.py"
  },
  "rag_config": {
    "chunk_size": 800,
    "chunk_overlap": 200,
    "top_k": 8,
    "bm25_k1": 1.5,
    "bm25_b": 0.75,
    "rerank_enabled": true,
    "rerank_top_n": 5
  },
  "embedding_model": "text-embedding-3-small",
  "retrieval_mode": "bm25_only",
  "settings_snapshot": {
    "llm_api_base": "https://api.openai.com/v1",
    "llm_model": "gpt-4o",
    "max_retries": 2,
    "context_compress_threshold": 32000,
    "task_timeout_seconds": 3600
  },
  "random_seed": 42,
  "started_at": "2026-06-26T10:30:00Z",
  "completed_at": "2026-06-26T10:42:15Z"
}
```

#### 复现能力

```bash
# 基于 manifest 复现实验结果
python scripts/reproduce.py \
  --manifest reports/task_abc123_manifest.json \
  --output reports/task_abc123_rep2.json

# 对比两次实验结果
python scripts/compare_reports.py \
  reports/task_abc123_manifest.json \
  reports/task_abc123_rep2.json
```

#### 扩展为实验表格

可设计参数扫描实验：

| 实验组 | chunk_size | top_k | rerank | 结构准确率 | 召回率 | 平均耗时 |
|--------|-----------|-------|--------|-----------|--------|---------|
| A | 500 | 5 | off | 85% | 72% | 8min |
| B | 500 | 10 | off | 87% | 76% | 10min |
| C | 800 | 8 | on | 92% | 82% | 12min |
| D | 1000 | 5 | on | 89% | 78% | 11min |

这类实验表格可以支撑论文中的"参数敏感性分析"和"消融实验"。

---

## 10. 实施路线图

### 第一阶段：核心竞争力（优先实现）

这 4 项是让平台从 Demo 升级为"科研演示"的关键：

| 优先级 | 增强项 | 关键交付物 | 预期科研价值 |
|--------|--------|-----------|-------------|
| **P0** | Agent 角色契约 | `AgentContract` 数据模型 + 每个 Agent 的显式契约定义 + Reviewer 质量门禁 | 解决"分工为什么合理"的问题，可论证的架构设计 |
| **P0** | 证据链可信度 | `EvidenceItem` 扩展 + 置信度计算器 + 报告中证据可视化 | 解决"结论是不是编的"问题，可解释性的核心 |
| **P1** | 上下文压缩 | 4 类结构化 Memory + 压缩触发逻辑 + token 用量统计 | 支撑长任务、大仓库分析，量化展示效率优势 |
| **P1** | 评测闭环 | `evaluation/` 模块 + 3 级评测集 + 8 项指标 + 基准报告 | 解决"系统好不好"的问题，提供定量数据 |

### 第二阶段：展示与工程深度

在第一阶段完成后，补充工程和展示层面：

| 优先级 | 增强项 | 关键交付物 | 预期科研价值 |
|--------|--------|-----------|-------------|
| **P2** | 前端演示控制台 | React SPA 四栏布局 + SSE 实时更新 | 支撑答辩/项目展示，直观呈现多 Agent 协作 |
| **P2** | 模型路由 | `ModelRouter` + 降级链路 + 成本追踪 | 展示工程化调度能力，提供成本分析数据 |
| **P3** | 工具沙箱 | `ToolSafetyGate` + 三级权限 + 审计日志 | 安全基线论证，说明工程安全意识 |
| **P3** | 可复现实验 | `RunManifest` + `reproduce.py` + 实验对比脚本 | 支撑方法论章节，实验可复现是科研基本要求 |

### 最终项目定位

> 我设计并实现了一个面向开源项目理解的可解释多智能体研究平台。
> 通过**角色化 Agent 契约**实现有边界的分工协作，
> 通过**结构化证据链**保证每个结论可追溯、可验证，
> 通过 **RAG 检索增强**（BM25 + 向量混合搜索）提升分析覆盖度，
> 通过**上下文压缩与结构化记忆**解决多轮执行中的 token 膨胀问题，
> 通过**可复现实验配置**保证科研结果可验证。
> 平台实现了从仓库输入到可信分析报告生成的自动化闭环，
> 在评测基准上达到了 [X] 的结构识别准确率和 [Y] 的证据可追溯率。
