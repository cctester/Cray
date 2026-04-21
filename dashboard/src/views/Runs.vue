<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { useWorkflowStore } from '../stores/workflow'
import { useRouter } from 'vue-router'

const store = useWorkflowStore()
const router = useRouter()

const statusFilter = ref<string>('all')
const searchQuery = ref('')

onMounted(async () => {
  await store.fetchRuns()
})

const filteredRuns = computed(() => {
  let runs = [...store.runs]
  
  if (statusFilter.value !== 'all') {
    runs = runs.filter(r => r.status === statusFilter.value)
  }
  
  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase()
    runs = runs.filter(r => 
      r.workflow_name.toLowerCase().includes(query)
    )
  }
  
  return runs.sort((a, b) => 
    new Date(b.started_at).getTime() - new Date(a.started_at).getTime()
  )
})

const statusCounts = computed(() => ({
  all: store.runs.length,
  running: store.runs.filter(r => r.status === 'running').length,
  success: store.runs.filter(r => r.status === 'success').length,
  failed: store.runs.filter(r => r.status === 'failed').length,
}))

function getStatusColor(status: string) {
  const colors: Record<string, string> = {
    pending: '#6b7280',
    running: '#3b82f6',
    success: '#10b981',
    failed: '#ef4444',
    stopped: '#f59e0b',
  }
  return colors[status] || '#6b7280'
}

function getStatusIcon(status: string) {
  const icons: Record<string, string> = {
    pending: '⏳',
    running: '🔄',
    success: '✅',
    failed: '❌',
    stopped: '⏹️',
  }
  return icons[status] || '❓'
}

