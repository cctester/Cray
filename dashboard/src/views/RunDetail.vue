<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useWorkflowStore } from '../stores/workflow'
import AnsiToHtml from 'ansi-to-html'

const route = useRoute()
const router = useRouter()
const store = useWorkflowStore()

const runId = route.params.id as string
const run = ref<any>(null)
const loading = ref(true)
const selectedStep = ref<string | null>(null)
const autoScroll = ref(true)

const ansiConverter = new AnsiToHtml()

onMounted(async () => {
  await loadRun()
})

async function loadRun() {
  try {
    const response = await fetch(`/api/runs/${runId}`)
    run.value = await response.json()
    if (run.value?.steps?.length && !selectedStep.value) {
      selectedStep.value = run.value.steps[0].name
    }
  } catch (e) {
    console.error('Failed to load run:', e)
  } finally {
    loading.value = false
  }
}

const selectedStepData = computed(() => {
  if (!run.value?.steps) return null
  return run.value.steps.find((s: any) => s.name === selectedStep.value)
})

const statusColor = computed(() => {
  if (!run.value) return '#6b7280'
  const colors: Record<string, string> = {
    pending: '#6b7280',
    running: '#3b82f6',
    success: '#10b981',
    failed: '#ef4444',
    stopped: '#f59e0b',
  }
  return colors[run.value.status] || '#6b7280'
})

const progress = computed(() => {
  if (!run.value?.steps) return 0
  const completed = run.value.steps.filter((s: any) => 
    ['success', 'failed', 'skipped'].includes(s.status)
  ).length
  return (completed / run.value.steps.length) * 100
})

function getStatusIcon(status: string) {
  const icons: Record<string, string> = {
    pending: '⏳',
    running: '🔄',
    success: '✅',
    failed: '❌',
    skipped: '⏭️',
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
  return new Date(date).toLocaleString('zh-CN')
}

function formatLog(log: any) {
  const html = ansiConverter.toHtml(log.message)
  return html
}

function getLogColor(level: string) {
  const colors: Record<string, string> = {
    debug: '#6b7280',
    info: '#3b82f6',
    warning: '#f59e0b',
    error: '#ef4444',
  }
  return colors[level] || '#6b7280'
}

async function stopRun() {
  if (confirm('Stop this run?')) {
    await store.stopRun(runId)
    await loadRun()
  }
}

async function rerun() {
  if (run.value) {
    await store.runWorkflow(run.value.workflow_id, run.value.input)
    router.push('/runs')
  }
}
</script>

<template>
  <div class="run-detail">
    <div class="page-header">
      <div class="header-left">
        <button class="btn-back" @click="router.back()">← Back</button>
        <div class="header-info" v-if="run">
          <h1>{{ run.workflow_name }}</h1>
          <span class="run-id">{{ run.id.slice(0, 8) }}</span>
        </div>
      </div>
      <div class="header-actions" v-if="run">
        <button 
          v-if="run.status === 'running'"
          class="btn btn-danger"
          @click="stopRun"
        >
          ⏹ Stop
        </button>
        <button 
          v-else
          class="btn btn-primary"
          @click="rerun"
        >
          ↻ Rerun
        </button>
      </div>
    </div>

    <div class="loading" v-if="loading">
      <div class="spinner"></div>
    </div>

    <template v-else-if="run">
      <!-- Status Overview -->
      <div class="status-card" :style="{ borderColor: statusColor }">
        <div class="status-left">
          <div 
            class="status-badge"
            :style="{ background: statusColor }"
          >
            {{ getStatusIcon(run.status) }}
          </div>
          <div class="status-info">
            <h2 class="status-text">{{ run.status.toUpperCase() }}</h2>
            <p class="status-time">
              Started {{ formatDate(run.started_at) }}
              <span v-if="run.completed_at">
                • Completed {{ formatDate(run.completed_at) }}
              </span>
            </p>
          </div>
        </div>
        <div class="status-right">
          <div class="stat">
            <span class="stat-value">{{ formatDuration(run.duration) }}</span>
            <span class="stat-label">Duration</span>
          </div>
          <div class="stat">
            <span class="stat-value">
              {{ run.steps.filter((s: any) => s.status === 'success').length }}/{{ run.steps.length }}
            </span>
            <span class="stat-label">Steps</span>
          </div>
        </div>
      </div>

      <!-- Progress Bar -->
      <div class="progress-section" v-if="run.status === 'running'">
        <div class="progress-bar">
          <div 
            class="progress-fill"
            :style="{ width: `${progress}%` }"
          ></div>
        </div>
        <span class="progress-text">{{ Math.round(progress) }}% complete</span>
      </div>

      <!-- Steps and Logs -->
      <div class="detail-grid">
        <!-- Steps List -->
        <div class="steps-panel">
          <h3>Steps</h3>
          <div class="steps-list">
            <div 
              v-for="step in run.steps"
              :key="step.name"
              class="step-item"
              :class="{ 
                active: selectedStep === step.name,
                running: step.status === 'running'
              }"
              @click="selectedStep = step.name"
            >
              <span 
                class="step-status"
                :style="{ color: getLogColor(step.status === 'failed' ? 'error' : 'info') }"
              >
                {{ getStatusIcon(step.status) }}
              </span>
              <span class="step-name">{{ step.name }}</span>
              <span class="step-duration">{{ formatDuration(step.duration) }}</span>
            </div>
          </div>
        </div>

        <!-- Step Details -->
        <div class="details-panel">
          <template v-if="selectedStepData">
            <h3>{{ selectedStepData.name }}</h3>
            
            <div class="detail-section" v-if="selectedStepData.error">
              <h4>Error</h4>
              <div class="error-box">
                {{ selectedStepData.error }}
              </div>
            </div>

            <div class="detail-section" v-if="selectedStepData.output">
              <h4>Output</h4>
              <pre class="output-box">{{ JSON.stringify(selectedStepData.output, null, 2) }}</pre>
            </div>

            <div class="detail-section">
              <h4>Logs</h4>
              <div class="logs-box">
                <div 
                  v-for="(log, idx) in selectedStepData.logs"
                  :key="idx"
                  class="log-line"
                >
                  <span class="log-time">{{ log.timestamp.split('T')[1]?.slice(0, 12) }}</span>
                  <span 
                    class="log-level"
                    :style="{ color: getLogColor(log.level) }"
                  >[{{ log.level.toUpperCase() }}]</span>
                  <span 
                    class="log-message"
                    v-html="formatLog(log)"
                  ></span>
                </div>
                <div v-if="!selectedStepData.logs?.length" class="no-logs">
                  No logs available
                </div>
              </div>
            </div>
          </template>
        </div>
      </div>

      <!-- Input/Output -->
      <div class="io-section" v-if="run.input && Object.keys(run.input).length">
        <h3>Input</h3>
        <pre class="io-box">{{ JSON.stringify(run.input, null, 2) }}</pre>
      </div>

      <div class="io-section" v-if="run.output">
        <h3>Output</h3>
        <pre class="io-box">{{ JSON.stringify(run.output, null, 2) }}</pre>
      </div>
    </template>

    <div class="not-found" v-else>
      <h2>Run not found</h2>
      <button class="btn btn-primary" @click="router.push('/runs')">
        Back to Runs
      </button>
    </div>
  </div>
