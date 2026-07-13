# Provider 模块索引模板（通用版）

> 本模板帮助 subagent 快速识别多模块项目中的 RPC Provider 归属。**不是**预填充的具体内容，而是按需填空的索引结构。

## 模板：模块 → 主要 RPC Provider 一览

复制以下表格，按需填写每个模块的 Provider：

| Provider FQN | Impl | Mapper | 表 | 分片 |
|---|---|---|---|---|
| `com.xxx.yyy.Provider1Service` | `Provider1` | `Provider1Mapper` (config) | `xxx_data_1` | 否 |
| `com.xxx.yyy.Provider2Service` | `Provider2` | `Provider2Mapper` (config) | `xxx_data_2` | 是（corp_id） |
| ... | ... | ... | ... | ... |

## 填表说明

| 字段 | 如何填 |
|---|---|
| **Provider FQN** | 全限定接口名（含包名），通常以 `ProviderService` 结尾 |
| **Impl** | 实现类名（通常 `ProviderN` 或 `ProviderNImpl`） |
| **Mapper** | MyBatis Mapper 接口名 + 命名空间（`config` = 非分片、`sharding` = 按 corp_id 分片） |
| **表** | 实际落库的表名（从 Mapper XML 中提取） |
| **分片** | 否 / 是（corp_id）/ 是（其他字段） |

## 关键常量清单

按需填入项目实际值：

### RabbitMQ（如使用）

| 常量 | 值 | 位置 |
|---|---|---|
| `{EXCHANGE_NAME}` | `exchange.topic.xxx` | `{module}/.../RabbitMqConstant.java` |
| `{ROUTING_KEY_NAME}` | `routing.xxx.yyy` | 同上 |
| `{QUEUE_NAME_1}` | `queue.xxx.yyy` | 同上 |

### RocketMQ（如使用）

| Topic | Group | 位置 |
|---|---|---|
| `{TOPIC_NAME}` | `{CONSUMER_GROUP}` | `{module}/.../RocketMqConstant.java` |

### Kafka（如使用）

| Topic | Group | 位置 |
|---|---|---|
| `{TOPIC_NAME}` | `{CONSUMER_GROUP}` | `{module}/.../KafkaConstant.java` |

### 缓存 Key

| 用途 | Key 模板 | 模块 |
|---|---|---|
| {用途描述} | `{key_template}` | {module} |
| ... | ... | ... |

### HTTP 路径

| 用途 | URL |
|---|---|
| {用途描述} | `https://api.example.com/xxx` |

---

## 项目端口速查（如适用）

| 服务 | HTTP 端口 | RPC 端口 | app.id |
|---|---|---|---|
| {service-name} | {port} | {rpc-port} | {app-id} |
| ... | ... | ... | ... |

---

## Provider 命名规律（按 RPC 框架分类）

### Dubbo

| 角色 | 命名 | 所在模块 |
|---|---|---|
| Dubbo 接口 | `xxxProviderService` | `xxx-interface` 模块，包名 `com.xxx.client` |
| Dubbo 实现 | `xxxProvider` | `xxx-provider` 模块，包名 `com.xxx.provider.provider` |
| 业务 Service 接口 | `xxxService` | 同 provider 模块，包名 `com.xxx.provider.service` |
| 业务 Service 实现 | `xxxServiceImpl` | 同上，包名 `com.xxx.provider.service.impl` |
| 业务编排 Service | `xxxBusinessService` | 同 provider 模块，包名 `com.xxx.provider.business` |
| Mapper | `xxxMapper` | 同 provider 模块，分片在 `mapper/sharding/`、非分片在 `mapper/config/` |
| Mapper XML | `xxxMapper.xml` | `resources/com/xxx/provider/mapper/{sharding\|config}/` |

### gRPC

| 角色 | 命名 |
|---|---|
| proto 定义 | `xxx.proto` → 生成 `XxxGrpc.java` |
| Service 实现 | `extends XxxGrpc.XxxImplBase` |
| Client stub | `XxxGrpc.XxxBlockingStub` |

### Thrift

| 角色 | 命名 |
|---|---|
| IDL 定义 | `xxx.thrift` → 生成 `XxxService.java` |
| Service 实现 | `implements XxxService.Iface` |
| Client | `XxxService.Client` |

---

## 代码入口搜索关键词（按需替换）

| 想找什么 | codegraph_explore query 示例 |
|---|---|
| Controller 方法 | `ClassName.methodName` |
| Service 入口方法 | `ServiceImpl.methodName` |
| 全部 Provider | `ProviderServiceName` |
| Listener 入口 | `ListenerClassName` |
| 反向调用 | `methodName callers` |

---

## 何时不需要 subagent

- 路径已经确定（用户提供完整 URL + 已知模块）→ inline 用代码索引即可
- 接口非常简单（CRUD 直接打表）→ inline 即可
- 复用上一次会话已建立的 Provider 索引 → 直接查表对照

何时**必须** subagent：
- MQ / Listener 链路未知
- 跨多个 Provider 模块
- 涉及 HTTP 外发调用
- 需要详细 SQL / XML 内容