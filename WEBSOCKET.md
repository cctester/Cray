# WebSocket 实时更新功能

## 概述

Cray 现在支持 WebSocket 实时更新，允许前端实时接收工作流执行状态变化。

## 架构

### 后端 (Python/FastAPI)

**文件**: `src/cray/web/app.py`

- `ConnectionManager`: 管理 WebSocket 连接池
- `EventBroadcaster`: 广播工作流事件到所有连接的客户端
- WebSocket 端点: `/ws`

### 前端 (Vue 3/TypeScript)

**文件**: `dashboard/src/services/websocket.ts`

- `WebSocketService`: WebSocket 连接管理类
- 自动重连机制
- 心跳保活 (ping/pong)
- 事件订阅系统

**文件**: `dashboard/src/stores/workflow.ts`

- 集成 WebSocket 事件到 Pinia store
- 自动更新 workflows 和 runs 状态

## 事件类型

| 事件类型 | 描述 |
|---------|------|
| `run_started` | 工作流开始执行 |
| `run_updated` | 工作流状态更新 |
| `run_completed` | 工作流执行完成 |
| `step_started` | 步骤开始执行 |
| `step_completed` | 步骤执行完成 |
| `workflow_created` | 新工作流创建 |
| `workflow_updated` | 工作流更新 |

## 使用方法

### 前端组件中使用

```typescript
import { useWebSocket } from '@/services/websocket'

// 在组件中
const { connected, onRunStarted, onRunCompleted } = useWebSocket()

// 订阅事件
onRunStarted((run) => {
  console.log('Run started:', run.id)
})

onRunCompleted((run) => {
  console.log('Run completed:', run.status)
})
```

### 在 Store 中使用

```typescript
import { useWorkflowStore } from '@/stores/workflow'

const store = useWorkflowStore()

// WebSocket 在 App.vue 中自动初始化
// Store 会自动接收并处理 WebSocket 事件
```

## 测试

1. 启动后端服务:
```bash
cd cray
uvicorn cray.web.app:app --reload
```

2. 打开测试页面:
```
http://localhost:8000/test_websocket.html
```

3. 点击 "Connect" 连接 WebSocket

4. 在另一个终端触发工作流执行，观察实时更新

## API 端点

- `GET /ws` - WebSocket 连接端点
- `POST /api/runs` - 启动工作流执行 (会触发 WebSocket 事件)
- `POST /api/runs/{run_id}/stop` - 停止执行

## 配置

WebSocket 连接 URL 自动检测:
- 开发环境: `ws://localhost:8000/ws`
- 生产环境: 根据当前页面协议自动选择 `ws://` 或 `wss://`

## 注意事项

- WebSocket 连接在 App.vue 挂载时自动建立
- 支持自动重连 (最多 5 次，指数退避)
- 每 30 秒发送心跳 ping 保持连接
- 断线时会自动清理资源并尝试重连
