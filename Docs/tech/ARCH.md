# 架构文档

## 1. 系统概述

本项目采用微服务架构，将原单体应用拆分为三个独立服务：任务服务、用户服务、通知服务。服务间通过消息队列（RabbitMQ）进行异步通信，实现松耦合和高可扩展性。

## 2. 系统边界与外部依赖

### 2.1 外部系统
- **数据库**: PostgreSQL（每个服务独立数据库）
- **消息队列**: RabbitMQ
- **缓存**: Redis（可选）
- **外部API**: 无

### 2.2 系统边界图

```
┌─────────────────────────────────────────────────────────────┐
│                        外部系统                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                 │
│  │PostgreSQL│  │ RabbitMQ │  │  Redis   │                 │
│  └──────────┘  └──────────┘  └──────────┘                 │
└─────────────────────────────────────────────────────────────┘
         ▲              ▲              ▲
         │              │              │
         │              │              │
┌────────┴──────────────┴──────────────┴────────────────────┐
│                      微服务系统                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │  用户服务     │  │  任务服务     │  │  通知服务     │    │
│  │ User Service │  │Task Service  │  │Notification  │    │
│  │              │  │              │  │  Service     │    │
│  │ Port: 8001   │  │ Port: 8002   │  │ Port: 8003   │    │
│  └──────────────┘  └──────────────┘  └──────────────┘    │
│         │                  │                  │           │
│         └──────────────────┴──────────────────┘           │
│                     消息队列通信                           │
└───────────────────────────────────────────────────────────┘
```

## 3. 技术选型

| 组件 | 技术栈 | 版本 | 理由 |
|------|--------|------|------|
| **后端框架** | FastAPI | 0.104+ | 高性能异步框架，自动API文档 |
| **数据库** | PostgreSQL | 14+ | 强事务支持，复杂查询能力 |
| **ORM** | SQLAlchemy | 2.0+ | 成熟的Python ORM，支持异步 |
| **消息队列** | RabbitMQ | 3.12+ | 可靠的消息传递，支持多种模式 |
| **容器化** | Docker | 24+ | 标准化部署环境 |
| **编排工具** | Kubernetes | 1.28+ | 容器编排，自动扩缩容 |
| **API网关** | Kong/Nginx | - | 统一入口，负载均衡 |

## 4. 系统架构图

```
                    ┌─────────────┐
                    │   客户端     │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │  API 网关   │
                    │  (Kong)     │
                    └──────┬──────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
   ┌────▼────┐        ┌────▼────┐        ┌────▼────┐
   │用户服务  │        │任务服务  │        │通知服务  │
   │8001     │        │8002     │        │8003     │
   └────┬────┘        └────┬────┘        └────┬────┘
        │                  │                  │
        │                  │                  │
   ┌────▼────┐        ┌────▼────┐        ┌────▼────┐
   │user_db  │        │task_db  │        │notif_db │
   └─────────┘        └─────────┘        └─────────┘
        │                  │                  │
        └──────────────────┼──────────────────┘
                           │
                    ┌──────▼──────┐
                    │  RabbitMQ   │
                    │  消息队列    │
                    └─────────────┘
```

## 5. 模块分解与职责

### 5.1 用户服务 (User Service)

**职责**: 用户认证、授权、用户信息管理

| 模块 | 职责 | API端点 |
|------|------|---------|
| AuthController | 用户登录/注册/登出 | POST /auth/login<br>POST /auth/register<br>POST /auth/logout |
| UserController | 用户信息CRUD | GET /users/{id}<br>PUT /users/{id}<br>DELETE /users/{id} |
| PermissionController | 权限管理 | GET /permissions<br>POST /permissions |

**数据库表**:
- users (用户信息)
- permissions (权限表)
- user_permissions (用户-权限关联表)

**消息队列**:
- 发布: user.created, user.updated, user.deleted
- 订阅: task.assigned, notification.required

### 5.2 任务服务 (Task Service)

**职责**: 任务创建、分配、状态管理、任务查询

