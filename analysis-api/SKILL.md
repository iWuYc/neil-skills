---
name: analysis-api
description: Use when the user asks to analyze / 梳理 / trace / 追踪 a REST API endpoint's full call chain in a Java Spring Boot multi-module monorepo (e.g. "分析 /api/v1/xxx/sync 接口的整体流程", "梳理 X 接口的调用链", "trace the call flow of POST /xxx"). Produces a Markdown report with Mermaid flow diagrams covering Controller → Service → RPC Provider → Service → Mapper → DB plus MQ producers / consumers and outbound HTTP (e.g. third-party / 外部 API) calls. Triggers on any 跨模块接口调用链 / 业务链路 / MQ 消息流梳理 request, even when the user just says "分析下这个接口" or "这个同步链路是怎么走的". Works for any Java backend stack with RPC framework (Dubbo / gRPC / Thrift) and message queue (RabbitMQ / RocketMQ / Kafka). Handles interruptions gracefully when MQ destinations or cross-service boundaries are unclear.
---

# Analysis API (Java Multi-Module Monorepo 接口调用链分析)

把一个 HTTP 接口（或一段跨模块业务链路）从入口到出口完整画出来，并输出 Mermaid 流程图 + 关键代码位置索引的 Markdown 报告。

## When to use this skill

**Use this skill when ANY of the following is true:**

- 用户给出一个具体 REST 路径并要求"分析接口流程 / 梳理调用链 / 看看是怎么实现的"
- 用户问"X 接口调用了哪些 RPC Provider / 写了哪些表 / 发了哪些 MQ / 调了哪些外部 API"
- 用户问"某个同步链路是怎么走的 / MQ 消息最终落到了哪里"
- 用户说"帮我梳理下这条业务流程"或"分析 X 业务到 Y 业务的链路"

**Do NOT use this skill when:**

- 用户只是问"X 类是什么 / X 方法做什么"（用 codegraph / 直接搜索回答即可）
- 用户要修改代码 / 实现新功能（用 brainstorming → writing-plans → implementation）
- 用户的请求与调用链无关（如：单纯 grep 找字符串、code review、生成测试用例）
- 项目不是 Java 后端（如：前端调用链、Python 脚本）

## Required tools / dependencies

**核心工具：**

- `Agent` (general-purpose) —— 并行 subagent，用于分模块下钻 Provider / Mapper
- `AskUserQuestion` —— 中断问询（MQ 流向不明 / 跨服务跳转时必须使用）
- `Write` —— 输出报告到指定路径

**强烈推荐（提升效率）：**

- 代码索引 MCP（如 `codegraph`）—— 把符号/文件名当 query，返回源代码 + 引用关系
- `Grep` / `Glob` —— 全仓搜索关键字
- `Read` —— 读取关键文件

如果没有代码索引 MCP，回退到 `Grep` + `Read` + `Glob`，但效率会显著降低，应在报告开头标注"未使用代码索引工具"。

## Granularity (粒度可配置)

通过 `AskUserQuestion` 在第一步询问下钻粒度（详见 §1 Step 0），三个选项：

| 粒度 | 含义 | 适用 |
|---|---|---|
| **轻量** | 追到 Controller / Service + 主要 RPC 接口签名，不下钻到 Mapper/XML | 用户只想了解"大概调了哪些东西" |
| **标准**（默认） | 含 Provider → Service → Mapper + 关键 SQL + 表名 | 多数接口分析的默认选择 |
| **完整** | 含所有 Listener / Task / AsyncTask 链路、外发 HTTP 调用、Retry 机制 | 用户明确说"全量"或涉及消息异步链路 |

如果用户没明确说，默认走"标准"。

---

## Workflow（7 步法）

```
Step 0 — 范围确认（AskUserQuestion）
   ↓
Step 1 — 入口定位（主进程，单 subagent 或 inline）
   ↓
Step 2 — 拆分子任务，按模块并行 subagent 下钻 Provider
   ↓
Step 3 — MQ / Listener 反向追踪（独立 subagent）
   ↓
Step 4 — 中断问询（如遇到 MQ 流向不明 / 跨服务跳转）
   ↓
Step 5 — 主进程汇总报告（含 Mermaid 流程图）
   ↓
Step 6 — 自检 + 输出
```

---

## Step 0 — 范围确认（必须）

在动手之前用 `AskUserQuestion` 询问 2 个问题：

