<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useWorkflowStore } from '../stores/workflow'
import YAML from 'yaml'

const route = useRoute()
const router = useRouter()
const store = useWorkflowStore()

const workflowId = route.params.id as string
const workflow = ref<any>(null)
const loading = ref(true)
const showYaml = ref(false)
const running = ref(false)

const yamlContent = computed(() => {
  if (!workflow.value) return ''
  return YAML.stringify(workflow.value)
})

const stepStats = computed(() => {
  if (!workflow.value?.steps) return { total: 0, plugins: {} }
  const steps = workflow.value.steps
  const plugins: Record<string, number> = {}
  steps.forEach((s: any) => {
    plugins[s.plugin] = (plugins[s.plugin] || 0) + 1
  })
  return { total: steps.length, plugins }
})

onMounted(async () => {
  try {
    const response = await fetch(`/api/workflows/${workflowId}`)
    workflow.value = await response.json()
  } catch (e) {
    console.error('Failed to load workflow:', e)
  } finally {
    loading.value = false
  }
})

async function runWorkflow() {
  if (running.value) return
  running.value = true
  try {
    await store.runWorkflow(workflowId)
    router.push('/runs')
  } finally {
    running.value = false
  }
}

function editWorkflow() {
  router.push(`/editor?id=${workflowId}`)
}

function getPluginColor(plugin: string) {
  const colors: Record<string, string> = {
    shell: '#6b7280',
    http: '#3b82f6',
    file: '#10b981',
    json: '#f59e0b',
    database: '#8b5cf6',
    git: '#ef4444',
    aws: '#f97316',
    redis: '#dc2626',
  }
  return colors[plugin] || '#64748b'
}

function formatDate(date: string) {
  return new Date(date).toLocaleString('zh-CN')
}
</script>

<template>
  <div class="workflow-detail">
    <div class="page-header">
      <div class="header-left">
        <button class="btn-back" @click="router.back()">← Back</button>
        <div class="header-info" v-if="workflow">
          <h1>{{ workflow.name }}</h1>
          <span class="version">v{{ workflow.version }}</span>
        </div>
      </div>
      <div class="header-actions">
        <button class="btn btn-secondary" @click="showYaml = !showYaml">
          {{ showYaml ? 'View Visual' : 'View YAML' }}
        </button>
        <button class="btn btn-secondary" @click="router.push(`/workflows/${workflowId}/versions`)">
          📜 Versions
        </button>
        <button class="btn btn-secondary" @click="editWorkflow">
          ✏️ Edit
        </button>
        <button 
          class="btn btn-primary" 
          @click="runWorkflow"
          :disabled="running"
        >
          {{ running ? 'Starting...' : '▶ Run' }}
        </button>
      </div>
    </div>

    <div class="loading" v-if="loading">
      <div class="spinner"></div>
    </div>

    <template v-else-if="workflow">
      <!-- YAML View -->
      <div class="yaml-view" v-if="showYaml">
        <pre class="yaml-content">{{ yamlContent }}</pre>
      </div>

      <!-- Visual View -->
      <div class="visual-view" v-else>
        <div class="info-grid">
          <div class="info-card">
            <h3>Description</h3>
            <p>{{ workflow.description || 'No description provided' }}</p>
          </div>
          
          <div class="info-card">
            <h3>File Path</h3>
            <p class="mono">{{ workflow.file_path }}</p>
          </div>
          
          <div class="info-card">
            <h3>Last Updated</h3>
            <p>{{ formatDate(workflow.updated_at) }}</p>
          </div>
          
          <div class="info-card">
            <h3>Steps</h3>
            <p>{{ stepStats.total }} steps across {{ Object.keys(stepStats.plugins).length }} plugins</p>
          </div>
        </div>

        <div class="steps-section">
          <h2>Workflow Steps</h2>
          <div class="steps-flow">
            <div 
              v-for="(step, index) in workflow.steps" 
              :key="step.name"
              class="step-node"
            >
              <div class="step-connector" v-if="index > 0">
                <div class="connector-line"></div>
                <div class="connector-arrow">↓</div>
              </div>
              
              <div class="step-card">
                <div 
                  class="step-plugin-badge"
                  :style="{ background: getPluginColor(step.plugin) }"
                >
                  {{ step.plugin }}
                </div>
                <div class="step-info">
                  <h4 class="step-name">{{ step.name }}</h4>
                  <p class="step-action">{{ step.action }}</p>
                </div>
                <div class="step-params" v-if="Object.keys(step.params || {}).length">
                  <div 
                    v-for="(value, key) in step.params" 
                    :key="key"
                    class="param-item"
                  >
                    <span class="param-key">{{ key }}:</span>
                    <span class="param-value">{{ value }}</span>
                  </div>
                </div>
                <div class="step-meta" v-if="step.depends_on?.length">
                  <span class="depends-label">Depends on:</span>
                  <span 
                    v-for="dep in step.depends_on" 
                    :key="dep"
                    class="depends-tag"
                  >
                    {{ dep }}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="plugins-section">
          <h2>Plugins Used</h2>
          <div class="plugins-grid">
            <div 
              v-for="(count, plugin) in stepStats.plugins" 
              :key="plugin"
              class="plugin-chip"
              :style="{ borderColor: getPluginColor(plugin) }"
            >
              <span 
                class="plugin-dot"
                :style="{ background: getPluginColor(plugin) }"
              ></span>
              <span class="plugin-name">{{ plugin }}</span>
              <span class="plugin-count">{{ count }}x</span>
            </div>
          </div>
        </div>
      </div>
    </template>

    <div class="not-found" v-else>
      <h2>Workflow not found</h2>
      <p>The requested workflow could not be loaded.</p>
      <button class="btn btn-primary" @click="router.push('/workflows')">
        Back to Workflows
      </button>
    </div>
  </div>