| 模块 | 职责 | API端点 |
|------|------|---------|
| TaskController | 任务CRUD | POST /tasks<br>GET /tasks<br>GET /tasks/{id}<br>PUT /tasks/{id}<br>DELETE /tasks/{id} |
| AssignmentController | 任务分配 | POST /tasks/{id}/assign<br>PUT /tasks/{id}/reassign |
| StatusController | 状态流转 | PUT /tasks/{id}/status |

**数据库表**:
- tasks (任务信息)
- assignments (分配记录)
- status_history (状态历史)

**消息队列**:
- 发布: task.created, task.assigned, task.completed, task.cancelled
- 订阅: user.created, user.deleted

### 5.3 通知服务 (Notification Service)

**职责**: 邮件通知、站内信、推送通知

| 模块 | 职责 | API端点 |
|------|------|---------|
| NotificationController | 通知管理 | GET /notifications<br>PUT /notifications/{id}/read<br>DELETE /notifications/{id} |
| EmailController | 邮件发送 | POST /email/send |
| PushController | 推送通知 | POST /push/send |

**数据库表**:
- notifications (通知记录)
- notification_templates (通知模板)
- user_notification_settings (用户通知设置)

**消息队列**:
- 发布: notification.sent, notification.failed
- 订阅: task.assigned, task.completed, user.created

## 6. 数据模型

### 6.1 用户服务数据模型

```sql
-- 用户表
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    username VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT true
);

-- 权限表
CREATE TABLE permissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) UNIQUE NOT NULL,
    description TEXT
);

-- 用户-权限关联表
CREATE TABLE user_permissions (
    user_id UUID REFERENCES users(id),
    permission_id UUID REFERENCES permissions(id),
    PRIMARY KEY (user_id, permission_id)
);
```

### 6.2 任务服务数据模型

```sql
-- 任务表
CREATE TABLE tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(255) NOT NULL,
    description TEXT,
    status VARCHAR(50) DEFAULT 'pending',
    priority VARCHAR(20) DEFAULT 'medium',
    assignee_id UUID,
    creator_id UUID NOT NULL,
    due_date TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 分配记录表
CREATE TABLE assignments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID REFERENCES tasks(id),
    assignee_id UUID NOT NULL,
    assigned_by UUID NOT NULL,
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 状态历史表
CREATE TABLE status_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID REFERENCES tasks(id),
    old_status VARCHAR(50),
    new_status VARCHAR(50) NOT NULL,
    changed_by UUID NOT NULL,
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 6.3 通知服务数据模型

```sql
-- 通知表
CREATE TABLE notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    type VARCHAR(50) NOT NULL,
    title VARCHAR(255) NOT NULL,
    content TEXT,
    is_read BOOLEAN DEFAULT false,
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    read_at TIMESTAMP
);

-- 通知模板表
CREATE TABLE notification_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) UNIQUE NOT NULL,
    subject VARCHAR(255),
    body_template TEXT NOT NULL,
    type VARCHAR(50) NOT NULL
);
```

## 7. REST API 端点列表

### 7.1 用户服务 API

| 方法 | 端点 | 描述 | 认证 |
|------|------|------|------|
| POST | /auth/login | 用户登录 | 否 |
| POST | /auth/register | 用户注册 | 否 |
| POST | /auth/logout | 用户登出 | 是 |
| GET | /users/{id} | 获取用户信息 | 是 |
| PUT | /users/{id} | 更新用户信息 | 是 |
| DELETE | /users/{id} | 删除用户 | 是 |
| GET | /permissions | 获取权限列表 | 是 |

### 7.2 任务服务 API

| 方法 | 端点 | 描述 | 认证 |
|------|------|------|------|
| POST | /tasks | 创建任务 | 是 |
| GET | /tasks | 获取任务列表 | 是 |
| GET | /tasks/{id} | 获取任务详情 | 是 |
| PUT | /tasks/{id} | 更新任务 | 是 |
| DELETE | /tasks/{id} | 删除任务 | 是 |
| POST | /tasks/{id}/assign | 分配任务 | 是 |
| PUT | /tasks/{id}/status | 更新任务状态 | 是 |

### 7.3 通知服务 API

| 方法 | 端点 | 描述 | 认证 |
|------|------|------|------|
| GET | /notifications | 获取通知列表 | 是 |
| PUT | /notifications/{id}/read | 标记为已读 | 是 |
| DELETE | /notifications/{id} | 删除通知 | 是 |
| POST | /email/send | 发送邮件 | 内部调用 |
| POST | /push/send | 发送推送 | 内部调用 |

## 8. 消息队列通信模式

### 8.1 Exchange 和 Queue 设计

```
RabbitMQ 架构:

                    ┌──────────────────┐
                    │  topic exchange  │
                    │   app.events     │
                    └────────┬─────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
   ┌────▼────┐         ┌────▼────┐         ┌────▼────┐
   │user.    │         │task.    │         │notif.   │
   │queue    │         │queue    │         │queue    │
   └─────────┘         └─────────┘         └─────────┘
