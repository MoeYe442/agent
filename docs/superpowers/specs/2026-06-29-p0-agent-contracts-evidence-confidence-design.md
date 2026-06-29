# P0: Agent 角色契约 + 证据链可信度 — 设计文档

> 日期：2026-06-29
> 范围：第一阶段核心竞争力 P0 模块
> 状态：已确认

## 1. 目标

将 CodeResearch Agent 平台从"能跑的多 Agent 系统"升级为"有方法论、有可解释性的科研演示平台"的第一阶段。

两个 P0 模块：

1. **Agent 角色契约**：每个 Agent 有显式的结构化契约，定义输入/输出 schema、工具白名单、禁止行为、失败条件、质量门禁；运行时校验但不硬阻断
2. **证据链可信度**：纯规则引擎计算每条证据的置信度，报告中按可信度排列，低置信度结论标注推测标记

## 2. 数据模型

### 2.1 新增 `src/models/contract.py`

```python
class AgentContract(BaseModel):
    agent_role: AgentRole
    description: str                # 一句话角色定位
    input_schema: list[str]          # 必需的 state 字段
    output_schema: list[str]         # 产出的 state 字段
    allowed_tools: list[str]         # 工具白名单
    forbidden_actions: list[str]     # 禁止行为描述
    failure_conditions: list[str]    # 声明式失败条件
    fallback_behavior: str           # 失败交接策略
    quality_gate: dict[str, float]   # 最低通过阈值
```

### 2.2 扩展 `src/models/evidence.py`

`EvidenceItem` 新增字段：

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `line_range` | `tuple[int, int] \| None` | `None` | 精确行号引用 |
| `confidence_score` | `float \| None` | `None` | 可信度评分 |
| `collected_by` | `AgentRole \| None` | `None` | 收集者角色 |
| `corroboration_count` | `int` | `0` | 交叉验证数 |
| `cross_references` | `list[str]` | `[]` | 关联证据 ID |
| `related_claim` | `str \| None` | `None` | 关联结论文本 |

`EvidenceChain` 新增字段：

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `confidence_summary` | `dict \| None` | `None` | 按来源类型汇总的置信度统计 |

## 3. Agent 基类

### 3.1 `BaseAgent` (ABC)

```python
class BaseAgent(ABC):
    contract: AgentContract          # 子类定义

    def __init__(self, llm_client, tool_registry=None):
        self.llm_client = llm_client
        self.tool_registry = tool_registry

    async def execute(self, state: AgentState) -> dict:
        self._validate_input(state)
        result = await self._run(state)
        self._validate_output(result)
        self._audit_tools(result)
        self._check_quality_gate(result)
        return result

    @abstractmethod
    async def _run(self, state: AgentState) -> dict:
        ...
```

### 3.2 校验行为

| 步骤 | 失败时行为 |
|------|-----------|
| `_validate_input` | 记录 warning 到 `errors`，继续执行 |
| `_validate_output` | 缺失字段记录到 `errors`，不阻断 |
| `_audit_tools` | 违规 tool 记录到 `errors`，在结果中标记 |
| `_check_quality_gate` | 返回 `quality_gate_passed: bool` |

核心原则：校验是"预警+记录"，不是硬阻断。

## 4. 置信度计算器

### 4.1 `ConfidenceCalculator` (`src/evaluation/confidence.py`)

纯规则引擎，`calculate(evidence: EvidenceItem) -> float`。

**基准分 (BASE_SCORES):**

| SourceType | 分数 |
|------------|------|
| `CODE_FILE` | 0.90 |
| `DOCUMENT` | 0.85 |
| `GITHUB_REPO` | 0.80 |
| `COMMAND_OUTPUT` | 0.75 |
| `RAG_CHUNK` | 0.60 |
| `WEB_PAGE` | 0.50 |

**衰减因子（乘法）：**
- `line_range` 为空：×0.90
- `corroboration_count == 0`：×0.85

**增强因子（加法）：**
- `corroboration_count >= 2`：+0.10
- `CODE_FILE` + 精确行号：+0.05

**输出 clamp 到 [0.05, 0.95]。**

### 4.2 集成点

1. Agent 创建 EvidenceItem 后调用 `calculator.calculate(item)`
2. Reviewer 读取置信度分布，低置信度 (< 0.5) 强制交叉验证
3. Reporter 按置信度降序排列引用
4. API 返回 `confidence_summary`

## 5. 现有 Agent 改造

| Agent | 原函数 | 改造后 |
|-------|--------|--------|
| Planner | `planner_node(state, llm, tools)` | `PlannerAgent(BaseAgent)._run(state)` |
| Researcher | `researcher_node(state, llm, tools)` | `ResearcherAgent(BaseAgent)._run(state)` |
| CodeReader | `code_reader_node(state, llm, tools)` | `CodeReaderAgent(BaseAgent)._run(state)` |
| Executor | `executor_node(state, llm, tools)` | `ExecutorAgent(BaseAgent)._run(state)` |
| Reviewer | `reviewer_node(state, llm, tools)` | `ReviewerAgent(BaseAgent)._run(state)` |
| Reporter | `reporter_node(state, llm, tools)` | `ReporterAgent(BaseAgent)._run(state)` |

Agent 核心 LLM 调用逻辑不变，仅改外层结构。

## 6. Workflow 适配

`graph.py` 节点注册从函数改为实例方法：

```python
planner_agent = PlannerAgent(llm_client, tool_registry)
graph.add_node("planner", planner_agent.execute)
```

路由逻辑不变。

## 7. 实施顺序

1. 数据模型 (`contract.py` + `evidence.py` 扩展)
2. `ConfidenceCalculator` (`src/evaluation/confidence.py`)
3. `BaseAgent` 基类 (`src/agents/base.py` 扩展)
4. 逐个 Agent 重构 (Planner → Researcher → CodeReader → Executor → Reviewer → Reporter)
5. `graph.py` + `executor.py` 适配
6. 测试更新 (`test_contracts.py` + `test_confidence.py` + 修改 `test_agents.py`)
7. `demo.py` 端到端验证

## 8. 不变量

- 6 个 Agent 核心 LLM 调用逻辑不变
- LangGraph 状态机路由不变
- API 接口不变，数据模型兼容
- 零基础设施依赖 (Redis/Milvus 可选)
