<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useWorkflowStore } from '../stores/workflow'

const route = useRoute()
const router = useRouter()
const store = useWorkflowStore()

const workflowId = route.params.id as string
const versions = ref<any[]>([])
const loading = ref(true)
const rollingBack = ref(false)

onMounted(async () => {
  try {
    versions.value = await store.fetchVersions(workflowId)
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
      <div 
        v-for="version in versions" 
        :key="version.version_id"
        class="version-card"
      >
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
          <button 
            class="btn btn-secondary" 
            @click="rollback(version.version_id)"
            :disabled="rollingBack"
          >
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
</style>