function formatDuration(ms?: number) {
  if (!ms) return '-'
  if (ms < 1000) return `${ms}ms`
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`
  return `${(ms / 60000).toFixed(1)}m`
}

function formatDate(date: string) {
  return new Date(date).toLocaleString('zh-CN', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
}

function openRun(id: string) {
  router.push(`/runs/${id}`)
}

async function stopRun(id: string) {
  if (confirm('Stop this run?')) {
    await store.stopRun(id)
  }
}
</script>

<template>
  <div class="runs-page">
    <div class="page-header">
      <h1>Runs</h1>
    </div>

    <div class="toolbar">
      <div class="search-box">
        <input 
          v-model="searchQuery"
          type="text" 
          placeholder="Search by workflow name..."
          class="search-input"
        />
      </div>
      
      <div class="status-filters">
        <button 
          v-for="(count, status) in statusCounts" 
          :key="status"
          class="filter-btn"
          :class="{ active: statusFilter === status }"
          @click="statusFilter = status"
        >
          {{ status === 'all' ? 'All' : status }}
          <span class="count">{{ count }}</span>
        </button>
      </div>
    </div>

    <div class="runs-list" v-if="filteredRuns.length">
      <div 
        v-for="run in filteredRuns" 
        :key="run.id"
        class="run-card"
        @click="openRun(run.id)"
      >
        <div class="run-status">
          <span 
            class="status-badge"
            :style="{ background: getStatusColor(run.status) }"
          >
            {{ getStatusIcon(run.status) }}
          </span>
        </div>
        
        <div class="run-info">
          <h3 class="run-workflow">{{ run.workflow_name }}</h3>
          <p class="run-id">{{ run.workflow_name }} ({{ run.id.slice(0, 8) }})</p>
        </div>
        
        <div class="run-timing">
          <div class="timing-item">
            <span class="timing-label">Started</span>
            <span class="timing-value">{{ formatDate(run.started_at) }}</span>
          </div>
          <div class="timing-item" v-if="run.duration">
            <span class="timing-label">Duration</span>
            <span class="timing-value">{{ formatDuration(run.duration) }}</span>
          </div>
        </div>
        
        <div class="run-steps">
          <div class="steps-progress">
            <div class="steps-bar">
              <div 
                v-for="step in run.steps" 
                :key="step.name"
                class="step-dot"
                :style="{ background: getStatusColor(step.status) }"
                :title="step.name"
              ></div>
            </div>
            <span class="steps-count">
              {{ run.steps.filter(s => s.status === 'success').length }}/{{ run.steps.length }}
            </span>
          </div>
        </div>
        
        <div class="run-actions">
          <button 
            v-if="run.status === 'running'"
            class="btn btn-stop"
            @click.stop="stopRun(run.id)"
          >
            Stop
          </button>
          <button class="btn btn-view">
            View
          </button>
        </div>
      </div>
    </div>

    <div class="empty-state" v-else>
      <div class="empty-icon">📊</div>
      <h3>No runs found</h3>
      <p>Run a workflow to see execution history here</p>
      <router-link to="/workflows" class="btn btn-primary">
        Browse Workflows
      </router-link>
    </div>
  </div>
</template>

<style scoped>
.runs-page {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.page-header h1 {
  font-size: 24px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.toolbar {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
}

.search-box {
  flex: 1;
  min-width: 200px;
  max-width: 400px;
}

.search-input {
  width: 100%;
  padding: 10px 16px;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  background: var(--bg-secondary);
  color: var(--text-primary);
  font-size: 14px;
}

.search-input:focus {
  outline: none;
  border-color: var(--primary-color);
}

.status-filters {
  display: flex;
  gap: 8px;
}

.filter-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  border: 1px solid var(--border-color);
  border-radius: 6px;
  background: var(--bg-secondary);
  color: var(--text-secondary);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.filter-btn:hover {
  background: var(--bg-hover);
}

.filter-btn.active {
  background: var(--primary-color);
  border-color: var(--primary-color);
  color: white;
}

.filter-btn .count {
  background: rgba(0,0,0,0.1);
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 11px;
}

.runs-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.run-card {
  display: grid;
  grid-template-columns: auto 1fr auto auto auto;
  gap: 20px;
  align-items: center;
  background: var(--bg-secondary);
  border-radius: 12px;
  padding: 16px 20px;
  cursor: pointer;
  transition: all 0.2s;
}

.run-card:hover {
  background: var(--bg-hover);
}

.status-badge {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: 8px;
  font-size: 18px;
}

.run-info {
  min-width: 0;
}

.run-workflow {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 4px 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.run-id {
  font-size: 12px;
  font-family: 'Monaco', 'Menlo', monospace;
  color: var(--text-muted);
  margin: 0;
}

.run-timing {
  display: flex;
  gap: 16px;
}

.timing-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.timing-label {
  font-size: 11px;
  color: var(--text-muted);
  text-transform: uppercase;
}

.timing-value {
  font-size: 13px;
  color: var(--text-secondary);
}

.run-steps {
  min-width: 150px;
}

.steps-progress {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.steps-bar {
  display: flex;
  gap: 3px;
}

.step-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.steps-count {
  font-size: 11px;
  color: var(--text-muted);
}

.run-actions {
  display: flex;
  gap: 8px;
}

.btn {
  padding: 6px 12px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  border: none;
}

.btn-view {
  background: var(--bg-primary);
  color: var(--text-secondary);
  border: 1px solid var(--border-color);
}

.btn-view:hover {
  background: var(--bg-hover);
}

.btn-stop {
  background: #ef4444;
  color: white;
}

.btn-stop:hover {
  background: #dc2626;
}

.btn-primary {
  background: var(--primary-color);
  color: white;
  text-decoration: none;
  display: inline-block;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  text-align: center;
}

.empty-icon {
  font-size: 48px;
  margin-bottom: 16px;
}

.empty-state h3 {
  font-size: 18px;
  color: var(--text-primary);
  margin: 0 0 8px 0;
}

.empty-state p {
  font-size: 14px;
  color: var(--text-muted);
  margin: 0 0 20px 0;
}

@media (max-width: 900px) {
  .run-card {
    grid-template-columns: auto 1fr;
    gap: 12px;
  }
  
  .run-timing, .run-steps, .run-actions {
    grid-column: span 1;
  }
}
</style>
