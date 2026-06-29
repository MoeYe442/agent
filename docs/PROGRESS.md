# CodeResearch Agent — 开发进度

## 完成状态一览

| 阶段 | 内容 | 状态 | 开始时间 | 完成时间 |
|------|------|------|----------|----------|
| 基础 | 项目脚手架、数据模型、基础设施 | ✅ 完成 | — | — |
| Phase 1 | 工具层 + 仓库分析器 | ✅ 完成 | 2026-06-24 | 2026-06-24 |
| Phase 2 | RAG 管道 | ✅ 完成 | 2026-06-24 | 2026-06-24 |
| Phase 3 | Agent 节点 | ✅ 完成 | 2026-06-24 | 2026-06-24 |
| Phase 4 | LangGraph 工作流 | ✅ 完成 | 2026-06-24 | 2026-06-24 |
| Phase 5 | API 路由 | ✅ 完成 | 2026-06-24 | 2026-06-24 |
| Phase 6 | 稳定性增强 | ✅ 完成 | 2026-06-24 | 2026-06-24 |
| Phase 7 | 集成测试 + 演示 | ✅ 完成 | 2026-06-24 | 2026-06-24 |
| Phase 8 | Vertical Slice 最小闭环 | ✅ 完成 | 2026-06-25 | 2026-06-26 |
| Phase 9 | Bug 修复 + 方案文档升级 | ✅ 完成 | 2026-06-26 | 2026-06-26 |

## 已完成模块

### 数据模型 (`src/models/`)
- [x] `enums.py` — AgentRole, TaskPhase, SourceType
- [x] `task.py` — TaskStatus, TaskSpec, TaskRecord
- [x] `tool_call.py` — ToolCallRecord
- [x] `evidence.py` — EvidenceItem, EvidenceChain
- [x] `code_index.py` — CodeIndexItem, ProjectIndex
- [x] `rag.py` — RagChunk, SearchQuery, RetrievalResult
- [x] `report.py` — Citation, ReportSection, AnalysisReport
- [x] `agent_state.py` — AgentState (LangGraph TypedDict)

### 基础设施 (`src/infrastructure/`)
- [x] `llm.py` — LLMClient (chat/embed/stream + retry)
- [x] `milvus.py` — MilvusClientWrapper (collection/search)
- [x] `redis.py` — RedisClient (KV/pubsub/queues)

### Phase 1: 工具层 + 仓库分析器 (12/12 文件)
- [x] `src/tools/__init__.py`
- [x] `src/tools/registry.py`
- [x] `src/tools/file_tools.py`
- [x] `src/tools/web_tools.py`
- [x] `src/tools/github_tools.py`
- [x] `src/tools/exec_tools.py`
- [x] `src/tools/report_tools.py`
- [x] `src/repo_analyzer/__init__.py`
- [x] `src/repo_analyzer/cloner.py`
- [x] `src/repo_analyzer/parser.py`
- [x] `src/repo_analyzer/jedi_analyzer.py`
- [x] `src/repo_analyzer/indexer.py`

### Phase 2: RAG 管道 (6/6 文件)
- [x] `src/rag/__init__.py`
- [x] `src/rag/chunker.py`
- [x] `src/rag/indexer.py`
- [x] `src/rag/bm25_index.py`
- [x] `src/rag/hybrid_search.py`
- [x] `src/rag/pipeline.py`

### Phase 3: Agent 节点 (8/8 文件)
- [x] `src/agents/__init__.py`
- [x] `src/agents/base.py`
- [x] `src/agents/planner.py`
- [x] `src/agents/researcher.py`
- [x] `src/agents/code_reader.py`
- [x] `src/agents/executor.py`
- [x] `src/agents/reviewer.py`
- [x] `src/agents/reporter.py`

### Phase 4: LangGraph 工作流 (4/4 文件)
- [x] `src/workflow/__init__.py`
- [x] `src/workflow/graph.py`
- [x] `src/workflow/executor.py`
- [x] `src/workflow/checkpoint.py`

### Phase 5: API 路由 (10/10 文件)
- [x] `src/api/__init__.py`
- [x] `src/api/dependencies.py`
- [x] `src/api/routes/__init__.py`
- [x] `src/api/routes/tasks.py`
- [x] `src/api/routes/events.py`
- [x] `src/api/routes/reports.py`
- [x] `src/api/routes/evidence.py`
- [x] `src/api/routes/tools.py`
- [x] `src/api/task_manager.py`
- [x] `src/main.py` (修改)

### Phase 6: 稳定性增强 (5/5 文件)
- [x] `src/workflow/context_manager.py`
- [x] `src/workflow/retry.py`
- [x] `src/workflow/timeout.py`
- [x] `src/utils/token_counter.py`
- [x] `src/workflow/graph.py` (修改)

