<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { useWorkflowStore } from '../stores/workflow'

const store = useWorkflowStore()
const searchQuery = ref('')
const selectedPlugin = ref<string | null>(null)

onMounted(async () => {
  await store.fetchPlugins()
})

const filteredPlugins = computed(() => {
  if (!searchQuery.value) return store.plugins
  const query = searchQuery.value.toLowerCase()
  return store.plugins.filter(p => 
    p.name.toLowerCase().includes(query) ||
    p.description.toLowerCase().includes(query)
  )
})

const selectedPluginData = computed(() => {
  if (!selectedPlugin.value) return null
  return store.plugins.find(p => p.name === selectedPlugin.value)
})

function getPluginColor(name: string) {
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
  return colors[name] || '#64748b'
}

function getPluginIcon(name: string) {
  const icons: Record<string, string> = {
    shell: '💻',
    http: '🌐',
    file: '📁',
    json: '📄',
    database: '🗄️',
    git: '📦',
    aws: '☁️',
    redis: '🔴',
  }
  return icons[name] || '🔌'
}
</script>

<template>
  <div class="plugins-page">
    <div class="page-header">
      <h1>Plugins</h1>
    </div>

    <div class="toolbar">
      <div class="search-box">
        <input 
          v-model="searchQuery"
          type="text" 
          placeholder="Search plugins..."
          class="search-input"
        />
      </div>
    </div>

    <div class="plugins-layout">
      <div class="plugins-list">
        <div 
          v-for="plugin in filteredPlugins"
          :key="plugin.name"
          class="plugin-card"
          :class="{ active: selectedPlugin === plugin.name }"
          @click="selectedPlugin = plugin.name"
        >
          <div 
            class="plugin-icon"
            :style="{ background: getPluginColor(plugin.name) }"
          >
            {{ getPluginIcon(plugin.name) }}
          </div>
          <div class="plugin-info">
            <h3 class="plugin-name">{{ plugin.name }}</h3>
            <p class="plugin-desc">{{ plugin.description }}</p>
          </div>
          <span class="plugin-version">v{{ plugin.version }}</span>
        </div>
      </div>

      <div class="plugin-detail" v-if="selectedPluginData">
        <div class="detail-header">
          <div 
            class="detail-icon"
            :style="{ background: getPluginColor(selectedPluginData.name) }"
          >
            {{ getPluginIcon(selectedPluginData.name) }}
          </div>
          <div class="detail-info">
            <h2>{{ selectedPluginData.name }}</h2>
            <p>{{ selectedPluginData.description }}</p>
          </div>
          <span class="detail-version">v{{ selectedPluginData.version }}</span>
        </div>

        <div class="actions-section">
          <h3>Actions</h3>
          <div class="actions-list">
            <div 
              v-for="action in selectedPluginData.actions"
              :key="action.name"
              class="action-card"
            >
              <h4 class="action-name">{{ action.name }}</h4>
              <p class="action-desc">{{ action.description }}</p>
              
              <div class="params-section" v-if="action.params?.length">
                <h5>Parameters</h5>
                <div class="params-table">
                  <div 
                    v-for="param in action.params"
                    :key="param.name"
                    class="param-row"
                  >
                    <span class="param-name">
                      {{ param.name }}
                      <span v-if="param.required" class="required">*</span>
                    </span>
                    <span class="param-type">{{ param.type }}</span>
                    <span class="param-default" v-if="param.default !== undefined">
                      default: {{ param.default }}
                    </span>
                    <span class="param-desc">{{ param.description }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="empty-detail" v-else>
        <div class="empty-icon">🔌</div>
        <p>Select a plugin to view details</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.plugins-page {
  display: flex;
  flex-direction: column;
  gap: 24px;
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

.plugins-layout {
  display: grid;
  grid-template-columns: 350px 1fr;
  gap: 24px;
  min-height: 500px;
}

.plugins-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.plugin-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  background: var(--bg-secondary);
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s;
  border: 2px solid transparent;
}

.plugin-card:hover {
  background: var(--bg-hover);
}

.plugin-card.active {
  border-color: var(--primary-color);
}

.plugin-icon {
  width: 40px;
  height: 40px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
}

.plugin-info {
  flex: 1;
  min-width: 0;
}

.plugin-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.plugin-desc {
  font-size: 12px;
  color: var(--text-muted);
  margin: 4px 0 0 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.plugin-version {
  font-size: 11px;
  color: var(--text-muted);
  background: var(--bg-primary);
  padding: 2px 8px;
  border-radius: 4px;
}

.plugin-detail {
  background: var(--bg-secondary);
  border-radius: 12px;
  padding: 24px;
}

.detail-header {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 24px;
  padding-bottom: 24px;
  border-bottom: 1px solid var(--border-color);
}

.detail-icon {
  width: 56px;
  height: 56px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28px;
}

.detail-info {
  flex: 1;
}

.detail-info h2 {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 4px 0;
}

.detail-info p {
  font-size: 14px;
  color: var(--text-secondary);
  margin: 0;
}

.detail-version {
  font-size: 12px;
  color: var(--text-muted);
  background: var(--bg-primary);
  padding: 4px 12px;
  border-radius: 6px;
}

.actions-section h3 {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 16px 0;
}

.actions-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.action-card {
  background: var(--bg-primary);
  border-radius: 8px;
  padding: 16px;
}

.action-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 4px 0;
  font-family: 'Monaco', 'Menlo', monospace;
}

.action-desc {
  font-size: 13px;
  color: var(--text-secondary);
  margin: 0 0 12px 0;
}

.params-section h5 {
  font-size: 11px;
  color: var(--text-muted);
  margin: 0 0 8px 0;
  text-transform: uppercase;
}

.params-table {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.param-row {
  display: grid;
  grid-template-columns: 120px 80px 100px 1fr;
  gap: 12px;
  font-size: 12px;
  padding: 8px;
  background: var(--bg-secondary);
  border-radius: 4px;
}

.param-name {
  font-family: 'Monaco', 'Menlo', monospace;
  color: var(--text-primary);
}

.required {
  color: #ef4444;
}

.param-type {
  color: var(--primary-color);
  font-family: 'Monaco', 'Menlo', monospace;
}

.param-default {
  color: var(--text-muted);
  font-family: 'Monaco', 'Menlo', monospace;
}

.param-desc {
  color: var(--text-secondary);
}

.empty-detail {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: var(--bg-secondary);
  border-radius: 12px;
  padding: 60px;
}

.empty-icon {
  font-size: 48px;
  margin-bottom: 16px;
}

.empty-detail p {
  color: var(--text-muted);
  margin: 0;
}

@media (max-width: 900px) {
  .plugins-layout {
    grid-template-columns: 1fr;
  }
  
  .plugin-detail {
    display: none;
  }
  
  .plugin-detail:only-child {
    display: block;
  }
}
</style>
