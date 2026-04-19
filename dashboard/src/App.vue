<script setup lang="ts">
import { onMounted } from 'vue'
import Sidebar from './components/Sidebar.vue'

onMounted(() => {
  const stored = localStorage.getItem('cray-settings')
  if (stored) {
    const settings = JSON.parse(stored)
    document.documentElement.setAttribute('data-theme', settings.theme || 'dark')
  } else {
    document.documentElement.setAttribute('data-theme', 'dark')
  }
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
