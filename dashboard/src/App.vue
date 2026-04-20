<script setup lang="ts">
import { onMounted, onUnmounted, watch } from 'vue'
import Sidebar from './components/Sidebar.vue'
import { wsService } from './services/websocket'
import { useWorkflowStore } from './stores/workflow'
import { useSettings } from './stores/settings'

const store = useWorkflowStore()
const { settings } = useSettings()

onMounted(async () => {
  document.documentElement.setAttribute('data-theme', settings.theme)

  if (!wsService.isConnected()) {
    try {
      await wsService.connect()
      store.initWebSocket()
      console.log('[App] WebSocket connected')
    } catch (e) {
      console.error('[App] WebSocket connection failed:', e)
    }
  }
})

watch(() => settings.theme, (theme) => {
  document.documentElement.setAttribute('data-theme', theme)
})

onUnmounted(() => {
  store.cleanupWebSocket()
  wsService.disconnect()
})
</script>

<template>
  <div class="app-layout">
    <Sidebar />
    <main class="main-content">
      <router-view />
    </main>
  </div>
</template>

<style scoped>
.app-layout {
  display: flex;
  min-height: 100vh;
}

.main-content {
  flex: 1;
  margin-left: 240px;
  padding: 24px;
  background: var(--bg-primary) !important;
  min-height: 100vh;
}
</style>
