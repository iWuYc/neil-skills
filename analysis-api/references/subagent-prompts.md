# Subagent Prompt 模板（通用版）

本目录的 5 个模板对应 Step 1（入口定位）、Step 2（按模块下钻 Provider）、Step 3（MQ 消费者追踪）。模板适用于任何"Java + RPC + MQ"的多模块项目，请按需替换占位符。

所有 prompt 的共同约束：
- 强制使用代码索引 MCP（如 codegraph），禁止 grep/read 循环（除非代码索引不可用）
- 返回内容必须是结构化的（接口签名 / 实现类 / 表名 / XML 路径）
- 不跨模块扩散（每个 subagent 只看自己负责的模块）
- 完成后只返回结论 + 关键代码块，**不要**返回 agent metadata

---

## 模板 1：entry-locator（Step 1 - 入口定位）

```markdown
请在 `{REPO_ROOT}` 这个 monorepo 中，帮我定位以下接口的完整调用入口：

**接口路径**：`{USER_GIVEN_PATH}`

请使用代码索引工具（如 codegraph）来搜索：
1. 在 `{SUSPECTED_MODULE}` 或相关模块中，搜索包含 `{PATH_KEYWORD}` 或 `{METHOD_KEYWORD}` 的 controller 端点
2. 找到这个 controller 方法的完整方法签名、所在类、所在模块
3. 找到这个 controller 方法的完整实现代码（包括方法体、参数解析、调用下游 service 的逻辑）
4. 找到这个 controller 注入的 Service/Manager 对象及其类型

注意：
- 这是 Java Spring Boot 项目，使用 RPC 框架（Dubbo / gRPC / Thrift 任选其一）
- 优先使用代码索引工具而非 grep/read 文件

请返回：
- 入口 Controller 的完整路径（绝对路径）
- Controller 类的完整内容
- 入口方法的完整实现
- 这个方法调用了哪些 Service/Manager 方法（包括方法签名）
```

---

## 模板 2：provider-tracer-business（Step 2 - 业务模块通用版）