### Phase 7: 集成测试 + 演示 (7/7 文件)
- [x] `tests/conftest.py`
- [x] `tests/test_tools.py`
- [x] `tests/test_rag.py`
- [x] `tests/test_agents.py`
- [x] `tests/test_workflow.py`
- [x] `scripts/demo.py`
- [x] `README.md`

### 文档 (2/2 文件)
- [x] `docs/SOLUTION.md` — 方案文档（2026-06-26 升级为 744 行完整科研演示增强设计）
- [x] `docs/PROGRESS.md` — 进度文档

## 项目配置
- [x] `pyproject.toml` — 依赖管理
- [x] `config.py` — Settings (13配置项)
- [x] `Dockerfile` — 多阶段构建
- [x] `docker-compose.yml` — 基础设施服务
- [x] `Makefile` — 开发命令
- [x] `.env.example` — 环境变量模板

### Phase 8: Vertical Slice 最小闭环 (2026-06-26)

目标：消除 Redis/Milvus 硬依赖，实现「提交本地仓库 → 多 Agent 执行 → Markdown 报告」最小闭环。

#### Bug 修复 (5 项)
- [x] `executor.py:139` — `project_index` 注入 agent state（修复始终为 None 的 bug）
- [x] `task_manager.py` — `enqueue()` 返回真实 `task_id` 而非 `"queued"`
- [x] `config.py` + `.env.example` — embedding model 改为 `text-embedding-3-small`（dim=1536）
- [x] `llm.py:92` — `chat_stream()` 补充 `temperature` 参数
- [x] `task_manager.py:98-102` — BRPOPLPUSH 包 try/finally 确保 `lrem` 必定执行

#### Redis 可选化
- [x] **新文件** `src/infrastructure/memory_store.py` — 纯内存替代，接口与 RedisClient 一致（KV/pubsub/queue）
- [x] `executor.py` — `__init__` 自动回退到 InMemoryStore
- [x] `dependencies.py` — `get_redis()` 连接失败时返回 InMemoryStore
- [x] `tasks.py` — `list_tasks` 兼容 InMemoryStore

#### Milvus 可选化
- [x] `pipeline.py` — RAGPipeline 接受 `milvus_client=None`，仅构建 BM25
- [x] `hybrid_search.py` — `milvus_client=None` 时跳过向量检索
- [x] `executor.py` — 无 RAG 时自动构建 BM25-only 管道

#### 演示脚本重写
- [x] `scripts/demo.py` — 支持 `--repo-path`、`--query`、`--output`、`--timeout`

#### Reporter 放宽
- [x] `reporter.py` — 从"必须 7 章节"放宽为"至少 3 章节"

#### 验证结果
- [x] demo.py 对本项目端到端运行成功
- [x] Jedi 索引: 69 文件, 1691 符号
- [x] BM25 检索: 5 结果
- [x] 6 Agent 全部执行
- [x] 状态流转: queued → running → completed

## 全部完成

所有 9 个阶段已实现完毕。项目可端到端运行，无需 Redis/Milvus 即可完成本地代码仓库分析。

---

### Phase 9: Bug 修复 + 方案文档升级 (2026-06-26)

#### Bug 修复
- [x] `llm.py:30-34` — 空 API key 时提前校验，抛出明确 `ValueError`，修复 `Illegal header value b'Bearer '` 错误

#### 方案文档升级 (`docs/SOLUTION.md`)
- [x] **第 9 节重写** — 8 大增强方向从简要描述扩展为完整科研设计方案：
  - `9.1` 评测闭环 — 三级评测集 (L1/L2/L3) + 8 项指标 + 标准问题设计 + 目标基线
  - `9.2` Agent 角色契约 — 每个 Agent 7 列契约表 + Reviewer 5 维审核逻辑
  - `9.3` 证据链可信度 — 结构化 JSON 证据字段 + 6 级来源置信度 + 衰减/增强因子
  - `9.4` 上下文压缩 — 4 类结构化记忆 (Task/Evidence/Failure/Plan) + 量化效果预期
  - `9.5` 工具安全与沙箱 — 三级权限体系 + Executor 命令白名单 + 审计架构
  - `9.6` 模型路由与成本控制 — ModelRouter + 降级链路 + 成本追踪
  - `9.7` 前端演示控制台 — 四面板布局 + 技术栈选型
  - `9.8` 可复现实验配置 — Run Manifest JSON + 复现命令 + 参数扫描实验表格
- [x] **新增第 10 节** — 两阶段实施路线图 + 最终项目定位声明

---