```

### 8.2 消息格式

**标准消息格式**:
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
  "correlation_id": "uuid"
}
```

### 8.3 消息流示例

**场景: 任务分配**

```
1. 用户通过API网关调用任务服务分配任务
   POST /tasks/{id}/assign

2. 任务服务更新数据库，发布消息
   → task.assigned → RabbitMQ

3. 通知服务订阅 task.assigned
   ← 接收消息
   → 创建通知记录
   → 发送邮件/推送

4. 用户服务订阅 task.assigned
   ← 接收消息（用于统计用户任务数）
```

## 9. 部署方案

### 9.1 容器化配置

**Docker Compose (开发环境)**:
```yaml
version: '3.8'

services:
  user-service:
    build: ./services/user-service
    ports:
      - "8001:8001"
    environment:
      - DATABASE_URL=postgresql://user:pass@user-db:5432/userdb
      - RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672
    depends_on:
      - user-db
      - rabbitmq

  task-service:
    build: ./services/task-service
    ports:
      - "8002:8002"
    environment:
      - DATABASE_URL=postgresql://user:pass@task-db:5432/taskdb
      - RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672
    depends_on:
      - task-db
      - rabbitmq

  notification-service:
    build: ./services/notification-service
    ports:
      - "8003:8003"
    environment:
      - DATABASE_URL=postgresql://user:pass@notif-db:5432/notifdb
      - RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672
    depends_on:
      - notif-db
      - rabbitmq

  user-db:
    image: postgres:14
    environment:
      - POSTGRES_DB=userdb
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass
    volumes:
      - user-db-data:/var/lib/postgresql/data

  task-db:
    image: postgres:14
    environment:
      - POSTGRES_DB=taskdb
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass
    volumes:
      - task-db-data:/var/lib/postgresql/data

  notif-db:
    image: postgres:14
    environment:
      - POSTGRES_DB=notifdb
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass
    volumes:
      - notif-db-data:/var/lib/postgresql/data

  rabbitmq:
    image: rabbitmq:3.12-management
    ports:
      - "5672:5672"
      - "15672:15672"
    volumes:
      - rabbitmq-data:/var/lib/rabbitmq

volumes:
  user-db-data:
  task-db-data:
  notif-db-data:
  rabbitmq-data:
```

### 9.2 Kubernetes 部署架构

```
Kubernetes Cluster
├── Namespace: production
│   ├── Deployment: user-service (3 replicas)
│   │   └── Service: user-service-svc
│   ├── Deployment: task-service (3 replicas)
│   │   └── Service: task-service-svc
│   ├── Deployment: notification-service (2 replicas)
│   │   └── Service: notification-service-svc
│   ├── StatefulSet: postgresql-user
│   ├── StatefulSet: postgresql-task
│   ├── StatefulSet: postgresql-notification
│   ├── StatefulSet: rabbitmq
│   └── Ingress: api-gateway
```

## 10. 非功能性需求

