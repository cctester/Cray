/**
 * Workflow store with WebSocket real-time updates
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { wsService, type RunInfo, type WorkflowInfo } from '@/services/websocket'

// API base URL
const API_BASE = '/api'

export interface Workflow {
  id: string
  name: string
  version: string
  description: string
  file_path?: string
  steps: Array<{
    name: string
    plugin: string
  }>
}

export interface Run {
  id: string
  workflow_id: string
  status: 'pending' | 'running' | 'success' | 'failed' | 'stopped'
  started_at: string
  completed_at: string | null
  input: Record<string, any>
  output: any
  error: string | null
  steps: Array<{
    name: string
    success: boolean
    output?: any
    error?: string
    duration_ms?: number
  }>
}

export interface Plugin {
  name: string
  description: string
  actions: string[]
}

export const useWorkflowStore = defineStore('workflow', () => {
  // State
  const workflows = ref<Workflow[]>([])
  const runs = ref<Run[]>([])
  const plugins = ref<Plugin[]>([])
  const currentWorkflow = ref<Workflow | null>(null)
  const currentRun = ref<Run | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const wsConnected = ref(false)

  // Computed
  const workflowCount = computed(() => workflows.value.length)
  const runningCount = computed(() => runs.value.filter(r => r.status === 'running').length)
  const successRate = computed(() => {
    const completed = runs.value.filter(r => r.status === 'success' || r.status === 'failed')
    if (completed.length === 0) return 0
    return Math.round((completed.filter(r => r.status === 'success').length / completed.length) * 100)
  })

  // WebSocket subscriptions
  let unsubscribers: Array<() => void> = []

  // Initialize WebSocket listeners
  function initWebSocket() {
    // Subscribe to run events
    unsubscribers.push(
      wsService.onRunStarted((run) => {
        const existingIndex = runs.value.findIndex(r => r.id === run.id)
        if (existingIndex >= 0) {
          runs.value[existingIndex] = run
        } else {
          runs.value.unshift(run)
        }
      })
    )

    unsubscribers.push(
      wsService.onRunUpdated((run) => {
        const index = runs.value.findIndex(r => r.id === run.id)
        if (index >= 0) {
          runs.value[index] = run
        }
      })
    )

    unsubscribers.push(
      wsService.onRunCompleted((run) => {
        const index = runs.value.findIndex(r => r.id === run.id)
        if (index >= 0) {
          runs.value[index] = run
        }
      })
    )

    unsubscribers.push(
      wsService.onStepStarted((runId, step) => {
        const run = runs.value.find(r => r.id === runId)
        if (run) {
          // Update step status if needed
          console.log(`[Store] Step ${step} started for run ${runId}`)
        }
      })
    )

    unsubscribers.push(
      wsService.onStepCompleted((runId, step, success, output) => {
        const run = runs.value.find(r => r.id === runId)
        if (run) {
          const stepInfo = run.steps.find(s => s.name === step)
          if (stepInfo) {
            stepInfo.success = success
            stepInfo.output = output
          }
        }
      })
    )

    // Subscribe to workflow events
    unsubscribers.push(
      wsService.onWorkflowCreated((workflow) => {
        const existing = workflows.value.find(w => w.id === workflow.id)
        if (!existing) {
          workflows.value.push({
            id: workflow.id,
            name: workflow.name,
            version: workflow.version,
            description: workflow.description,
            steps: workflow.steps
          })
        }
      })
    )

    unsubscribers.push(
      wsService.onWorkflowUpdated((workflow) => {
        const index = workflows.value.findIndex(w => w.id === workflow.id)
        if (index >= 0) {
          workflows.value[index] = {
            ...workflows.value[index],
            name: workflow.name,
            version: workflow.version,
            description: workflow.description,
            steps: workflow.steps
          }
        }
      })
    )

    wsConnected.value = true
  }

  // Cleanup WebSocket listeners
  function cleanupWebSocket() {
    unsubscribers.forEach(unsub => unsub())
    unsubscribers = []
    wsConnected.value = false
  }

  // Actions
  async function fetchWorkflows() {
    loading.value = true
    error.value = null

    try {
      const response = await fetch(`${API_BASE}/workflows`)
      if (!response.ok) throw new Error('Failed to fetch workflows')
      workflows.value = await response.json()
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Unknown error'
    } finally {
      loading.value = false
    }
  }

  async function fetchRuns() {
    loading.value = true
    error.value = null

    try {
      const response = await fetch(`${API_BASE}/runs`)
      if (!response.ok) throw new Error('Failed to fetch runs')
      runs.value = await response.json()
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Unknown error'
    } finally {
      loading.value = false
    }
  }

  async function fetchPlugins() {
    loading.value = true
    error.value = null

    try {
      const response = await fetch(`${API_BASE}/plugins`)
      if (!response.ok) throw new Error('Failed to fetch plugins')
      plugins.value = await response.json()
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Unknown error'
    } finally {
      loading.value = false
    }
  }

  async function fetchWorkflow(id: string) {
    loading.value = true
    error.value = null

    try {
      const response = await fetch(`${API_BASE}/workflows/${id}`)
      if (!response.ok) throw new Error('Workflow not found')
      currentWorkflow.value = await response.json()
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Unknown error'
    } finally {
      loading.value = false
    }
  }

  async function fetchRun(id: string) {
    loading.value = true
    error.value = null

    try {
      const response = await fetch(`${API_BASE}/runs/${id}`)
      if (!response.ok) throw new Error('Run not found')
      currentRun.value = await response.json()
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Unknown error'
    } finally {
      loading.value = false
    }
  }

  async function createWorkflow(workflow: Partial<Workflow>) {
    loading.value = true
    error.value = null

    try {
      const response = await fetch(`${API_BASE}/workflows`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(workflow)
      })
      if (!response.ok) throw new Error('Failed to create workflow')
      const created = await response.json()
      // WebSocket will handle the update
      return created
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Unknown error'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function updateWorkflow(id: string, workflow: Partial<Workflow>) {
    loading.value = true
    error.value = null

    try {
      const response = await fetch(`${API_BASE}/workflows/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(workflow)
      })
      if (!response.ok) throw new Error('Failed to update workflow')
      const updated = await response.json()
      // WebSocket will handle the update
      return updated
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Unknown error'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function deleteWorkflow(id: string) {
    loading.value = true
    error.value = null

    try {
      const response = await fetch(`${API_BASE}/workflows/${id}`, {
        method: 'DELETE'
      })
      if (!response.ok) throw new Error('Failed to delete workflow')
      workflows.value = workflows.value.filter(w => w.id !== id)
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Unknown error'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function fetchVersions(workflowId: string) {
    try {
      const response = await fetch(`/api/workflows/${workflowId}/versions`)
      if (response.ok) {
        return await response.json()
      }
    } catch (e) {
      console.error('Failed to fetch versions:', e)
    }
    return []
  }

  async function rollbackWorkflow(workflowId: string, versionId: string) {
    try {
      const response = await fetch(`/api/workflows/${workflowId}/rollback/${versionId}`, {
        method: 'POST'
      })
      if (response.ok) {
        return true
      }
    } catch (e) {
      console.error('Failed to rollback:', e)
    }
    return false
  }

  async function getDiff(workflowId: string, fromVersion: string, toVersion: string) {
    try {
      const response = await fetch(`/api/workflows/${workflowId}/diff/${fromVersion}/${toVersion}`)
      if (response.ok) {
        return await response.json()
      }
    } catch (e) {
      console.error('Failed to get diff:', e)
    }
    return null
  }

  async function runWorkflow(workflowId: string, input?: Record<string, any>) {
    loading.value = true
    error.value = null

    try {
      const response = await fetch(`${API_BASE}/runs`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ workflow_id: workflowId, input: input || {} })
      })
      if (!response.ok) throw new Error('Failed to start workflow')
      const run = await response.json()
      // WebSocket will handle the update
      return run
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Unknown error'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function stopRun(runId: string) {
    loading.value = true
    error.value = null

    try {
      const response = await fetch(`${API_BASE}/runs/${runId}/stop`, {
        method: 'POST'
      })
      if (!response.ok) throw new Error('Failed to stop run')
      // WebSocket will handle the update
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Unknown error'
      throw e
    } finally {
      loading.value = false
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
    wsConnected,

    // Computed
    workflowCount,
    runningCount,
    successRate,

    // Actions
    initWebSocket,
    cleanupWebSocket,
    fetchWorkflows,
    fetchRuns,
    fetchPlugins,
    fetchWorkflow,
    fetchRun,
    createWorkflow,
    updateWorkflow,
    deleteWorkflow,
    runWorkflow,
    stopRun,
    fetchVersions,
    rollbackWorkflow,
    getDiff
  }
})
