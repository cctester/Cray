<script setup lang="ts">
import { useWorkflowStore } from '../stores/workflow'
import { computed } from 'vue'

const store = useWorkflowStore()

const statusColor = computed(() => {
  return store.connected ? 'var(--success-color)' : 'var(--error-color)'
})

const statusText = computed(() => {
  return store.connected ? 'Connected' : 'Disconnected'
})
</script>

<template>
  <header class="header">
    <div class="header-left">
      <h1 class="page-title">
        <slot name="title">Dashboard</slot>
      </h1>
    </div>

    <div class="header-right">
      <div class="status-indicator">
        <span class="status-dot" :style="{ background: statusColor }"></span>
        <span class="status-text">{{ statusText }}</span>
      </div>

      <div class="running-count" v-if="store.runningWorkflows.length > 0">
        <span class="running-badge">{{ store.runningWorkflows.length }}</span>
        <span class="running-label">Running</span>
      </div>
    </div>
  </header>
</template>

<style scoped>
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 24px;
  background: var(--bg-secondary);
  border-bottom: 1px solid var(--border-color);
}

.page-title {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 24px;
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.status-text {
  font-size: 13px;
  color: var(--text-secondary);
}

.running-count {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  background: var(--primary-color);
  border-radius: 16px;
}

.running-badge {
  font-size: 13px;
  font-weight: 600;
  color: white;
}

.running-label {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.8);
}
</style>