### Q1: 粒度
- 轻量（仅 Service/RPC 签名）
- **标准**（含 Mapper/SQL/表名）—— 推荐默认
- 完整（含 MQ/AsyncTask/HTTP 外发/Retry）

### Q2: 输出位置
- 追加到原始需求文档同目录下（`xxx.md` 旁边新建 `002.xxx-接口流程分析.md`）—— 推荐
- 写到 `{project}/doc/api-analysis/{module}/{interface}.md`
- 仅终端输出（不写文件）

如果用户的指令里已经明确这两点（例如 "全量接口分析 + 进 Provider 查具体业务实现 + 追加 .md"），可以**直接跳过 Q2**，把粒度记在心里即可。

**也用 TaskCreate 把流程切分成 5-7 个 todo**（入口 / Service / MQ / Provider / Listener / 报告），便于跟踪进度。

---

## Step 1 — 入口定位（inline 或 1 个 subagent）

**目标**：找到 HTTP 入口的 Controller 方法，搞清楚方法签名 + 调用了哪些 Service。

### Inline 做（首选，快）
用代码索引 MCP 直接查询路径中的关键字，或用 `Grep` 按关键字搜索：

```python
# 如果有 codegraph:
mcp__codegraph__codegraph_explore(query="ClassName methodName endpoint-path")
mcp__codegraph__codegraph_search(kind="method", query="methodName")

# 否则用 Grep:
Grep(pattern="@RequestMapping.*api/v1/xxx", glob="**/*Controller.java")
```

如果返回内容已经能直接看到入口 Controller 的实现，就**不要**额外启动 subagent；直接进入 Step 1.5 读取关键 Service 文件。

### 派 subagent 做（当入口不确定 / 路径模糊时）
派一个 `general-purpose` subagent，专门做"定位入口 Controller + Service 入口"，返回：
- 完整 URL 路径
- Controller 文件绝对路径 + Maven 模块
- `@RequestMapping` + `@PostMapping` 全路径拼接过程
- Controller 方法的完整源码
- Controller 注入的 Service / Producer 字段（含 `@Autowired` + RPC 引用注解，如 `@DubboReference` / `@Reference`）

Prompt 模板见 `references/subagent-prompts.md#entry-locator`。

### Step 1.5 — 读完 Service 主流程（inline）

**必须 inline 读完** `*ServiceImpl.java` 的入口方法（如 `labelSync`），不能只听 subagent 报告。

理由：subagent 容易漏掉异常分支、注释掉的旧 MQ 逻辑等；以及异步线程池调用、`@Async` 方法等隐式入口。

读完后立刻用 TaskUpdate 把对应 todo 标记 completed。

---

## Step 2 — 拆 subagent，按模块并行下钻 Provider

根据 Service 用到的 RPC Provider 列表，按模块拆 subagent。**每个模块一个 subagent，并行派发**。

### 拆分原则
- 一个 subagent = 一个独立模块 / 一组相关 Provider
- subagent 之间**不共享状态**、**不互相依赖**
- 一个 subagent 任务包含：该模块所有目标 Provider 的完整接口 + 实现 + Service + Mapper + 表名 + XML 关键 SQL

### 典型拆分（按 RPC 框架调整 Provider 命名）

| Subagent | 模块 | Provider 列表 | 落点表 |
|---|---|---|---|
| A | 业务模块 A | 3 个业务 Provider | 业务表 A1/A2/A3 |
| B | 客户模块 B | 4 个客户 Provider | 客户表 B1/B2/B3/B4 |
| C | 第三方 / 中台 C | 2 个 HTTP 透传 Provider | 不落表 / 调外部 HTTP |
| D | 全仓 MQ 消费者 | 监听目标 message DTO 的所有 `@RabbitListener` / `@RocketMQMessageListener` / `@KafkaListener` | 反向 RPC 调用 Provider |

### Subagent Prompt 模板
详见 `references/subagent-prompts.md`，包含 5 个已验证可用的模板。

### 关键约束（写到每个 subagent prompt 里）
- **强制使用代码索引工具**（如 codegraph），禁止 grep/read 循环（除非不可用）
- 返回内容必须包含：接口方法签名、Impl/Service/Mapper 完整内容、最终表名、是否有消费者
- 严禁跨模块扩散，只看自己负责的模块

---

## Step 3 — MQ / Listener 反向追踪（独立 subagent）

**独立派一个 subagent** 做这件事，不要让它和 Step 2 的 Provider subagent 混在一起。

