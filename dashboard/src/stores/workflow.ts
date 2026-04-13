import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Workflow, WorkflowRun, Plugin } from '../types'

export const useWorkflowStore = defineStore('workflow', () => {
  // State
  const workflows = ref<Workflow[]>([])
  const runs = ref<WorkflowRun[]>([])
  const plugins = ref<Plugin[]>([])
  const currentWorkflow = ref<Workflow | null>(null)
  const currentRun = ref<WorkflowRun | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  // WebSocket connection
  const ws = ref<WebSocket | null>(null)
  const connected = ref(false)

  // Computed
  const recentRuns = computed(() => {
    return [...runs.value]
      .sort((a, b) => new Date(b.started_at).getTime() - new Date(a.started_at).getTime())
      .slice(0, 10)
  })

  const runningWorkflows = computed(() => {
    return runs.value.filter(r => r.status === 'running')
  })

  const successRate = computed(() => {
    const completed = runs.value.filter(r => r.status === 'success' || r.status === 'failed')
    if (completed.length === 0) return 0
    const success = completed.filter(r => r.status === 'success').length
    return Math.round((success / completed.length) * 100)
  })

  // Actions
  async function fetchWorkflows() {
    loading.value = true
    try {
      const response = await fetch('/api/workflows')
      workflows.value = await response.json()
    } catch (e) {
      error.value = 'Failed to fetch workflows'
    } finally {
      loading.value = false
    }
  }

  async function fetchRuns() {
    try {
      const response = await fetch('/api/runs')
      runs.value = await response.json()
    } catch (e) {
      error.value = 'Failed to fetch runs'
    }
  }

  async function fetchPlugins() {
    try {
      const response = await fetch('/api/plugins')
      plugins.value = await response.json()
    } catch (e) {
      error.value = 'Failed to fetch plugins'
    }
  }

  async function runWorkflow(workflowId: string, input?: Record<string, any>) {
    try {
      const response = await fetch(`/api/workflows/${workflowId}/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ input }),
      })
      const run = await response.json()
      runs.value.unshift(run)
      return run
    } catch (e) {
      error.value = 'Failed to run workflow'
      throw e
    }
  }

  async function stopRun(runId: string) {
    try {
      await fetch(`/api/runs/${runId}/stop`, { method: 'POST' })
      const run = runs.value.find(r => r.id === runId)
      if (run) run.status = 'stopped'
    } catch (e) {
      error.value = 'Failed to stop run'
    }
  }

  function connectWebSocket() {
    if (ws.value) return

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    ws.value = new WebSocket(`${protocol}//${window.location.host}/ws`)

    ws.value.onopen = () => {
      connected.value = true
      console.log('WebSocket connected')
    }

    ws.value.onclose = () => {
      connected.value = false
      console.log('WebSocket disconnected')
      // Reconnect after 3 seconds
      setTimeout(connectWebSocket, 3000)
    }

    ws.value.onmessage = (event) => {
      const data = JSON.parse(event.data)
      handleWebSocketMessage(data)
    }
  }

  function handleWebSocketMessage(data: any) {
    switch (data.type) {
      case 'run_started':
        runs.value.unshift(data.run)
        break
      case 'run_updated':
        const index = runs.value.findIndex(r => r.id === data.run.id)
        if (index !== -1) {
          runs.value[index] = data.run
        }
        break
      case 'run_completed':
        const runIndex = runs.value.findIndex(r => r.id === data.run.id)
        if (runIndex !== -1) {
          runs.value[runIndex] = data.run
        }
        break
    }
  }

  function disconnectWebSocket() {
    if (ws.value) {
      ws.value.close()
      ws.value = null
    }
  }

  return {
    // State
    workflows,
    runs,
    plugins,
    currentWorkflow,
    currentRun,
    loading,
    error,
    connected,
    // Computed
    recentRuns,
    runningWorkflows,
    successRate,
    // Actions
    fetchWorkflows,
    fetchRuns,
    fetchPlugins,
    runWorkflow,
    stopRun,
    connectWebSocket,
    disconnectWebSocket,
  }
})
