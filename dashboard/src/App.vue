<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import Sidebar from './components/Sidebar.vue'
import { wsService } from './services/websocket'
import { useWorkflowStore } from './stores/workflow'

const store = useWorkflowStore()

onMounted(async () => {
  // Apply theme from settings
  const stored = localStorage.getItem('cray-settings')
  if (stored) {
    const settings = JSON.parse(stored)
    document.documentElement.setAttribute('data-theme', settings.theme || 'dark')
  } else {
    document.documentElement.setAttribute('data-theme', 'dark')
  }

  // Connect WebSocket on app mount
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

onUnmounted(() => {
  // Cleanup on app unmount
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