理由：MQ 监听者通常跨多个业务模块（同一个 `@RabbitListener` 可能调多个模块的 Provider）。

### 这个 subagent 要做的事

1. 全仓搜 `@RabbitListener` / `@RocketMQMessageListener` / `@KafkaListener` / `@Consumer` 注解
2. 找到所有监听目标 message DTO 的类
3. 找到所有监听目标 routing key / topic 的类
4. **每个 Listener 返回**：
   - 完整类路径
   - 监听的 queue / topic / routing key
   - 消息体 DTO
   - 入口方法名 + 入参
   - 内部调用的 RPC Provider 列表（按调用顺序）

Prompt 模板见 `references/subagent-prompts.md#mq-consumer-tracer`。

### 用反向调用工具
如果已知某个方法（如 `subscribeNotify`），可以用 `codegraph_callers`（或 grep）反查谁调了它，这比正向搜索准很多：

```python
mcp__codegraph__codegraph_callers(query="subscribeNotify")
```

---

## Step 4 — 中断问询（关键！）

**在以下情况必须停下来用 `AskUserQuestion` 询问用户，不能继续猜：**

1. **MQ 路由不确定**：知道 Producer 发了消息，但同一个 routing key 在 broker 端可能绑定到多个 queue；不知道用户关注哪个 consumer
2. **跨服务跳转**：发现 Service A 调了 Service B，但 Service B 不在本仓库（如 third-party SDK / 外部微服务）
3. **数据库表名有歧义**：Mapper XML 中看到 `xxx_data` 这种表名，但同名字段在不同模块可能代表不同含义
4. **下钻粒度拿不准**：用户说"分析 X 接口"，但接口背后可能涉及 5+ 模块，下钻到哪个深度？
5. **用户的需求文档中明确写了"如果遇到了 mq 或者其他情况导致数据流不知道流向到哪个模块了，请停下来进行询问"** —— 这种情况必须严格遵守

### 提问格式

```python
AskUserQuestion(questions=[
    {
        "question": "在分析 X 接口时，需要分析到什么粒度？",
        "header": "分析范围",
        "multiSelect": false,
        "options": [
            {"label": "仅主同步路径", "description": "..."},
            {"label": "主路径 + 关联 MQ", "description": "..."},
            {"label": "全量接口分析", "description": "..."},
        ],
    },
    {
        "question": "对于 RPC Provider 调用的分析，下钻到什么粒度？",
        "header": "下钻范围",
        "multiSelect": false,
        "options": [...],
    },
])
```

**一次最多 4 个问题**，每个问题 ≤ 4 个选项。让用户选完之后再继续。

---

## Step 5 — 主进程汇总报告

主进程把 subagent 结果 + inline 读取的代码融合，输出最终 Markdown 报告。

### 报告结构（强制）

报告**必须**包含以下章节，缺一不可：

```markdown
# {NNN}.{日期}.{原文件名}-接口流程分析

> 1-3 句概述：覆盖哪些接口、关键事实（如"不发 MQ"、"调用外部 API"）。

## 1. 接口清单（如果是接口分析）

| 方法 | 路径 | 方法签名 | 说明 |

## 2. 主调用链流程图（Mermaid）

用 mermaid flowchart TD 画完整链路图，标注 Controller / Service / RPC / 表名 / MQ。

## 3. 详细步骤分解

每一步：
- 步骤 N — 标题
- 涉及代码位置（绝对路径 + 行号）
- 关键 RPC / SQL / HTTP 调用
- 备注（如有 MQ 触发条件）

## 4. 其他相关接口（如果是 Controller 包含多个接口）

每个接口的独立流程图 + 关键调用链。

## 5. 跨模块调用关系图（Mermaid graph LR）

把模块作为 subgraph，所有 Provider / Listener 作为节点，箭头表示调用。

## 6. 各 RPC Provider 落点对照表

| RPC Provider | 模块 | 实现类 | Service | Mapper | 表名 | XML 路径 |

## 7. 关键代码位置索引

| 关注点 | 文件 | 关键行 / 方法 |

## 8. 消息队列全链路消费者（如有）

每个 Listener 的流程图 + 落点表。

## 9. 总结

3-5 句话总结：
- 接口是不是发 MQ
- 数据流归宿（哪些表）
- 同 Controller 其他接口的副作用
- 真正的下游链路在哪里
```

### Mermaid 绘图规范

**flowchart TD** 用于单个调用链；**graph LR** 用于跨模块关系图。