```markdown
请在 `{REPO_ROOT}` 这个 monorepo 中，帮我分析 `{MODULE}` 模块中以下 RPC Provider 的完整实现链路：

**目标 Provider 接口**：
{PROVIDER_LIST_WITH_JAVA_FQNS}

需要做的事：

1. **找到所有 Provider 接口的完整方法签名**（用代码索引工具）
2. **找到 Provider 实现类**（典型路径：`{MODULE}/xxx-provider/src/main/java/.../provider/provider/*ProviderImpl.java` 或 `*Provider.java`），并获取完整内容
3. **找到对应的 Service 和 ServiceImpl**（典型路径：`{MODULE}/xxx-provider/.../service/impl/*ServiceImpl.java` 或 `{MODULE}/xxx-core/.../service/impl/*ServiceImpl.java`），获取完整内容
4. **找到对应的 Mapper 类**，列出 SQL 操作（insert/update/delete/select）涉及的表名
5. **找到任何消费者 / 异步任务 / 监听者**（如 `@RabbitListener`、`@RocketMQMessageListener`、`@KafkaListener`、Task 类）

请使用代码索引工具（如 codegraph_explore / codegraph_search / codegraph_callers）来：
- 调用 `codegraph_explore` 时，传入完整的方法/类名作为查询
- 调用 `codegraph_callers` 时，可以传入方法名，反向追踪谁调用它

注意：
- 这是 Java Spring Boot 项目
- 项目使用 RPC 框架：{RPC_FRAMEWORK_NAME}（如 Dubbo / gRPC / Thrift）
- Provider 名称典型结尾是 `ProviderService`，对应实现是 `ProviderImpl` / `ProviderServiceImpl`
- 不要依赖 grep/read 文件，请优先用代码索引工具

返回内容：
- 每个 Provider 接口的完整方法列表
- 每个 Provider 对应的 Impl / Service / Mapper 完整内容
- 最终的数据库表名
- 是否有消费者在监听相关 MQ 主题
```

---

## 模板 3：provider-tracer-customer（Step 2 - 客户 / 业务域通用版）

```markdown
请在 `{REPO_ROOT}` 这个 monorepo 中，帮我分析 `{MODULE}` 模块中以下 RPC Provider 的完整实现链路：

**目标 Provider 接口**：
{PROVIDER_LIST_WITH_JAVA_FQNS}

需要做的事：

1. **找到所有 Provider 接口的完整方法签名**（使用代码索引工具）
2. **找到 Provider 实现类**（典型路径：`{MODULE}/xxx-provider/src/main/java/.../provider/provider/*ProviderImpl.java` 或 `*Service` 后缀）
3. **找到对应的 Service 和 ServiceImpl**
4. **找到对应的 Mapper 类**，列出 SQL 操作涉及的表名（典型表前缀：{TABLE_PREFIX_HINTS}）
5. **查找是否有相关的事件 / 监听者**（如 `@RabbitListener`、`@RocketMQMessageListener`）

请使用代码索引工具（如 codegraph_explore / codegraph_search / codegraph_callers / codegraph_node）来查询。

注意：
- 这是 Java Spring Boot 项目，使用 RPC 框架：{RPC_FRAMEWORK_NAME}
- Provider 名称典型结尾是 `ProviderService`
- 优先使用代码索引工具而非 grep/read

返回内容：
- 每个 Provider 接口的完整方法列表
- 每个 Provider 对应的 Impl / Service / Mapper 完整内容
- 最终的数据库表名
- 是否有消费者在监听相关 MQ 主题
```

---

## 模板 4：provider-tracer-middleend（Step 2 - 中台 / 透传层通用版）

```markdown
请在 `{REPO_ROOT}` 这个 monorepo 中，帮我分析 `{MODULE}` 模块中以下 RPC Provider 的完整实现链路：

**目标 Provider 接口**：
{PROVIDER_LIST_WITH_JAVA_FQNS}

需要做的事：

1. **找到所有 Provider 接口的完整方法签名**（使用代码索引工具）
2. **找到 Provider 实现类**（典型路径：`{MODULE}/` 下 `provider/impl/` 或 `service/impl/`，以 `*ProviderImpl` 或 `*ServiceImpl` 结尾）
3. **找到对应的 Service 和 ServiceImpl**
4. **找到对应的 Mapper 类**（如果有的话），列出 SQL 操作涉及的表名
5. **查找是否有相关的 HTTP 调用 / 外部 API 封装**（特别是某个 Provider 方法最终是如何调用外部 HTTP 接口的）
6. **查找是否在 `{MODULE}` 模块内有 MQ 消费者或 Task**

请使用代码索引工具（如 codegraph_explore / codegraph_search / codegraph_callers / codegraph_node）来查询。

注意：
- 这是 Java Spring Boot 项目
- `{MODULE}` 项目结构可以参考项目 CLAUDE.md
- 优先使用代码索引工具而非 grep/read

返回内容：
- 每个 Provider 接口的完整方法列表
- 每个 Provider 对应的 Impl / Service / Mapper 完整内容
- 是否最终调用了外部 HTTP API（如使用 RestTemplate / OkHttpClient / Feign / HttpClient）
- 最终的 HTTP 接口地址或调用方式
```

---

## 模板 5：mq-consumer-tracer（Step 3 - MQ 消费者追踪）

```markdown
请在 `{REPO_ROOT}` 这个 monorepo 中，帮我查找所有监听以下 MQ 主题/路由键的消费者：

**目标 MQ 主题**：
1. RabbitMQ Exchange: `{EXCHANGE}`，Routing Key: `{ROUTING_KEY}`
2. RocketMQ topic 包含 `{TOPIC_KEYWORD}` 等关键词（来自 `{MESSAGE_DTO_FQN}` 的同步类型）
3. Kafka topic: `{KAFKA_TOPIC}`（如有）

具体要做的：

1. **全仓搜索**包含 `@RocketMQMessageListener` 注解、`@RabbitListener` 注解、`@KafkaListener` 注解、`@Consumer` 注解的所有 Java 类
2. **特别关注**那些消息体是 `{MESSAGE_DTO_FQN}` 或 `{ALT_MESSAGE_DTO_FQN}` 的消费者
3. **特别关注**位于 `{MODULE_HINTS}` 等模块的消费者
4. **找到这些消费者的入口类**，并列出它的：
   - 完整路径
   - 监听的 topic/exchange/routing key
   - 监听到消息后的处理逻辑（方法名 + 调用下游 service/provider 的方法）
   - 处理过程中涉及的 RPC Provider（service 名称 + 方法名）

请使用代码索引工具（如 codegraph_explore / codegraph_search）来：
- 在所有 `*.java` 文件中搜索 `{MESSAGE_DTO_FQN}` 的引用
- 搜索 `RabbitListener`、`RocketMQMessageListener`、`KafkaListener` 等注解
- 搜索 `{ROUTING_KEY}` 字符串常量

注意：
- 这是 Java Spring Boot 项目
- 项目使用的 MQ：{MQ_TYPE}（RabbitMQ / RocketMQ / Kafka / 多 MQ 并存）
- 优先使用代码索引工具而非 grep/read

返回内容：
- 找到的所有消费者（按模块归类）
- 每个消费者的完整入口类路径
- 每个消费者处理的逻辑概要
- 这些消费者处理的最终落点（哪个 Provider / 哪个表）
```

---

## 占位符替换清单

| 占位符 | 含义 | 示例 |
|---|---|---|
| `{REPO_ROOT}` | 仓库根目录 | `/path/to/monorepo` |
| `{USER_GIVEN_PATH}` | 用户提供的接口路径 | `/api/v1/foo/bar/sync` |
| `{SUSPECTED_MODULE}` | 推测所在模块 | `foo-module` |
| `{PATH_KEYWORD}` | 路径关键字 | `foo/bar/sync` |
| `{METHOD_KEYWORD}` | 方法名关键字 | `fooSync` |
| `{MODULE}` | 目标模块名 | `bar-module` |
| `{PROVIDER_LIST_WITH_JAVA_FQNS}` | Provider 全限定名列表 | `com.x.BarProviderService`、`com.x.BazProviderService` |
| `{TABLE_PREFIX_HINTS}` | 表名前缀提示 | `customer`、`order`、`bar_` |
| `{RPC_FRAMEWORK_NAME}` | RPC 框架名 | `Dubbo` / `gRPC` / `Thrift` |
| `{EXCHANGE}` | RabbitMQ 交换机名 | `exchange.topic.foo` |
| `{ROUTING_KEY}` | RabbitMQ 路由键 | `routing.foo.bar` |
| `{TOPIC_KEYWORD}` | RocketMQ topic 关键字 | `fooTopic` |
| `{KAFKA_TOPIC}` | Kafka topic 名 | `foo-topic` |
| `{MESSAGE_DTO_FQN}` | 消息体 DTO 全限定名 | `com.x.FooMessageDTO` |
| `{ALT_MESSAGE_DTO_FQN}` | 备选消息体 DTO | `com.x.AltFooMessageDTO` |
| `{MODULE_HINTS}` | 模块提示列表 | `["foo-module", "bar-job"]` |
| `{MQ_TYPE}` | MQ 类型 | `RabbitMQ` / `RocketMQ` |

---

## 模板使用注意

1. **替换占位符**：每个模板的 `{XXX}` 占位符必须在派发前替换成实际值
2. **派发时机**：所有 subagent **必须并行派发**（一个 message 里放多个 Agent tool 调用），不要串行
3. **不要等所有 subagent 都完成才进入 Step 5**：等所有 subagent 完成后再开始汇总
4. **subagent 出错处理**：如果某个 subagent 失败，重试 1 次；仍失败则在报告"未解决的疑点"章节里标注
5. **代码索引不可用时**：把"使用代码索引工具"替换成"使用 Grep + Read + Glob"，并在报告开头标注

## 派发前的最后清单

- [ ] 所有 `{XXX}` 占位符已替换
- [ ] 5 个 subagent 在一个 message 里并行派发
- [ ] 每个 subagent 明确只负责一个模块 / 一个主题
- [ ] 每个 subagent 收到的指令里都包含"返回结构化结论，不要返回 metadata"