<script setup lang="ts">
import { onMounted, computed } from 'vue'
import { useWorkflowStore } from '../stores/workflow'
import StatsCard from '../components/StatsCard.vue'
import RunsList from '../components/RunsList.vue'

const store = useWorkflowStore()

onMounted(async () => {
  await Promise.all([
    store.fetchWorkflows(),
    store.fetchRuns(),
    store.fetchPlugins(),
  ])
  store.connectWebSocket()
})

const stats = computed(() => ({
  workflows: store.workflows.length,
  runs: store.runs.length,
  running: store.runningWorkflows.length,
  successRate: store.successRate,
}))

const recentRuns = computed(() => store.recentRuns.slice(0, 5))
</script>

<template>
  <div class="dashboard">
    <div class="dashboard-header">
      <h1>Dashboard</h1>
      <div class="header-actions">
        <router-link to="/editor" class="btn btn-primary">
          + New Workflow
        </router-link>
      </div>
    </div>

    <div class="stats-grid">
      <StatsCard
        title="Workflows"
        :value="stats.workflows"
        icon="📋"
        color="#3b82f6"
      />
      <StatsCard
        title="Total Runs"
        :value="stats.runs"
        icon="▶️"
        color="#8b5cf6"
      />
      <StatsCard
        title="Running"
        :value="stats.running"
        icon="🔄"
        color="#f59e0b"
      />
      <StatsCard
        title="Success Rate"
        :value="`${stats.successRate}%`"
        icon="✅"
        color="#10b981"
      />
    </div>

    <div class="dashboard-grid">
      <div class="panel recent-runs">
        <div class="panel-header">
          <h2>Recent Runs</h2>
          <router-link to="/runs" class="view-all">View All →</router-link>
        </div>
        <RunsList :runs="recentRuns" />
      </div>

      <div class="panel quick-actions">
        <div class="panel-header">
          <h2>Quick Actions</h2>
        </div>
        <div class="actions-grid">
          <router-link to="/workflows" class="action-card">
            <span class="action-icon">📋</span>
            <span class="action-label">Browse Workflows</span>
          </router-link>
          <router-link to="/editor" class="action-card">
            <span class="action-icon">✏️</span>
            <span class="action-label">Create Workflow</span>
          </router-link>
          <router-link to="/plugins" class="action-card">
            <span class="action-icon">🔌</span>
            <span class="action-label">View Plugins</span>
          </router-link>
          <router-link to="/runs" class="action-card">
            <span class="action-icon">📊</span>
            <span class="action-label">Run History</span>
          </router-link>
        </div>
      </div>

      <div class="panel workflows-panel">
        <div class="panel-header">
          <h2>Workflows</h2>
          <router-link to="/workflows" class="view-all">View All →</router-link>
        </div>
        <div class="workflows-list">
          <div 
            v-for="workflow in store.workflows.slice(0, 5)" 
            :key="workflow.id"
            class="workflow-item"
          >
            <div class="workflow-info">
              <h3 class="workflow-name">{{ workflow.name }}</h3>
              <p class="workflow-desc">{{ workflow.description || 'No description' }}</p>
            </div>
            <div class="workflow-meta">
              <span class="step-count">{{ workflow.steps?.length || 0 }} steps</span>
            </div>
          </div>
          <div v-if="!store.workflows.length" class="empty">
            No workflows yet
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.dashboard {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.dashboard-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.dashboard-header h1 {
  font-size: 24px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.btn {
  padding: 10px 20px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  text-decoration: none;
  border: none;
}

.btn-primary {
  background: var(--primary-color);
  color: white;
}

.btn-primary:hover {
  background: var(--primary-hover);
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

.dashboard-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  grid-template-rows: auto auto;
  gap: 24px;
}

.panel {
  background: var(--bg-secondary);
  border-radius: 12px;
  padding: 20px;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.panel-header h2 {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.view-all {
  font-size: 13px;
  color: var(--primary-color);
  text-decoration: none;
}

.view-all:hover {
  text-decoration: underline;
}

.actions-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.action-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 20px;
  background: var(--bg-primary);
  border-radius: 10px;
  text-decoration: none;
  transition: all 0.2s;
}

.action-card:hover {
  background: var(--bg-hover);
  transform: translateY(-2px);
}

.action-icon {
  font-size: 28px;
}

.action-label {
  font-size: 13px;
  color: var(--text-secondary);
  font-weight: 500;
}

.workflows-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.workflow-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px;
  background: var(--bg-primary);
  border-radius: 8px;
}

.workflow-info {
  flex: 1;
  min-width: 0;
}

.workflow-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.workflow-desc {
  font-size: 12px;
  color: var(--text-muted);
  margin: 4px 0 0 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.workflow-meta {
  display: flex;
  align-items: center;
  gap: 12px;
}

.step-count {
  font-size: 12px;
  color: var(--text-secondary);
  background: var(--bg-secondary);
  padding: 4px 8px;
  border-radius: 4px;
}

.empty {
  text-align: center;
  padding: 40px;
  color: var(--text-muted);
}

@media (max-width: 1200px) {
  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }
  
  .dashboard-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 600px) {
  .stats-grid {
    grid-template-columns: 1fr;
  }
}
</style>