</template>

<style scoped>
.workflow-detail {
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

.version {
  font-size: 12px;
  color: var(--text-muted);
  background: var(--bg-secondary);
  padding: 2px 8px;
  border-radius: 4px;
  margin-left: 8px;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.btn-back {
  background: none;
  border: none;
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 14px;
}

.btn-back:hover {
  color: var(--text-primary);
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

.btn-primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-secondary {
  background: var(--bg-secondary);
  color: var(--text-secondary);
  border: 1px solid var(--border-color);
}

.btn-secondary:hover {
  background: var(--bg-hover);
}

.yaml-view {
  background: var(--bg-secondary);
  border-radius: 12px;
  padding: 20px;
}

.yaml-content {
  font-family: 'Monaco', 'Menlo', monospace;
  font-size: 13px;
  color: var(--text-primary);
  margin: 0;
  white-space: pre-wrap;
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

.info-card {
  background: var(--bg-secondary);
  border-radius: 8px;
  padding: 16px;
}

.info-card h3 {
  font-size: 12px;
  color: var(--text-muted);
  margin: 0 0 8px 0;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.info-card p {
  font-size: 14px;
  color: var(--text-primary);
  margin: 0;
}

.info-card p.mono {
  font-family: 'Monaco', 'Menlo', monospace;
  font-size: 12px;
}

.steps-section, .plugins-section {
  background: var(--bg-secondary);
  border-radius: 12px;
  padding: 20px;
}

.steps-section h2, .plugins-section h2 {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 20px 0;
}

.steps-flow {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.step-connector {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 8px 0;
}

.connector-line {
  width: 2px;
  height: 20px;
  background: var(--border-color);
}

.connector-arrow {
  color: var(--text-muted);
  font-size: 12px;
}

.step-card {
  background: var(--bg-primary);
  border-radius: 8px;
  padding: 16px;
  border: 1px solid var(--border-color);
}

.step-plugin-badge {
  display: inline-block;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
  color: white;
  text-transform: uppercase;
  margin-bottom: 8px;
}

.step-info {
  margin-bottom: 12px;
}

.step-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 4px 0;
}

.step-action {
  font-size: 12px;
  color: var(--text-secondary);
  margin: 0;
}

.step-params {
  background: var(--bg-secondary);
  border-radius: 4px;
  padding: 8px;
  margin-bottom: 12px;
}

.param-item {
  font-size: 12px;
  font-family: 'Monaco', 'Menlo', monospace;
}

.param-key {
  color: var(--text-muted);
}

.param-value {
  color: var(--text-primary);
}

.step-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.depends-label {
  font-size: 11px;
  color: var(--text-muted);
}

.depends-tag {
  font-size: 11px;
  background: var(--bg-secondary);
  padding: 2px 6px;
  border-radius: 4px;
  color: var(--text-secondary);
}

.plugins-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.plugin-chip {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: var(--bg-primary);
  border-radius: 20px;
  border: 2px solid;
}

.plugin-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.plugin-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
}

.plugin-count {
  font-size: 12px;
  color: var(--text-muted);
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
  margin-bottom: 8px;
}

.not-found p {
  color: var(--text-muted);
  margin-bottom: 20px;
}

@media (max-width: 1200px) {
  .info-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