</template>

<style scoped>
.run-detail {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.header-info h1 {
  font-size: 24px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.run-id {
  font-size: 12px;
  font-family: 'Monaco', 'Menlo', monospace;
  color: var(--text-muted);
  margin-left: 8px;
}

.btn-back {
  background: none;
  border: none;
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 14px;
}

.btn {
  padding: 8px 16px;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  border: none;
}

.btn-primary {
  background: var(--primary-color);
  color: white;
}

.btn-primary:hover {
  background: var(--primary-hover);
}

.btn-danger {
  background: #ef4444;
  color: white;
}

.btn-danger:hover {
  background: #dc2626;
}

.status-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: var(--bg-secondary);
  border-radius: 12px;
  padding: 20px;
  border-left: 4px solid;
}

.status-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.status-badge {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
}

.status-text {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.status-time {
  font-size: 13px;
  color: var(--text-muted);
  margin: 4px 0 0 0;
}

.status-right {
  display: flex;
  gap: 24px;
}

.stat {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.stat-value {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
}

.stat-label {
  font-size: 12px;
  color: var(--text-muted);
}

.progress-section {
  display: flex;
  align-items: center;
  gap: 12px;
}

.progress-bar {
  flex: 1;
  height: 8px;
  background: var(--bg-secondary);
  border-radius: 4px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: var(--primary-color);
  transition: width 0.3s;
}

.progress-text {
  font-size: 13px;
  color: var(--text-muted);
  white-space: nowrap;
}

.detail-grid {
  display: grid;
  grid-template-columns: 300px 1fr;
  gap: 24px;
}

.steps-panel, .details-panel {
  background: var(--bg-secondary);
  border-radius: 12px;
  padding: 20px;
}

.steps-panel h3, .details-panel h3 {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 16px 0;
}

.steps-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.step-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
}

.step-item:hover {
  background: var(--bg-hover);
}

.step-item.active {
  background: var(--primary-color);
  color: white;
}

.step-item.running {
  animation: pulse 1.5s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.7; }
}

.step-status {
  font-size: 14px;
}

.step-name {
  flex: 1;
  font-size: 13px;
}

.step-duration {
  font-size: 12px;
  color: var(--text-muted);
}

.step-item.active .step-duration {
  color: rgba(255,255,255,0.7);
}

.detail-section {
  margin-bottom: 20px;
}

.detail-section h4 {
  font-size: 12px;
  color: var(--text-muted);
  margin: 0 0 8px 0;
  text-transform: uppercase;
}

.error-box {
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: 6px;
  padding: 12px;
  color: #ef4444;
  font-family: 'Monaco', 'Menlo', monospace;
  font-size: 13px;
}

.output-box, .io-box {
  background: var(--bg-primary);
  border-radius: 6px;
  padding: 12px;
  font-family: 'Monaco', 'Menlo', monospace;
  font-size: 12px;
  color: var(--text-primary);
  overflow-x: auto;
  margin: 0;
}

.logs-box {
  background: var(--bg-primary);
  border-radius: 6px;
  padding: 12px;
  max-height: 400px;
  overflow-y: auto;
  font-family: 'Monaco', 'Menlo', monospace;
  font-size: 12px;
}

.log-line {
  display: flex;
  gap: 8px;
  padding: 2px 0;
}

.log-time {
  color: var(--text-muted);
  white-space: nowrap;
}

.log-level {
  font-weight: 600;
}

.log-message {
  color: var(--text-primary);
  word-break: break-all;
}

.no-logs {
  color: var(--text-muted);
  text-align: center;
  padding: 20px;
}

.io-section {
  background: var(--bg-secondary);
  border-radius: 12px;
  padding: 20px;
}

.io-section h3 {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 12px 0;
}

.loading {
  display: flex;
  justify-content: center;
  padding: 60px;
}

.spinner {
  width: 32px;
  height: 32px;
  border: 3px solid var(--border-color);
  border-top-color: var(--primary-color);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.not-found {
  text-align: center;
  padding: 60px;
}

.not-found h2 {
  color: var(--text-primary);
  margin-bottom: 20px;
}

@media (max-width: 900px) {
  .detail-grid {
    grid-template-columns: 1fr;
  }
}
</style>
