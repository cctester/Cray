/**
 * WebSocket service for real-time updates
 */

export interface WebSocketMessage {
  type: string
  run?: RunInfo
  workflow?: WorkflowInfo
  step?: string
  run_id?: string
  success?: boolean
  output?: any
  timestamp: string
}

export interface RunInfo {
  id: string
  workflow_id: string
  status: 'pending' | 'running' | 'success' | 'failed' | 'stopped'
  started_at: string
  completed_at: string | null
  input: Record<string, any>
  output: any
  error: string | null
  steps: StepResult[]
}

export interface StepResult {
  name: string
  success: boolean
  output?: any
  error?: string
  duration_ms?: number
}

export interface WorkflowInfo {
  id: string
  name: string
  version: string
  description: string
  steps: Array<{ name: string; plugin: string }>
}

type MessageHandler = (message: WebSocketMessage) => void

class WebSocketService {
  private ws: WebSocket | null = null
  private handlers: Map<string, Set<MessageHandler>> = new Map()
  private reconnectAttempts = 0
  private maxReconnectAttempts = 5
  private reconnectDelay = 1000
  private pingInterval: number | null = null

  connect(url?: string): Promise<void> {
    const wsUrl = url || this.getWebSocketUrl()

    return new Promise((resolve, reject) => {
      try {
        this.ws = new WebSocket(wsUrl)

        this.ws.onopen = () => {
          console.log('[WebSocket] Connected')
          this.reconnectAttempts = 0
          this.startPing()
          resolve()
        }

        this.ws.onmessage = (event) => {
          try {
            const message: WebSocketMessage = JSON.parse(event.data)
            this.handleMessage(message)
          } catch (e) {
            console.warn('[WebSocket] Failed to parse message:', event.data)
          }
        }

        this.ws.onclose = (event) => {
          console.log('[WebSocket] Disconnected:', event.code, event.reason)
          this.stopPing()
          this.attemptReconnect()
        }

        this.ws.onerror = (error) => {
          console.error('[WebSocket] Error:', error)
          reject(error)
        }
      } catch (error) {
        reject(error)
      }
    })
  }

  private getWebSocketUrl(): string {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    return `${protocol}//${host}/ws`
  }

  private startPing(): void {
    this.pingInterval = window.setInterval(() => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({ type: 'ping' }))
      }
    }, 30000) // Ping every 30 seconds
  }

  private stopPing(): void {
    if (this.pingInterval) {
      clearInterval(this.pingInterval)
      this.pingInterval = null
    }
  }

  private attemptReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.log('[WebSocket] Max reconnect attempts reached')
      return
    }

    this.reconnectAttempts++
    const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1)

    console.log(`[WebSocket] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`)

    setTimeout(() => {
      this.connect().catch(console.error)
    }, delay)
  }

  private handleMessage(message: WebSocketMessage): void {
    const handlers = this.handlers.get(message.type)
    if (handlers) {
      handlers.forEach((handler) => {
        try {
          handler(message)
        } catch (e) {
          console.error(`[WebSocket] Handler error for ${message.type}:`, e)
        }
      })
    }

    // Also call wildcard handlers
    const wildcardHandlers = this.handlers.get('*')
    if (wildcardHandlers) {
      wildcardHandlers.forEach((handler) => {
        try {
          handler(message)
        } catch (e) {
          console.error('[WebSocket] Wildcard handler error:', e)
        }
      })
    }
  }

  subscribe(eventType: string, handler: MessageHandler): () => void {
    if (!this.handlers.has(eventType)) {
      this.handlers.set(eventType, new Set())
    }
    this.handlers.get(eventType)!.add(handler)

    // Return unsubscribe function
    return () => {
      const handlers = this.handlers.get(eventType)
      if (handlers) {
        handlers.delete(handler)
      }
    }
  }

  // Convenience methods for common events
  onRunStarted(handler: (run: RunInfo) => void): () => void {
    return this.subscribe('run_started', (msg) => handler(msg.run!))
  }

  onRunUpdated(handler: (run: RunInfo) => void): () => void {
    return this.subscribe('run_updated', (msg) => handler(msg.run!))
  }

  onRunCompleted(handler: (run: RunInfo) => void): () => void {
    return this.subscribe('run_completed', (msg) => handler(msg.run!))
  }

  onStepStarted(handler: (runId: string, step: string) => void): () => void {
    return this.subscribe('step_started', (msg) => handler(msg.run_id!, msg.step!))
  }

  onStepCompleted(handler: (runId: string, step: string, success: boolean, output?: any) => void): () => void {
    return this.subscribe('step_completed', (msg) => handler(msg.run_id!, msg.step!, msg.success!, msg.output))
  }

  onWorkflowCreated(handler: (workflow: WorkflowInfo) => void): () => void {
    return this.subscribe('workflow_created', (msg) => handler(msg.workflow!))
  }

  onWorkflowUpdated(handler: (workflow: WorkflowInfo) => void): () => void {
    return this.subscribe('workflow_updated', (msg) => handler(msg.workflow!))
  }

  disconnect(): void {
    this.stopPing()
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
  }

  isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN
  }
}

// Singleton instance
export const wsService = new WebSocketService()

// Composable for Vue components
import { onMounted, onUnmounted, ref, type Ref } from 'vue'

export function useWebSocket() {
  const connected = ref(false)
  const lastMessage = ref<WebSocketMessage | null>(null)

  onMounted(async () => {
    if (!wsService.isConnected()) {
      try {
        await wsService.connect()
        connected.value = true
      } catch (e) {
        console.error('Failed to connect WebSocket:', e)
      }
    } else {
      connected.value = true
    }

    // Subscribe to all messages for tracking
    wsService.subscribe('*', (msg) => {
      lastMessage.value = msg
    })
  })

  onUnmounted(() => {
    // Don't disconnect on component unmount - keep connection alive
  })

  return {
    connected,
    lastMessage,
    subscribe: wsService.subscribe.bind(wsService),
    onRunStarted: wsService.onRunStarted.bind(wsService),
    onRunUpdated: wsService.onRunUpdated.bind(wsService),
    onRunCompleted: wsService.onRunCompleted.bind(wsService),
    onStepStarted: wsService.onStepStarted.bind(wsService),
    onStepCompleted: wsService.onStepCompleted.bind(wsService),
    onWorkflowCreated: wsService.onWorkflowCreated.bind(wsService),
    onWorkflowUpdated: wsService.onWorkflowUpdated.bind(wsService),
  }
}
