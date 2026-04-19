<template>
  <div class="dashboard">
    <header class="dashboard-header">
      <h1>Cray Dashboard</h1>
      <div class="connection-status" :class="{ connected: wsConnected }">
        <span class="status-dot"></span>
        {{ wsConnected ? 'Connected' : 'Disconnected' }}
      </div>
    </header>

    <!-- Stats Cards -->
    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-icon">📋</div>
        <div class="stat-content">
          <div class="stat-value">{{ workflowCount }}</div>
          <div class="stat-label">Workflows</div>
        </div>
      </div>

      <div class="stat-card">
        <div class="stat-icon">▶️</div>
        <div class="stat-content">
          <div class="stat-value">{{ runningCount }}</div>
          <div class="stat-label">Running</div>
        </div>
      </div>

      <div class="stat-card">
        <div class="stat-icon">✅</div>
        <div class="stat-content">
          <div class="stat-value">{{ successRate }}%</div>
          <div class="stat-label">Success Rate</div>
        </div>
      </div>

      <div class="stat-card">
        <div class="stat-icon">📊</div>
        <div class="stat-content">
          <div class="stat-value">{{ runs.length }}</div>
          <div class="stat-label">Total Runs</div>
        </div>
      </div>
    </div>

    <!-- Recent Runs -->
    <section class="recent-runs">
      <h2>Recent Runs</h2>
      <div class="runs-list" v-if="runs.length > 0">
        <div
          v-for="run in recentRuns"
          :key="run.id"
          class="run-item"
          :class="run.status"
        >
          <div class="run-info">
            <span class="run-workflow">{{ run.workflow_id }}</span>
            <span class="run-id">#{{ run.id }}</span>
          </div>
          <div class="run-status">
            <span class="status-badge" :class="run.status">
              {{ run.status }}
            </span>
          </div>
          <div class="run-time">
            {{ formatTime(run.started_at) }}
          </div>
          <div class="run-steps" v-if="run.steps.length > 0">
            {{ run.steps.filter(s => s.success).length }}/{{ run.steps.length }} steps
          </div>
        </div>
      </div>
      <div class="empty-state" v-else>
        No runs yet. Start a workflow to see results here.
      </div>
    </section>

    <!-- Workflows -->
    <section class="workflows">
      <h2>Workflows</h2>
      <div class="workflows-grid" v-if="workflows.length > 0">
        <div
          v-for="workflow in workflows"
          :key="workflow.id"
          class="workflow-card"
        >
          <h3>{{ workflow.name }}</h3>
          <p class="workflow-desc">{{ workflow.description || 'No description' }}</p>
          <div class="workflow-meta">
            <span>v{{ workflow.version }}</span>
            <span>{{ workflow.steps?.length || 0 }} steps</span>
          </div>
          <div class="workflow-actions">
            <button @click="runWorkflowHandler(workflow.id)" class="btn-run">
              Run
            </button>
            <router-link :to="`/editor/${workflow.id}`" class="btn-edit">
              Edit
            </router-link>
          </div>
        </div>
      </div>
      <div class="empty-state" v-else>
        No workflows. Create one in the Editor.
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted } from 'vue'
import { useWorkflowStore } from '@/stores/workflow'
import { wsService } from '@/services/websocket'

const store = useWorkflowStore()

// Computed
const workflows = computed(() => store.workflows)
const runs = computed(() => store.runs)
const workflowCount = computed(() => store.workflowCount)
const runningCount = computed(() => store.runningCount)
const successRate = computed(() => store.successRate)
const wsConnected = computed(() => store.wsConnected)

const recentRuns = computed(() => {
  return [...store.runs]
    .sort((a, b) => new Date(b.started_at).getTime() - new Date(a.started_at).getTime())
    .slice(0, 10)
})

// Methods
function formatTime(isoString: string): string {
  const date = new Date(isoString)
  return date.toLocaleTimeString()
}

async function runWorkflowHandler(workflowId: string) {
  try {
    await store.runWorkflow(workflowId)
  } catch (e) {
    console.error('Failed to run workflow:', e)
  }
}

