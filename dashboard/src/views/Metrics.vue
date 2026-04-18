<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'

interface MetricsData {
  timestamp: number
  workflows: {
    total_runs: number
    successful: number
    failed: number
    running: number
    success_rate: number
    avg_duration: number
  }
  system: {
    memory_mb?: number
    cpu_percent?: number
    uptime_seconds: number
  }
}

const metrics = ref<MetricsData | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)
let refreshInterval: number | null = null

const fetchMetrics = async () => {
  try {
    const response = await fetch('/api/metrics/realtime')
    if (!response.ok) throw new Error('Failed to fetch metrics')
    metrics.value = await response.json()
    error.value = null
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Unknown error'
  } finally {
    loading.value = false
  }
}

const formatUptime = (seconds: number): string => {
  const days = Math.floor(seconds / 86400)
  const hours = Math.floor((seconds % 86400) / 3600)
  const mins = Math.floor((seconds % 3600) / 60)
  
  if (days > 0) return `${days}d ${hours}h`
  if (hours > 0) return `${hours}h ${mins}m`
  return `${mins}m`
}

const formatDuration = (seconds: number): string => {
  if (seconds < 1) return `${(seconds * 1000).toFixed(0)}ms`
  if (seconds < 60) return `${seconds.toFixed(1)}s`
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  return `${mins}m ${secs}s`
}

const successRateColor = computed(() => {
  if (!metrics.value) return '#6b7280'
  const rate = metrics.value.workflows.success_rate
  if (rate >= 90) return '#10b981'
  if (rate >= 70) return '#f59e0b'
  return '#ef4444'
})

onMounted(() => {
  fetchMetrics()
  refreshInterval = window.setInterval(fetchMetrics, 5000) // Refresh every 5s
})

onUnmounted(() => {
  if (refreshInterval) clearInterval(refreshInterval)
})
</script>

