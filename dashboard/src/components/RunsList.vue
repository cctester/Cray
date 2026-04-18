<script setup lang="ts">
import { computed } from 'vue'
import type { WorkflowRun } from '../stores/workflow'

const props = defineProps<{
  runs: WorkflowRun[]
}>()

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
</script>

<template>
  <div class="runs-list">
    <div 
      v-for="run in runs" 
      :key="run.id"
      class="run-item"
    >
      <div 
        class="run-status"
        :style="{ background: getStatusColor(run.status) }"
      >
        {{ getStatusIcon(run.status) }}
      </div>
      <div class="run-info">
        <h4 class="run-workflow">{{ run.workflow_name }}</h4>
        <p class="run-time">{{ formatDate(run.started_at) }}</p>
      </div>
      <div class="run-duration">
        {{ formatDuration(run.duration) }}
      </div>
    </div>
    <div v-if="!runs.length" class="empty">
      No runs yet
    </div>
  </div>
</template>

<style scoped>
.runs-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.run-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  background: var(--bg-primary);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
}

.run-item:hover {
  background: var(--bg-hover);
}

.run-status {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
}

.run-info {
  flex: 1;
  min-width: 0;
}

.run-workflow {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
  margin: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.run-time {
  font-size: 12px;
  color: var(--text-muted);
  margin: 4px 0 0 0;
}

.run-duration {
  font-size: 13px;
  color: var(--text-secondary);
  font-family: 'Monaco', 'Menlo', monospace;
}

.empty {
  text-align: center;
  padding: 40px;
  color: var(--text-muted);
}
</style>
