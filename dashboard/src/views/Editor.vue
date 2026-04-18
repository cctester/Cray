<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import YAML from 'yaml'
import { useWorkflowStore } from '../stores/workflow'

const route = useRoute()
const router = useRouter()
const store = useWorkflowStore()

const yamlContent = ref(`name: my-workflow
description: A new workflow
version: "1.0"

steps:
  - name: step-1
    plugin: shell
    action: exec
    params:
      command: echo "Hello, World!"
`)

const parsedWorkflow = computed(() => {
  try {
    return YAML.parse(yamlContent.value)
  } catch (e) {
    return null
  }
})

const validationErrors = computed(() => {
  const errors: string[] = []
  
  if (!parsedWorkflow.value) {
    errors.push('Invalid YAML syntax')
    return errors
  }
  
  if (!parsedWorkflow.value.name) {
    errors.push('Missing workflow name')
  }
  
  if (!parsedWorkflow.value.steps || !parsedWorkflow.value.steps.length) {
    errors.push('Workflow must have at least one step')
  }
  
  parsedWorkflow.value.steps?.forEach((step: any, i: number) => {
    if (!step.name) {
      errors.push(`Step ${i + 1}: missing name`)
    }
    if (!step.plugin) {
      errors.push(`Step ${i + 1}: missing plugin`)
    }
    if (!step.action) {
      errors.push(`Step ${i + 1}: missing action`)
    }
  })
  
  return errors
})

const isValid = computed(() => validationErrors.value.length === 0)

const saving = ref(false)
const running = ref(false)

onMounted(async () => {
  const workflowId = route.query.id as string
  if (workflowId) {
    try {
      const response = await fetch(`/api/workflows/${workflowId}`)
      const workflow = await response.json()
      yamlContent.value = YAML.stringify(workflow)
    } catch (e) {
      console.error('Failed to load workflow:', e)
    }
  }
})

function insertTemplate(template: string) {
  const templates: Record<string, string> = {
    step: `
  - name: new-step
    plugin: shell
    action: exec
    params:
      command: echo "step"
`,
    http: `
  - name: http-request
    plugin: http
    action: get
    params:
      url: https://api.example.com
`,
    condition: `
    condition: "{{ steps.previous-step.success }}"
`,
    retry: `
    retry: 3
    retry_delay: 2
`,
    parallel: `
parallel: true
max_parallel: 5
`,
    error: `
    on_error:
      log: "Step failed"
    continue_on_error: true
`,
  }
  
  yamlContent.value += templates[template] || ''
}

async function save() {
  if (!isValid.value) return
  
  saving.value = true
  try {
    const workflow = parsedWorkflow.value
    const method = route.query.id ? 'PUT' : 'POST'
    const url = route.query.id 
      ? `/api/workflows/${route.query.id}`
      : '/api/workflows'
    
    const response = await fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(workflow)
    })
    
    if (response.ok) {
      const saved = await response.json()
      router.push(`/workflows/${saved.id}`)
    }
  } catch (e) {
    console.error('Failed to save:', e)
  } finally {
    saving.value = false
  }
}

async function runWorkflow() {
  if (!isValid.value) return
  
  running.value = true
  try {
    // First save
    await save()
    
    // Then run
    const workflow = parsedWorkflow.value
    const response = await fetch('/api/workflows/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ yaml: yamlContent.value })
    })
    
    if (response.ok) {
      const run = await response.json()
      router.push(`/runs/${run.id}`)
    }
  } catch (e) {
    console.error('Failed to run:', e)
  } finally {
    running.value = false
  }
}

function formatYaml() {
  try {
    const parsed = YAML.parse(yamlContent.value)
    yamlContent.value = YAML.stringify(parsed)
  } catch (e) {
    // Invalid YAML, can't format
  }
}
</script>