### 10.1 性能要求
- API响应时间 < 200ms (P95)
- 支持 100 并发用户
- 消息队列吞吐量 > 1000 msg/s

### 10.2 可用性
- 服务可用性 ≥ 99.5%
- 数据持久化保证
- 自动故障恢复

### 10.3 安全性
- JWT 认证
- HTTPS 加密传输
- 数据库访问控制
- API 网关限流

### 10.4 可观测性
- 日志聚合 (ELK Stack)
- 分布式追踪 (Jaeger)
- 监控告警 (Prometheus + Grafana)

## 11. 架构决策记录 (ADR)

### ADR-001: 选择微服务架构

**状态**: Proposed

**背景**:
原单体应用在业务增长后出现以下问题:
- 代码耦合度高，维护困难
- 部署周期长，影响整体系统
- 扩展性差，无法针对性扩容

**决策**:
采用微服务架构，拆分为三个独立服务: 用户服务、任务服务、通知服务

**理由**:
1. **独立部署**: 每个服务可独立部署，不影响其他服务
2. **技术灵活性**: 不同服务可选择最适合的技术栈
3. **可扩展性**: 可针对瓶颈服务单独扩容
4. **团队协作**: 不同团队可独立开发不同服务

**影响**:
- 增加系统复杂度
- 需要引入服务发现、配置中心等基础设施
- 运维成本增加
- 需要处理分布式事务问题

### ADR-002: 选择 RabbitMQ 作为消息队列

**状态**: Proposed

**背景**:
微服务间需要异步通信机制，解耦服务依赖

**决策**:
使用 RabbitMQ 作为消息队列中间件

**理由**:
1. **成熟稳定**: RabbitMQ 经过多年生产验证，稳定性高
2. **多种模式**: 支持多种消息模式 (直连、主题、扇出等)
3. **管理界面**: 提供Web管理界面，便于监控
4. **消息确认**: 支持消息确认机制，保证消息不丢失
5. **社区支持**: 活跃的社区和丰富的文档

**替代方案**:
- Kafka: 适合大数据流处理，对于当前规模过于复杂
- Redis Pub/Sub: 功能较简单，不支持消息持久化

**影响**:
- 需要额外部署和维护 RabbitMQ 集群
- 增加系统复杂度
- 需要处理消息幂等性问题

## 12. 审稿建议

### 待确认事项

1. [❓待确认: 服务拆分粒度] 当前拆分为3个服务是否合适？是否需要进一步拆分（如将权限管理独立为认证服务）？

2. [❓待确认: 数据一致性] 跨服务的业务操作如何保证数据一致性？是否需要引入分布式事务（如Saga模式）？

3. [❓待确认: API网关选型] 使用Kong还是Nginx作为API网关？Kong功能更强大但更复杂。

4. [❓待确认: 服务发现] 是否需要引入服务发现机制（如Consul、Eureka）？Kubernetes内置服务发现是否足够？

5. [❓待确认: 配置中心] 是否需要配置中心（如Apollo、Nacos）统一管理配置？

6. [❓待确认: 监控方案] 日志聚合和分布式追踪的具体实现方案？

### 审核要点

1. **服务边界**: 三个服务的职责划分是否清晰？是否存在职责重叠？
2. **数据库设计**: 每个服务独立数据库是否符合微服务原则？
3. **消息队列**: RabbitMQ的Exchange和Queue设计是否合理？
4. **API设计**: REST API端点设计是否符合RESTful规范？
5. **部署方案**: Kubernetes部署配置是否完整？是否需要HPA（自动扩缩容）？
6. **安全性**: 认证授权机制是否完善？是否需要OAuth2？
7. **性能**: 是否需要引入缓存层（Redis）？哪些接口需要缓存？

### 下一步行动

1. 确认上述待确认事项
2. 创建ADR文档并记录架构决策
3. 细化API接口文档（OpenAPI规范）
4. 设计数据库迁移脚本
5. 搭建开发环境（Docker Compose）
6. 实现服务间通信的SDK