<template>
  <div class="metrics-page">
    <div class="page-header">
      <h1>Metrics & Monitoring</h1>
      <div class="refresh-info">
        <span class="refresh-badge">Auto-refresh: 5s</span>
      </div>
    </div>

    <div v-if="loading" class="loading">Loading metrics...</div>
    <div v-else-if="error" class="error">{{ error }}</div>

    <template v-else-if="metrics">
      <!-- Workflow Stats -->
      <div class="section">
        <h2>Workflow Statistics</h2>
        <div class="metrics-grid">
          <div class="metric-card">
            <div class="metric-value">{{ metrics.workflows.total_runs }}</div>
            <div class="metric-label">Total Runs</div>
          </div>
          <div class="metric-card success">
            <div class="metric-value">{{ metrics.workflows.successful }}</div>
            <div class="metric-label">Successful</div>
          </div>
          <div class="metric-card danger">
            <div class="metric-value">{{ metrics.workflows.failed }}</div>
            <div class="metric-label">Failed</div>
          </div>
          <div class="metric-card warning">
            <div class="metric-value">{{ metrics.workflows.running }}</div>
            <div class="metric-label">Running</div>
          </div>
        </div>
      </div>

      <!-- Success Rate -->
      <div class="section">
        <h2>Success Rate</h2>
        <div class="success-rate-container">
          <div class="success-rate-circle" :style="{ '--rate': metrics.workflows.success_rate, '--color': successRateColor }">
            <svg viewBox="0 0 100 100">
              <circle cx="50" cy="50" r="45" class="bg-circle" />
              <circle cx="50" cy="50" r="45" class="progress-circle" />
            </svg>
            <div class="rate-text">
              <span class="rate-value">{{ metrics.workflows.success_rate.toFixed(1) }}</span>
              <span class="rate-unit">%</span>
            </div>
          </div>
          <div class="rate-details">
            <div class="detail-item">
              <span class="detail-label">Avg Duration</span>
              <span class="detail-value">{{ formatDuration(metrics.workflows.avg_duration) }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- System Stats -->
      <div class="section">
        <h2>System Resources</h2>
        <div class="system-grid">
          <div class="system-card">
            <div class="system-icon">⏱️</div>
            <div class="system-info">
              <div class="system-value">{{ formatUptime(metrics.system.uptime_seconds) }}</div>
              <div class="system-label">Uptime</div>
            </div>
          </div>
          <div class="system-card" v-if="metrics.system.memory_mb">
            <div class="system-icon">💾</div>
            <div class="system-info">
              <div class="system-value">{{ metrics.system.memory_mb }} MB</div>
              <div class="system-label">Memory Usage</div>
            </div>
          </div>
          <div class="system-card" v-if="metrics.system.cpu_percent !== undefined">
            <div class="system-icon">⚡</div>
            <div class="system-info">
              <div class="system-value">{{ metrics.system.cpu_percent.toFixed(1) }}%</div>
              <div class="system-label">CPU Usage</div>
            </div>
          </div>
        </div>
      </div>

      <!-- Prometheus Link -->
      <div class="section">
        <h2>Export</h2>
        <div class="export-options">
          <a href="/api/metrics/prometheus" target="_blank" class="export-link">
            <span class="export-icon">📊</span>
            <span>Prometheus Metrics</span>
          </a>
          <a href="/api/metrics/summary" target="_blank" class="export-link">
            <span class="export-icon">📋</span>
            <span>JSON Summary</span>
          </a>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.metrics-page {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.page-header h1 {
  font-size: 24px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.refresh-badge {
  font-size: 12px;
  color: var(--text-muted);
  background: var(--bg-secondary);
  padding: 4px 12px;
  border-radius: 12px;
}

.section {
  background: var(--bg-secondary);
  border-radius: 12px;
  padding: 20px;
}

.section h2 {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 16px 0;
}

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

.metric-card {
  background: var(--bg-primary);
  border-radius: 10px;
  padding: 20px;
  text-align: center;
}

.metric-card.success {
  border-left: 3px solid #10b981;
}

.metric-card.danger {
  border-left: 3px solid #ef4444;
}

.metric-card.warning {
  border-left: 3px solid #f59e0b;
}

.metric-value {
  font-size: 32px;
  font-weight: 700;
  color: var(--text-primary);
}

.metric-label {
  font-size: 13px;
  color: var(--text-secondary);
  margin-top: 4px;
}

.success-rate-container {
  display: flex;
  align-items: center;
  gap: 40px;
}

.success-rate-circle {
  position: relative;
  width: 150px;
  height: 150px;
}

.success-rate-circle svg {
  transform: rotate(-90deg);
}

.bg-circle {
  fill: none;
  stroke: var(--bg-primary);
  stroke-width: 8;
}

.progress-circle {
  fill: none;
  stroke: var(--color, #10b981);
  stroke-width: 8;
  stroke-linecap: round;
  stroke-dasharray: 283;
  stroke-dashoffset: calc(283 - (283 * var(--rate, 0)) / 100);
  transition: stroke-dashoffset 0.5s ease;
}

.rate-text {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  text-align: center;
}

.rate-value {
  font-size: 36px;
  font-weight: 700;
  color: var(--text-primary);
}

.rate-unit {
  font-size: 16px;
  color: var(--text-secondary);
}

.rate-details {
  flex: 1;
}

.detail-item {
  display: flex;
  justify-content: space-between;
  padding: 12px 0;
  border-bottom: 1px solid var(--border-color);
}

.detail-label {
  color: var(--text-secondary);
}

.detail-value {
  font-weight: 600;
  color: var(--text-primary);
}

.system-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

.system-card {
  display: flex;
  align-items: center;
  gap: 16px;
  background: var(--bg-primary);
  border-radius: 10px;
  padding: 20px;
}

.system-icon {
  font-size: 32px;
}

.system-value {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
}

.system-label {
  font-size: 13px;
  color: var(--text-secondary);
}

.export-options {
  display: flex;
  gap: 16px;
}

.export-link {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 24px;
  background: var(--bg-primary);
  border-radius: 10px;
  text-decoration: none;
  color: var(--text-primary);
  transition: all 0.2s;
}

.export-link:hover {
  background: var(--bg-hover);
  transform: translateY(-2px);
}

.export-icon {
  font-size: 24px;
}

.loading, .error {
  text-align: center;
  padding: 40px;
  color: var(--text-muted);
}

.error {
  color: #ef4444;
}

@media (max-width: 900px) {
  .metrics-grid {
    grid-template-columns: repeat(2, 1fr);
  }
  
  .system-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 600px) {
  .metrics-grid,
  .system-grid {
    grid-template-columns: 1fr;
  }
  
  .success-rate-container {
    flex-direction: column;
  }
}
</style>