## 下一阶段规划

基于 SOLUTION.md 第 10 节的实施路线图：

### 第一阶段：核心竞争力

| 优先级 | 模块 | 预计文件 | 说明 |
|--------|------|----------|------|
| P0 | Agent 角色契约 | `src/models/contract.py`、`src/agents/contracts/*.py` | `AgentContract` 数据模型 + 6 个 Agent 契约实现 |
| P0 | 证据链可信度 | `src/models/evidence.py`（扩展）、`src/evaluation/confidence.py` | 置信度计算器 + 报告中的证据可视化 |
| P1 | 上下文压缩 | `src/workflow/memory.py` | 4 类结构化 Memory + 压缩触发逻辑 |
| P1 | 评测闭环 | `src/evaluation/` 模块 | 评测集 + 指标计算 + 基准报告生成 |

### 第二阶段：展示与工程深度

| 优先级 | 模块 | 预计文件 | 说明 |
|--------|------|----------|------|
| P2 | 前端演示控制台 | `console/` | React SPA + SSE 实时更新 |
| P2 | 模型路由 | `src/infrastructure/model_router.py` | ModelRouter + 降级链路 + 成本追踪 |
| P3 | 工具沙箱 | `src/tools/safety_gate.py` | ToolSafetyGate + 三级权限 + 审计日志 |
| P3 | 可复现实验 | `scripts/reproduce.py` + `src/models/manifest.py` | RunManifest + 复现 + 对比脚本 |

---

## Phase 10: P0 Agent 角色契约 + 证据链可信度 (2026-06-29)

实施 SOLUTION.md 第一阶段核心竞争力中的 P0 模块。

### 实施进度

| 任务 | 内容 | 状态 | 提交 |
|------|------|------|------|
| Task 1 | AgentContract 数据模型 | ✅ 完成 | `b8e7881` |
| Task 2 | EvidenceItem/EvidenceChain 扩展 | ✅ 完成 | `0266170` |
| Task 3 | ConfidenceCalculator 规则引擎 | ✅ 完成 | `5e02efa` |
| Task 4 | BaseAgent 抽象基类 | ✅ 完成 | `a1cf0e2` |
| Task 5 | PlannerAgent 重构 | ✅ 完成 | `209d4dd` |
| Task 6 | ResearcherAgent 重构 | 🔄 进行中 | — |
| Task 7 | CodeReaderAgent 重构 | ⏳ 待开始 | — |
| Task 8 | ExecutorAgent 重构 | ⏳ 待开始 | — |
| Task 9 | ReviewerAgent 重构 | ⏳ 待开始 | — |
| Task 10 | ReporterAgent 重构 | ⏳ 待开始 | — |
| Task 11 | Workflow graph + executor 适配 | ⏳ 待开始 | — |
| Task 12 | Conftest 更新 | ⏳ 待开始 | — |
| Task 13 | Demo 端到端验证 | ⏳ 待开始 | — |
| Task 14 | 契约 JSON 文件 | ⏳ 待开始 | — |

### 已交付

#### 新增文件
- [x] `src/models/contract.py` — `AgentContract` Pydantic 模型（9 字段）
- [x] `src/evaluation/__init__.py` — 模块入口
- [x] `src/evaluation/confidence.py` — `ConfidenceCalculator` 规则引擎（6 来源类型基准分 + 衰减/增强因子）
- [x] `tests/test_contracts.py` — 契约模型 + BaseAgent 验证测试（10 个测试）
- [x] `tests/test_confidence.py` — 置信度计算器测试（8 个测试）
- [x] `docs/superpowers/specs/2026-06-29-p0-agent-contracts-evidence-confidence-design.md` — 设计文档
- [x] `docs/superpowers/plans/2026-06-29-p0-agent-contracts-evidence-confidence-plan.md` — 实施计划

#### 修改文件
- [x] `src/models/evidence.py` — `EvidenceItem` 新增 6 字段（line_range, confidence_score, collected_by, corroboration_count, cross_references, related_claim），`EvidenceChain` 新增 confidence_summary
- [x] `src/agents/base.py` — 新增 `BaseAgent` 抽象基类（模板方法 execute + 4 步校验），保留原有 3 个工具函数
- [x] `src/agents/planner.py` — 重构为 `PlannerAgent(BaseAgent)` + `PLANNER_CONTRACT`，保留向后兼容 `planner_node()` wrapper

### 设计决策记录
- Agent 契约校验采取"预警+记录"而非硬阻断
- 置信度计算采取纯规则引擎（非 LLM）
- 行号衰减仅对文件类来源类型生效（CODE_FILE、DOCUMENT、GITHUB_REPO、RAG_CHUNK）