节点命名规则：
- Controller：`[ClassName.methodName]`
- Service：`[ClassName.methodName]`
- RPC 调用：`[RPC: ProviderName.method]`
- MQ Producer：`[MQ: ProducerName.sendMethod]`
- MQ Queue：`[MQ: queue.name]`
- 表：`[(table_name 表)]`
- 决策菱形：`{condition?}`
- 外部 HTTP API：`[External API: endpoint]`

连线标签：
- 同步调用：`-->`
- 异步线程：`.->|异步线程池|`
- 异步 MQ：`==>|MQ 消息|`

### 报告输出路径

按用户在 Step 0 Q2 选择的位置写入：
- **追加 .md**（默认）：在原文档所在目录新建 `00N.{原文件名后缀}-接口流程分析.md`
- 用 `Write` 工具，**不要**覆盖原文件
- 报告 frontmatter 加上：日期、tags、aliases、SessionName

---

## Step 6 — 自检 + 输出

写完报告后做一次自检：

### 自检清单

1. **完整性**：9 个章节是否齐全？
2. **代码位置**：所有"文件路径 + 行号"是否能在前面的 subagent / inline 读取中找到？
3. **MQ 流向**：Producer → Exchange → Routing Key → Queue → Listener 链条是否完整？
4. **表名**：所有 RPC Provider 的最终落点表是否都列了？
5. **Mermaid 语法**：本地渲染一下（Mermaid Live Editor）确保无语法错误
6. **重复 / 冗余**：subagent 报告里和 inline 读到的是否有矛盾？

### 报告交付

完成后在终端给用户一个简短摘要（5-10 行），包含：
- 报告绝对路径
- 报告包含哪些章节
- 关键发现 3 条
- 是否还有未解决的疑点

---

## 关键经验（从本项目抽象出来）

> 以下经验不绑定具体项目名 / 表名 / 接口名，适用于所有"Java 多模块 + RPC + MQ"的调用链分析场景。

1. **sync 接口不一定发 MQ，delete 接口可能发 MQ**。仅看 Controller 的注解会漏掉 Service 内通过线程池发 MQ 的隐式入口。**主进程必须 inline 读完 Service 主流程**。
2. **同一个 Producer 路由键可绑定多个 Queue → 多个 Listener**。仅查 Producer 端会漏掉 consumer 链路。**MQ 分析必须独立 subagent**，且要列出所有匹配的 Listener，不止用户提到的那个。
3. **职责分离的多模块结构很常见**：业务模块（写库）、客户模块（写分片表）、中台模块（HTTP 透传）。识别这种结构能精准拆分 subagent。
4. **RPC 监听标准格式**：`@RabbitHandler` + `@RabbitListener(queues=...)` + `containerFactory=...`（RabbitMQ）；`@RocketMQMessageListener(topic=..., consumerGroup=...)`（RocketMQ）。
5. **分布式锁注解（如 `@CacheLock(key="...")`）是 RPC 框架常见特性**，不是 Spring Cache。处理并发时要注意。
6. **Provider 命名规律**：`xxxProviderService` 接口 + `xxxProvider` 实现，包名 `com.xxx.provider.provider`。
7. **Service 命名**：基础数据 Service 继承 `BaseServiceImpl`（非分片），业务 Service 继承 `ShardingBaseServiceImpl`（按 `corp_id` 分片）。
8. **AsyncTask 框架 ≠ MQ**，是基于 `AsyncTaskService` 的本地延迟任务（典型 90s 延时重试 3 次），别和消息队列混为一谈。

---

## Output rules

- 报告用中文，技术术语 / 代码标识符保留原文
- 所有 Mermaid 图都要用 ```mermaid 代码块包裹
- 代码路径用绝对路径（如 `/path/to/repo/xxx.java`）
- 行号格式：`file.java:123` 或 "line 123-128"
- 报告不超过 5000 行（一般 500-1500 行）
- 完成后**不在报告里包含 subagent 元信息**（agent ID、任务文件路径等）

## What this skill does NOT do

- 不修改任何代码
- 不创建新文件（除了报告本身）
- 不做 code review
- 不做单元测试 / 集成测试
- 不翻译代码 / 注释
- 不建议重构或优化（只描述现状）

## Related skills

- `superpowers:dispatching-parallel-agents` —— 本技能的核心依赖，用于并行下钻 Provider
- `superpowers:brainstorming` —— 如果用户在创建技能时使用
- `superpowers:writing-skills` —— 本技能被创建时用到