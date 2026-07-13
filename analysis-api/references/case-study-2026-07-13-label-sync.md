# 实战经验教训（通用版）

> 本文档是 analysis-api 技能迭代过程中沉淀的通用经验教训，不绑定具体项目。Skill 使用者可以忽略；skill 维护者可以参考。

## 起源

本技能在分析某个 Java Spring Boot + Dubbo + RabbitMQ 多模块 monorepo 中的 `/api/v1/.../sync` 接口时首次使用。整个流程跑通了"入口定位 → 模块拆分 → MQ 反向追踪 → 主进程汇总"的全链路，验证了 7 步法的可用性。

## 经验教训（抽象后）

### 1. subagent #1（入口定位）的结果有部分冗余

**现象**：入口 subagent 把 Controller、Service 入口、Provider 列表都列了，但后续模块 subagent 又把这些 Provider 重新覆盖了一遍。

**未来优化**：让 subagent #1 只做"定位 Controller + Service 入口"，**不要**让它列 Provider 列表；由 Step 2 的 subagent 自己去找，避免重复劳动。

### 2. 第一次容易漏掉部分 Listener

**现象**：用户没明确提到某个 Listener，第一个版本的报告漏掉了它。

**已修复**：在 SKILL.md 里强调 subagent #5（MQ 消费者追踪）必须列出**所有**匹配的 Listener，包括 user 没明确提到的——同一个 routing key 可能绑定多个 queue。

### 3. 报告可能被人工补了一次

**现象**：所有 subagent 报告都到齐后才开始写报告，但写完才发现遗漏，需要追加章节。

**已修复**：在 workflow 里明确 Step 3（MQ 追踪）必须在 Step 5（汇总）之前完成。同时强调"读完所有 subagent 结果再做总结"，避免遗漏。

### 4. inline 读完 Service 主流程至关重要

**现象**：subagent 只看 Controller 一开始没能直接报出 Service 内部的异步 MQ 逻辑（被注释掉的旧代码、异步线程池调用等）。

**已修复**：在 SKILL.md §Step 1.5 强调"必须 inline 读完 Service 主流程，不能只听 subagent 报告"。

### 5. 用户偏好粒度需要明确问

**现象**：用户说"分析 X 接口"，没说下钻到哪个深度。

**已修复**：Step 0 用 AskUserQuestion 询问粒度（轻量/标准/完整）+ 输出位置。如果用户在原始指令里已经说明，就跳过。

---

## 关于本案例的实际使用数据（仅作参考）

- **派发的 subagent 数**：5 个（1 个入口定位 + 3 个模块 Provider + 1 个 MQ 追踪）
- **运行时间**：约 200 秒（并行派发）
- **触发中断问询次数**：1 次（在派发 subagent 之前问粒度）
- **报告最终大小**：约 1000 行（含 5 个 Mermaid 流程图）
- **生成报告章节数**：9 章（含 8 章 MQ 全链路消费者）

---

## 对其他项目的适应性

本技能的 workflow 抽象程度足够高，可直接复用到任何"Java + RPC 框架 + 消息队列"的多模块项目。需要按项目调整的部分：

| 需要调整的部分 | 调整方式 |
|---|---|
| RPC 注解名 | `@DubboReference` → `@Reference`（gRPC）/ `@GrpcClient`（gRPC Spring） |
| Provider 命名规律 | 见 `provider-index.md` 的"按 RPC 框架分类"章节 |
| MQ 注解 | `@RabbitListener` → `@RocketMQMessageListener` / `@KafkaListener` |
| 异步任务框架 | Dubhe AsyncTask → Spring `@Async` / `@Scheduled` / Quartz |
| 分布式锁注解 | `@CacheLock`（Dubhe）→ 其他项目自定义注解 |
| 表名前缀 | 项目实际命名 |

具体调整方法见 `references/subagent-prompts.md` 的占位符替换清单。