<template>
  <div class="editor-page">
    <div class="page-header">
      <h1>Workflow Editor</h1>
      <div class="header-actions">
        <button 
          class="btn btn-secondary"
          @click="formatYaml"
        >
          Format
        </button>
        <button 
          class="btn btn-primary"
          @click="save"
          :disabled="!isValid || saving"
        >
          {{ saving ? 'Saving...' : 'Save' }}
        </button>
        <button 
          class="btn btn-run"
          @click="runWorkflow"
          :disabled="!isValid || running"
        >
          {{ running ? 'Starting...' : '▶ Run' }}
        </button>
      </div>
    </div>

    <div class="editor-layout">
      <div class="editor-main">
        <div class="editor-container">
          <div class="editor-header">
            <span class="file-name">workflow.yaml</span>
            <div class="validation-status" :class="{ valid: isValid }">
              {{ isValid ? '✓ Valid' : '✗ ' + validationErrors.length + ' errors' }}
            </div>
          </div>
          <textarea 
            v-model="yamlContent"
            class="yaml-editor"
            spellcheck="false"
          ></textarea>
        </div>

        <div class="errors-panel" v-if="validationErrors.length">
          <h4>Validation Errors</h4>
          <div class="error-list">
            <div 
              v-for="error in validationErrors"
              :key="error"
              class="error-item"
            >
              {{ error }}
            </div>
          </div>
        </div>
      </div>

      <div class="editor-sidebar">
        <div class="sidebar-section">
          <h3>Quick Insert</h3>
          <div class="insert-buttons">
            <button class="insert-btn" @click="insertTemplate('step')">
              + Step
            </button>
            <button class="insert-btn" @click="insertTemplate('http')">
              + HTTP
            </button>
            <button class="insert-btn" @click="insertTemplate('condition')">
              + Condition
            </button>
            <button class="insert-btn" @click="insertTemplate('retry')">
              + Retry
            </button>
            <button class="insert-btn" @click="insertTemplate('error')">
              + Error Handler
            </button>
            <button class="insert-btn" @click="insertTemplate('parallel')">
              + Parallel
            </button>
          </div>
        </div>

        <div class="sidebar-section">
          <h3>Preview</h3>
          <div class="preview-box" v-if="parsedWorkflow">
            <div class="preview-item">
              <span class="preview-label">Name:</span>
              <span class="preview-value">{{ parsedWorkflow.name }}</span>
            </div>
            <div class="preview-item">
              <span class="preview-label">Steps:</span>
              <span class="preview-value">{{ parsedWorkflow.steps?.length || 0 }}</span>
            </div>
            <div class="preview-item" v-if="parsedWorkflow.parallel">
              <span class="preview-label">Parallel:</span>
              <span class="preview-value">Yes (max: {{ parsedWorkflow.max_parallel || 10 }})</span>
            </div>
          </div>
          <div class="preview-box invalid" v-else>
            Invalid YAML
          </div>
        </div>

        <div class="sidebar-section">
          <h3>Steps</h3>
          <div class="steps-preview" v-if="parsedWorkflow?.steps">
            <div 
              v-for="(step, i) in parsedWorkflow.steps"
              :key="i"
              class="step-preview-item"
            >
              <span class="step-num">{{ i + 1 }}</span>
              <span class="step-name">{{ step.name }}</span>
              <span class="step-plugin">{{ step.plugin }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.editor-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
  height: calc(100vh - 120px);
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

.header-actions {
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
  border: none;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-secondary {
  background: var(--bg-secondary);
  color: var(--text-secondary);
  border: 1px solid var(--border-color);
}

.btn-secondary:hover:not(:disabled) {
  background: var(--bg-hover);
}

.btn-primary {
  background: var(--primary-color);
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background: var(--primary-hover);
}

.btn-run {
  background: #10b981;
  color: white;
}

.btn-run:hover:not(:disabled) {
  background: #059669;
}

.editor-layout {
  display: grid;
  grid-template-columns: 1fr 280px;
  gap: 16px;
  flex: 1;
  min-height: 0;
}

.editor-main {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: 0;
}

.editor-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: var(--bg-secondary);
  border-radius: 12px;
  overflow: hidden;
  min-height: 0;
}

.editor-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border-color);
}

.file-name {
  font-size: 13px;
  color: var(--text-muted);
  font-family: 'Monaco', 'Menlo', monospace;
}

.validation-status {
  font-size: 12px;
  color: #ef4444;
}

.validation-status.valid {
  color: #10b981;
}

.yaml-editor {
  flex: 1;
  background: transparent;
  border: none;
  color: var(--text-primary);
  font-family: 'Monaco', 'Menlo', monospace;
  font-size: 13px;
  line-height: 1.6;
  padding: 16px;
  resize: none;
}

.yaml-editor:focus {
  outline: none;
}

.errors-panel {
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: 8px;
  padding: 12px;
}

.errors-panel h4 {
  font-size: 12px;
  color: #ef4444;
  margin: 0 0 8px 0;
}

.error-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.error-item {
  font-size: 12px;
  color: #ef4444;
}

.editor-sidebar {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.sidebar-section {
  background: var(--bg-secondary);
  border-radius: 12px;
  padding: 16px;
}

.sidebar-section h3 {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-muted);
  margin: 0 0 12px 0;
  text-transform: uppercase;
}

.insert-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.insert-btn {
  padding: 6px 10px;
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  font-size: 12px;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.2s;
}

.insert-btn:hover {
  background: var(--bg-hover);
  border-color: var(--primary-color);
}

.preview-box {
  background: var(--bg-primary);
  border-radius: 6px;
  padding: 12px;
}

.preview-box.invalid {
  color: #ef4444;
}

.preview-item {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
  padding: 4px 0;
}

.preview-label {
  color: var(--text-muted);
}

.preview-value {
  color: var(--text-primary);
  font-weight: 500;
}

.steps-preview {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 200px;
  overflow-y: auto;
}

.step-preview-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px;
  background: var(--bg-primary);
  border-radius: 6px;
}

.step-num {
  width: 20px;
  height: 20px;
  background: var(--primary-color);
  color: white;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 600;
}

.step-name {
  flex: 1;
  font-size: 12px;
  color: var(--text-primary);
}

.step-plugin {
  font-size: 11px;
  color: var(--text-muted);
  background: var(--bg-secondary);
  padding: 2px 6px;
  border-radius: 4px;
}

@media (max-width: 900px) {
  .editor-layout {
    grid-template-columns: 1fr;
  }
  
  .editor-sidebar {
    display: none;
  }
}
</style>
