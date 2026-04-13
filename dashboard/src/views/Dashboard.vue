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
  successRate: store.successRate,
  active: store.runningWorkflows.length,
}))
</script>

<template>
  <div class="dashboard">
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
        color="#10b981"
      />
      <StatsCard
        title="Success Rate"
        :value="`${stats.successRate}%`"
        icon="✅"
        color="#8b5cf6"
      />
      <StatsCard
        title="Active"
        :value="stats.active"
        icon="🔄"
        color="#f59e0b"
      />
    </div>

    <div class="dashboard-content">
      <div class="recent-runs">
        <h2 class="section-title">Recent Runs</h2>
        <RunsList :runs="store.recentRuns" />
      </div>

      <div class="quick-actions">
        <h2 class="section-title">Quick Actions</h2>
        <div class="actions-grid">
          <router-link to="/editor" class="action-card">
            <span class="action-icon">✏️</span>
            <span class="action-label">New Workflow</span>
          </router-link>
          <router-link to="/workflows" class="action-card">
            <span class="action-icon">📂</span>
            <span class="action-label">Browse Workflows</span>
          </router-link>
          <router-link to="/plugins" class="action-card">
            <span class="action-icon">🔌</span>
            <span class="action-label">Manage Plugins</span>
          </router-link>
          <router-link to="/runs" class="action-card">
            <span class="action-icon">📊</span>
            <span class="action-label">View History</span>
          </router-link>
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

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

.dashboard-content {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 24px;
}

.section-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 16px 0;
}

.recent-runs {
  background: var(--bg-secondary);
  border-radius: 12px;
  padding: 20px;
}

.quick-actions {
  background: var(--bg-secondary);
  border-radius: 12px;
  padding: 20px;
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
  border-radius: 8px;
  text-decoration: none;
  transition: all 0.2s;
}

.action-card:hover {
  background: var(--bg-hover);
  transform: translateY(-2px);
}

.action-icon {
  font-size: 24px;
}

.action-label {
  font-size: 13px;
  color: var(--text-secondary);
}

@media (max-width: 1200px) {
  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .dashboard-content {
    grid-template-columns: 1fr;
  }
}
</style>
