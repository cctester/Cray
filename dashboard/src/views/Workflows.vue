<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { useWorkflowStore } from '../stores/workflow'
import { useRouter } from 'vue-router'

const store = useWorkflowStore()
const router = useRouter()
const searchQuery = ref('')
const sortBy = ref('name')

onMounted(async () => {
  await store.fetchWorkflows()
})

const filteredWorkflows = computed(() => {
  let workflows = [...store.workflows]
  
  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase()
    workflows = workflows.filter(w => 
      w.name.toLowerCase().includes(query) ||
      w.description.toLowerCase().includes(query)
    )
  }
  
  workflows.sort((a, b) => {
    if (sortBy.value === 'name') return a.name.localeCompare(b.name)
    if (sortBy.value === 'updated') return new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
    return 0
  })
  
  return workflows
})

function openWorkflow(id: string) {
  router.push(`/workflows/${id}`)
}

async function runWorkflow(workflow: any) {
  if (confirm(`Run workflow "${workflow.name}"?`)) {
    await store.runWorkflow(workflow.id)
    router.push('/runs')
  }
}

function formatDate(date: string) {
  return new Date(date).toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
}
</script>

<template>
  <div class="workflows-page">
    <div class="page-header">
      <h1>Workflows</h1>
      <router-link to="/editor" class="btn btn-primary">
        + New Workflow
      </router-link>
    </div>

    <div class="toolbar">
      <div class="search-box">
        <input 
          v-model="searchQuery"
          type="text" 
          placeholder="Search workflows..."
          class="search-input"
        />
      </div>
      <div class="sort-select">
        <select v-model="sortBy">
          <option value="name">Sort by name</option>
          <option value="updated">Sort by updated</option>
        </select>
      </div>
    </div>

    <div class="workflows-grid" v-if="filteredWorkflows.length">
      <div 
        v-for="workflow in filteredWorkflows" 
        :key="workflow.id"
        class="workflow-card"
        @click="openWorkflow(workflow.id)"
      >
        <div class="workflow-header">
          <h3 class="workflow-name">{{ workflow.name }}</h3>
          <span class="workflow-version">v{{ workflow.version }}</span>
        </div>
        
        <p class="workflow-description">{{ workflow.description || 'No description' }}</p>
        
        <div class="workflow-meta">
          <span class="meta-item">
            <span class="meta-icon">📋</span>
            {{ workflow.steps?.length || 0 }} steps
          </span>
          <span class="meta-item">
            <span class="meta-icon">📅</span>
            {{ formatDate(workflow.updated_at) }}
          </span>
        </div>

        <div class="workflow-actions">
          <button 
            class="btn btn-sm btn-run"
            @click.stop="runWorkflow(workflow)"
          >
            ▶ Run
          </button>
          <button 
            class="btn btn-sm btn-edit"
            @click.stop="openWorkflow(workflow.id)"
          >
            Edit
          </button>
        </div>
      </div>
    </div>

    <div class="empty-state" v-else-if="!store.loading">
      <div class="empty-icon">📭</div>
      <h3>No workflows found</h3>
      <p>Create your first workflow to get started</p>
      <router-link to="/editor" class="btn btn-primary">
        Create Workflow
      </router-link>
    </div>

    <div class="loading-state" v-if="store.loading">
      <div class="spinner"></div>
      <p>Loading workflows...</p>
    </div>
  </div>
</template>

<style scoped>
.workflows-page {
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

.toolbar {
  display: flex;
  gap: 16px;
}

.search-box {
  flex: 1;
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

.sort-select select {
  padding: 10px 16px;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  background: var(--bg-secondary);
  color: var(--text-primary);
  font-size: 14px;
}

.workflows-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px;
}

.workflow-card {
  background: var(--bg-secondary);
  border-radius: 12px;
  padding: 20px;
  cursor: pointer;
  transition: all 0.2s;
  border: 1px solid transparent;
}

.workflow-card:hover {
  border-color: var(--primary-color);
  transform: translateY(-2px);
}

.workflow-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 8px;
}

.workflow-name {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.workflow-version {
  font-size: 12px;
  color: var(--text-muted);
  background: var(--bg-primary);
  padding: 2px 8px;
  border-radius: 4px;
}

.workflow-description {
  font-size: 13px;
  color: var(--text-secondary);
  margin: 0 0 16px 0;
  line-height: 1.5;
}

.workflow-meta {
  display: flex;
  gap: 16px;
  margin-bottom: 16px;
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-muted);
}

.workflow-actions {
  display: flex;
  gap: 8px;
}

.btn {
  padding: 8px 16px;
  border-radius: 6px;
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

.btn-sm {
  padding: 6px 12px;
  font-size: 12px;
}

.btn-run {
  background: #10b981;
  color: white;
}

.btn-run:hover {
  background: #059669;
}

.btn-edit {
  background: var(--bg-primary);
  color: var(--text-secondary);
  border: 1px solid var(--border-color);
}

.btn-edit:hover {
  background: var(--bg-hover);
}

.empty-state, .loading-state {
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
</style>
