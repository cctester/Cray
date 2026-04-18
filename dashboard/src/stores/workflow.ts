import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export interface Workflow {
  id: string
  name: string
  version: string
  description: string
  file_path: string
  steps: Step[]
  updated_at: string
}

export interface Step {
  name: string
  plugin: string
  action: string
  params: Record<string, any>
  depends_on?: string[]
}

export interface WorkflowRun {
  id: string
  workflow_id: string
  workflow_name: string
  status: 'pending' | 'running' | 'success' | 'failed' | 'stopped'
  started_at: string
  completed_at?: string
  duration?: number
  steps: RunStep[]
  input?: Record<string, any>
  output?: Record<string, any>
}

export interface RunStep {
  name: string
  status: 'pending' | 'running' | 'success' | 'failed' | 'skipped'
  duration?: number
  error?: string
  output?: any
  logs?: LogEntry[]
}

export interface LogEntry {
  timestamp: string
  level: 'debug' | 'info' | 'warning' | 'error'
  message: string
}

export interface Plugin {
  name: string
  version: string
  description: string
  actions: PluginAction[]
}

export interface PluginAction {
  name: string
  description: string
  params: PluginParam[]
}

export interface PluginParam {
  name: string
  type: string
  required: boolean
  default?: any
  description: string
}

export const useWorkflowStore = defineStore('workflow', () => {
  const workflows = ref<Workflow[]>([])
  const runs = ref<WorkflowRun[]>([])
  const plugins = ref<Plugin[]>([])
  const loading = ref(false)
  const connected = ref(false)
  const ws = ref<WebSocket | null>(null)

  const runningWorkflows = computed(() => 
    runs.value.filter(r => r.status === 'running')
  )

  const recentRuns = computed(() => 
    [...runs.value]
      .sort((a, b) => new Date(b.started_at).getTime() - new Date(a.started_at).getTime())
      .slice(0, 10)
  )

  const successRate = computed(() => {
    const completed = runs.value.filter(r => r.status !== 'running' && r.status !== 'pending')
    if (completed.length === 0) return 0
    const success = completed.filter(r => r.status === 'success').length
    return Math.round((success / completed.length) * 100)
  })

  async function fetchWorkflows() {
    try {
      const response = await fetch('/api/workflows')
      if (response.ok) {
        workflows.value = await response.json()
      }
    } catch (e) {
      console.error('Failed to fetch workflows:', e)
    }
  }

  async function fetchRuns() {
    try {
      const response = await fetch('/api/runs')
      if (response.ok) {
        runs.value = await response.json()
      }
    } catch (e) {
      console.error('Failed to fetch runs:', e)
    }
  }

  async function fetchPlugins() {
    try {
      const response = await fetch('/api/plugins')
      if (response.ok) {
        plugins.value = await response.json()
      }
    } catch (e) {
      console.error('Failed to fetch plugins:', e)
    }
  }

  async function runWorkflow(workflowId: string, input?: Record<string, any>) {
    try {
      const response = await fetch('/api/runs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ workflow_id: workflowId, input })
      })
      if (response.ok) {
        const run = await response.json()
        runs.value.unshift(run)
        return run
      }
    } catch (e) {
      console.error('Failed to run workflow:', e)
    }
  }

  async function stopRun(runId: string) {
    try {
      const response = await fetch(`/api/runs/${runId}/stop`, {
        method: 'POST'
      })
      if (response.ok) {
        await fetchRuns()
      }
    } catch (e) {
      console.error('Failed to stop run:', e)
    }
  }

  function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${window.location.host}/ws`
    
    ws.value = new WebSocket(wsUrl)
    
    ws.value.onopen = () => {
      connected.value = true
      console.log('WebSocket connected')
    }
    
    ws.value.onclose = () => {
      connected.value = false
      console.log('WebSocket disconnected')
      // Reconnect after 5 seconds
      setTimeout(connectWebSocket, 5000)
    }
    
    ws.value.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        handleWebSocketMessage(data)
      } catch (e) {
        console.error('Failed to parse WebSocket message:', e)
      }
    }
    
    ws.value.onerror = (error) => {
      console.error('WebSocket error:', error)
    }
  }

  function handleWebSocketMessage(data: any) {
    switch (data.type) {
      case 'run_started':
      case 'run_updated':
        updateRun(data.run)
        break
      case 'run_completed':
        updateRun(data.run)
        break
      case 'workflow_created':
        workflows.value.push(data.workflow)
        break
      case 'workflow_updated':
        const idx = workflows.value.findIndex(w => w.id === data.workflow.id)
        if (idx !== -1) {
          workflows.value[idx] = data.workflow
        }
        break
    }
  }

  function updateRun(run: WorkflowRun) {
    const idx = runs.value.findIndex(r => r.id === run.id)
    if (idx !== -1) {
      runs.value[idx] = run
    } else {
      runs.value.unshift(run)
    }
  }

  function disconnectWebSocket() {
    if (ws.value) {
      ws.value.close()
      ws.value = null
    }
  }

  return {
    workflows,
    runs,
    plugins,
    loading,
    connected,
    runningWorkflows,
    recentRuns,
    successRate,
    fetchWorkflows,
    fetchRuns,
    fetchPlugins,
    runWorkflow,
    stopRun,
    connectWebSocket,
    disconnectWebSocket,
  }
})
