<script setup lang="ts">
import type { WorkflowRun } from '../types'

defineProps<{
  runs: WorkflowRun[]
}>()

const statusColors: Record<string, string> = {
  pending: '#6b7280',
  running: '#3b82f6',
  success: '#10b981',
  failed: '#ef4444',
  stopped: '#f59e0b',
}

function formatDate(date: string) {
  return new Date(date).toLocaleString()
}

function formatDuration(ms: number) {
  if (!ms) return '-'
  if (ms < 1000) return `${ms}ms`
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`
  return `${(ms / 60000).toFixed(1)}m`
}
</script>

<template>
  <div class="runs-list">
    <div v-if="runs.length === 0" class="empty-state">
      No runs yet
    </div>

    <div v-else class="runs-items">
      <router-link
        v-for="run in runs"
        :key="run.id"
        :to="`/runs/${run.id}`"
        class="run-item"
      >
        <div class="run-status" :style="{ background: statusColors[run.status] }">
          {{ run.status === 'running' ? '▶' : run.status === 'success' ? '✓' : run.status === 'failed' ? '✗' : '○' }}
        </div>

        <div class="run-info">
          <div class="run-name">{{ run.workflow_name }}</div>
          <div class="run-time">{{ formatDate(run.started_at) }}</div>
        </div>

        <div class="run-duration">
          {{ formatDuration(run.duration || 0) }}
        </div>
      </router-link>
    </div>
  </div>
</template>

<style scoped>
.runs-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.empty-state {
  text-align: center;
  padding: 40px;
  color: var(--text-muted);
}

.run-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  background: var(--bg-primary);
  border-radius: 8px;
  text-decoration: none;
  transition: all 0.2s;
}

.run-item:hover {
  background: var(--bg-hover);
}

.run-status {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  color: white;
  font-size: 14px;
}

.run-info {
  flex: 1;
  min-width: 0;
}

.run-name {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.run-time {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 2px;
}

.run-duration {
  font-size: 13px;
  color: var(--text-secondary);
  font-variant-numeric: tabular-nums;
}
</style>
