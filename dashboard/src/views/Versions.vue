<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useWorkflowStore } from '../stores/workflow'

const route = useRoute()
const router = useRouter()
const store = useWorkflowStore()

const workflowId = route.params.id as string
const versions = ref<any[]>([])
const loading = ref(true)
const rollingBack = ref(false)
const comparing = ref(false)
const diffResult = ref<any>(null)
const compareFrom = ref('')
const compareTo = ref('')

onMounted(async () => {
  try {
    versions.value = await store.fetchVersions(workflowId)
    if (versions.value.length >= 2) {
      compareFrom.value = versions.value[1].version_id
      compareTo.value = versions.value[0].version_id
    }
  } catch (e) {
    console.error('Failed to load versions:', e)
  } finally {
    loading.value = false
  }
})

async function rollback(versionId: string) {
  if (!confirm(`Rollback to version ${versionId}?`)) return

  rollingBack.value = true
  try {
    const success = await store.rollbackWorkflow(workflowId, versionId)
    if (success) {
      router.push(`/workflows/${workflowId}`)
    }
  } finally {
    rollingBack.value = false
  }
}

async function compareVersions() {
  if (!compareFrom.value || !compareTo.value) return

  comparing.value = true
  try {
    diffResult.value = await store.getDiff(workflowId, compareFrom.value, compareTo.value)
  } finally {
    comparing.value = false
  }
}

function formatDate(date: string) {
  return new Date(date).toLocaleString('zh-CN')
}
</script>

<template>
  <div class="versions-page">
    <div class="page-header">
      <button class="btn-back" @click="router.back()">← Back</button>
      <h1>{{ workflowId }} - Versions</h1>
    </div>

    <div class="loading" v-if="loading">
      <div class="spinner"></div>
    </div>

    <div class="versions-list" v-else-if="versions.length > 0">

      <!-- Compare section -->
      <div class="compare-section" v-if="versions.length >= 2">
        <h2>Compare Versions</h2>
        <div class="compare-controls">
          <select v-model="compareFrom" class="select-version">
            <option v-for="v in versions" :key="v.version_id" :value="v.version_id">
              {{ v.version_id }}
            </option>
          </select>
          <span class="compare-arrow">→</span>
          <select v-model="compareTo" class="select-version">
            <option v-for="v in versions" :key="v.version_id" :value="v.version_id">
              {{ v.version_id }}
            </option>
          </select>
          <button class="btn btn-primary" @click="compareVersions" :disabled="comparing">
            {{ comparing ? 'Comparing...' : 'Compare' }}
          </button>
        </div>

        <div class="diff-result" v-if="diffResult">
          <div class="diff-summary">
            <span class="diff-additions">+{{ diffResult.additions }}</span>
            <span class="diff-deletions">-{{ diffResult.deletions }}</span>
          </div>
          <div class="diff-changes">
            <div v-for="(change, idx) in diffResult.changes" :key="idx" class="diff-line" :class="change.type">
              {{ change.type === 'add' ? '+' : '-' }} {{ change.line }}
            </div>
          </div>
        </div>
      </div>

      <div v-for="version in versions" :key="version.version_id" class="version-card">
        <div class="version-info">
          <h3 class="version-id">{{ version.version_id }}</h3>
          <p class="version-date">{{ formatDate(version.created_at) }}</p>
          <p class="version-author" v-if="version.author">by {{ version.author }}</p>
          <p class="version-message" v-if="version.message">{{ version.message }}</p>
          <div class="version-tags" v-if="version.tags?.length">
            <span v-for="tag in version.tags" :key="tag" class="tag">{{ tag }}</span>
          </div>
        </div>
        <div class="version-actions">
          <button class="btn btn-secondary" @click="rollback(version.version_id)" :disabled="rollingBack">
            Rollback
          </button>
        </div>
      </div>
    </div>

    <div class="empty" v-else>
      <p>No versions found</p>
    </div>
  </div>
</template>

<style scoped>
.versions-page {
  max-width: 800px;
}

.page-header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 24px;
}

.page-header h1 {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.btn-back {
  padding: 8px 12px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  color: var(--text-primary);
  cursor: pointer;
}

.btn-back:hover {
  background: var(--bg-hover);
}

.loading {
  display: flex;
  justify-content: center;
  padding: 40px;
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

.versions-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.version-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  background: var(--bg-secondary);
  border-radius: 8px;
}

.version-info {
  flex: 1;
}

.version-id {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 4px 0;
}

.version-date {
  font-size: 12px;
  color: var(--text-secondary);
  margin: 0;
}

.version-author {
  font-size: 12px;
  color: var(--text-muted);
  margin: 0;
}

.version-message {
  font-size: 14px;
  color: var(--text-secondary);
  margin: 8px 0 0 0;
}

.version-tags {
  display: flex;
  gap: 8px;
  margin-top: 8px;
}

.tag {
  padding: 2px 8px;
  background: var(--bg-hover);
  border-radius: 4px;
  font-size: 12px;
  color: var(--text-secondary);
}

.version-actions {
  margin-left: 16px;
}

.empty {
  text-align: center;
  padding: 40px;
  color: var(--text-secondary);
}

.compare-section {
  padding: 16px;
  background: var(--bg-secondary);
  border-radius: 8px;
  margin-bottom: 16px;
}

.compare-section h2 {
  font-size: 16px;
  margin: 0 0 12px 0;
  color: var(--text-primary);
}

.compare-controls {
  display: flex;
  align-items: center;
  gap: 12px;
}

.select-version {
  padding: 8px 12px;
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  color: var(--text-primary);
}

.compare-arrow {
  color: var(--text-secondary);
}

.diff-result {
  margin-top: 16px;
  padding: 12px;
  background: var(--bg-primary);
  border-radius: 6px;
}

.diff-summary {
  display: flex;
  gap: 12px;
  margin-bottom: 12px;
}

.diff-additions {
  color: var(--success-color);
}

.diff-deletions {
  color: var(--error-color);
}

.diff-changes {
  font-family: monospace;
  font-size: 12px;
}

.diff-line {
  padding: 2px 0;
}

.diff-line.add {
  color: var(--success-color);
}

.diff-line.delete {
  color: var(--error-color);
}
</style>