# ADR-002: 选择 RabbitMQ 作为消息队列

## 状态

Proposed

## 背景

微服务架构需要服务间通信机制，主要需求:
- 异步消息传递，解耦服务依赖
- 支持多种消息模式（发布/订阅、点对点等）
- 消息可靠性保证，不丢失消息
- 易于监控和管理
- 团队熟悉度和社区支持

## 决策

使用 RabbitMQ 作为消息队列中间件，采用 Topic Exchange 模式实现消息路由。

## 理由

### RabbitMQ 优势

1. **成熟稳定**: 经过10+年生产验证，稳定性高，被广泛应用于大型系统
2. **多种消息模式**: 支持直连、主题、扇出、头部等多种Exchange类型
3. **管理界面**: 提供Web管理界面，便于监控队列状态、消息速率等
4. **消息确认**: 支持消息确认机制（ACK），保证消息不丢失
5. **消息持久化**: 支持消息持久化到磁盘，重启后可恢复
6. **社区支持**: 活跃的社区和丰富的文档，问题易于解决
7. **多语言客户端**: 支持Python、Java、Go等多种语言客户端
8. **灵活路由**: 通过Routing Key实现灵活的消息路由

### 技术特性

- **协议**: AMQP 0-9-1（高级消息队列协议）
- **吞吐量**: 单机可达 1-2万消息/秒
- **延迟**: 毫秒级延迟
- **可靠性**: 支持消息确认、持久化、事务

## 替代方案

### 方案A: Apache Kafka

**优点**:
- 高吞吐量（百万级消息/秒）
- 消息持久化，支持回溯
- 分布式架构，高可用
- 适合大数据流处理

**缺点**:
- 架构复杂，运维成本高
- 消息顺序保证需要分区设计
- 不支持消息路由，需要自行实现
- 对于当前规模过于复杂

**结论**: 不适合当前规模，未来如果需要大数据流处理可考虑引入

### 方案B: Redis Pub/Sub

**优点**:
- 轻量级，部署简单
- 性能高，延迟低
- 团队熟悉度高

**缺点**:
- 不支持消息持久化，重启后消息丢失
- 不支持消息确认机制
- 功能简单，缺乏高级特性
- 不适合可靠性要求高的场景

**结论**: 可用于实时性要求高但可靠性要求低的场景（如缓存更新通知）

### 方案C: AWS SQS / 阿里云 MQ

**优点**:
- 托管服务，无需运维
- 高可用，自动扩容
- 按需付费

**缺点**:
- 厂商锁定
- 延迟较高（SQS约10-20ms）
- 成本随消息量增加
- 需要公网访问

**结论**: 如果未来迁移到云平台可考虑，当前自建更灵活

## 架构设计

### Exchange 和 Queue 设计

```
┌─────────────────────────────────────────┐
│         Topic Exchange: app.events      │
│                                         │
│  Routing Keys:                          │
│  - user.*     (用户相关事件)            │
│  - task.*     (任务相关事件)            │
│  - notif.*    (通知相关事件)            │
└────────────┬────────────────────────────┘
             │
    ┌────────┴────────┬──────────────┐
    │                 │              │
┌───▼────┐      ┌────▼───┐     ┌────▼───┐
│ user.  │      │ task.  │     │notif.  │
│ queue  │      │ queue  │     │ queue  │
└────────┘      └────────┘     └────────┘
    │                 │              │
┌───▼────┐      ┌────▼───┐     ┌────▼───┐
│ User   │      │ Task   │     │Notif.  │
│Service │      │Service │     │Service │
└────────┘      └────────┘     └────────┘
```

### 消息格式

```json
{
  "event_type": "task.assigned",
  "timestamp": "2026-04-17T10:30:00Z",
  "source": "task-service",
  "data": {
    "task_id": "uuid",
    "assignee_id": "uuid",
    "assigned_by": "uuid"
  },
  "correlation_id": "uuid",
  "version": "1.0"
}
```

### 消息流示例

**场景: 任务分配**

```
1. Task Service 接收 API 请求
   POST /tasks/{id}/assign

2. Task Service 更新数据库
   UPDATE tasks SET assignee_id = ? WHERE id = ?

3. Task Service 发布消息
   Exchange: app.events
   Routing Key: task.assigned
   Message: { task_id, assignee_id, ... }

4. Notification Service 接收消息
   Queue: notif.queue
   Routing Key Binding: task.*

5. Notification Service 创建通知
   INSERT INTO notifications ...

6. Notification Service 发送邮件
   Send email to assignee

7. Notification Service ACK 消息
   确认消息处理成功
```

## 影响

### 正面影响
- 实现服务间解耦，提高系统灵活性
- 异步处理提升系统性能
- 消息可靠性保证，避免数据丢失
- 易于监控和排查问题

### 负面影响
- 增加系统复杂度，需要学习RabbitMQ
- 需要额外部署和维护RabbitMQ集群
- 增加网络延迟（服务间通信）
- 需要处理消息幂等性问题

### 风险与缓解措施

| 风险 | 缓解措施 |
|------|---------|
| 消息丢失 | 开启消息持久化 + 消息确认机制 |
| 消息重复 | 实现幂等性处理（使用correlation_id去重） |
| 队列堆积 | 设置队列长度限制 + 监控告警 |
| 单点故障 | 部署RabbitMQ集群（镜像队列） |
| 性能瓶颈 | 监控消息速率，必要时扩容 |

## 实施计划

1. **Phase 1**: 部署RabbitMQ单节点（开发环境）
2. **Phase 2**: 实现消息发布/订阅SDK
3. **Phase 3**: 集成到各个服务
4. **Phase 4**: 实现消息幂等性处理
5. **Phase 5**: 部署RabbitMQ集群（生产环境）
6. **Phase 6**: 配置监控告警

## 监控指标

- 队列深度（Queue Depth）
- 消息速率（Message Rate）
- 消费者数量（Consumer Count）
- 消息确认率（ACK Rate）
- 内存使用（Memory Usage）

## 决策者

- 架构师: [待填写]
- 技术负责人: [待填写]

## 决策日期

2026-04-17

## 相关文档

- [ADR-001: 选择微服务架构](ADR-001-microservices-architecture.md)
- [架构文档](../tech/ARCH.md)