// Lifecycle
onMounted(async () => {
  // Initialize WebSocket
  if (!wsService.isConnected()) {
    try {
      await wsService.connect()
      store.initWebSocket()
    } catch (e) {
      console.error('WebSocket connection failed:', e)
    }
  }

  // Fetch initial data
  await Promise.all([
    store.fetchWorkflows(),
    store.fetchRuns()
  ])
})

onUnmounted(() => {
  // Don't disconnect WebSocket - keep it alive for other components
})
</script>

<style scoped>
.dashboard {
  padding: 2rem;
  max-width: 1200px;
  margin: 0 auto;
}

.dashboard-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 2rem;
}

.dashboard-header h1 {
  font-size: 1.75rem;
  font-weight: 600;
  margin: 0;
}

.connection-status {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 1rem;
  background: #fee2e2;
  border-radius: 9999px;
  font-size: 0.875rem;
  color: #991b1b;
}

.connection-status.connected {
  background: #dcfce7;
  color: #166534;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: currentColor;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1rem;
  margin-bottom: 2rem;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 1.25rem;
  background: white;
  border-radius: 0.5rem;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.stat-icon {
  font-size: 2rem;
}

.stat-value {
  font-size: 1.5rem;
  font-weight: 600;
}

.stat-label {
  color: #6b7280;
  font-size: 0.875rem;
}

section {
  margin-bottom: 2rem;
}

section h2 {
  font-size: 1.25rem;
  margin-bottom: 1rem;
}

.runs-list {
  background: white;
  border-radius: 0.5rem;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
  overflow: hidden;
}

.run-item {
  display: grid;
  grid-template-columns: 1fr auto auto auto;
  gap: 1rem;
  padding: 1rem;
  border-bottom: 1px solid #f3f4f6;
  align-items: center;
}

.run-item:last-child {
  border-bottom: none;
}

.run-workflow {
  font-weight: 500;
}

.run-id {
  color: #6b7280;
  font-size: 0.875rem;
  margin-left: 0.5rem;
}

.status-badge {
  padding: 0.25rem 0.75rem;
  border-radius: 9999px;
  font-size: 0.75rem;
  font-weight: 500;
  text-transform: uppercase;
}

.status-badge.pending {
  background: #fef3c7;
  color: #92400e;
}

.status-badge.running {
  background: #dbeafe;
  color: #1e40af;
}

.status-badge.success {
  background: #dcfce7;
  color: #166534;
}

.status-badge.failed {
  background: #fee2e2;
  color: #991b1b;
}

.status-badge.stopped {
  background: #f3f4f6;
  color: #4b5563;
}

.run-time {
  color: #6b7280;
  font-size: 0.875rem;
}

.run-steps {
  color: #6b7280;
  font-size: 0.875rem;
}

.workflows-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 1rem;
}

.workflow-card {
  background: white;
  border-radius: 0.5rem;
  padding: 1.25rem;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.workflow-card h3 {
  margin: 0 0 0.5rem;
  font-size: 1.125rem;
}

.workflow-desc {
  color: #6b7280;
  font-size: 0.875rem;
  margin: 0 0 1rem;
}

.workflow-meta {
  display: flex;
  gap: 1rem;
  font-size: 0.75rem;
  color: #9ca3af;
  margin-bottom: 1rem;
}

.workflow-actions {
  display: flex;
  gap: 0.5rem;
}

.btn-run,
.btn-edit {
  padding: 0.5rem 1rem;
  border-radius: 0.375rem;
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  text-decoration: none;
  text-align: center;
}

.btn-run {
  background: #3b82f6;
  color: white;
  border: none;
}

.btn-run:hover {
  background: #2563eb;
}

.btn-edit {
  background: #f3f4f6;
  color: #374151;
  border: 1px solid #d1d5db;
}

.btn-edit:hover {
  background: #e5e7eb;
}

.empty-state {
  text-align: center;
  padding: 2rem;
  color: #6b7280;
  background: white;
  border-radius: 0.5rem;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}
</style>
