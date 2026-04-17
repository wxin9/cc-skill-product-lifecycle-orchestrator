# 架构决策记录索引

本目录包含项目的重要架构决策记录（Architecture Decision Records, ADR）。

## ADR 列表

| 编号 | 标题 | 状态 | 日期 |
|------|------|------|------|
| [ADR-001](ADR-001-microservices-architecture.md) | 选择微服务架构 | Proposed | 2026-04-17 |
| [ADR-002](ADR-002-rabbitmq-message-queue.md) | 选择 RabbitMQ 作为消息队列 | Proposed | 2026-04-17 |

**合计**: 2 条 ADR

## ADR 状态说明

- **Proposed**: 提议中，等待审核和批准
- **Accepted**: 已接受，正在实施
- **Deprecated**: 已废弃，不再使用
- **Superseded**: 被新的 ADR 取代

## ADR 模板

创建新的 ADR 时，请使用以下模板：

```markdown
# ADR-NNN: 决策标题

## 状态
[Proposed | Accepted | Deprecated | Superseded by ADR-XXX]

## 背景
[描述背景和问题]

## 决策
[描述决策内容]

## 理由
[描述决策理由]

## 替代方案
[描述考虑过的其他方案]

## 影响
[描述决策的影响]

## 决策者
[列出决策参与者]

## 决策日期
[YYYY-MM-DD]

## 相关文档
[列出相关文档链接]
```

## 相关文档

- [架构文档](../tech/ARCH.md)
- [产品需求文档](../product/PRD.md)
