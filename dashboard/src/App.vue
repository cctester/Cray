<script setup lang="ts">
import { useWorkflowStore } from './stores/workflow'
import Sidebar from './components/Sidebar.vue'
import Header from './components/Header.vue'

const workflowStore = useWorkflowStore()
</script>

<template>
  <div class="app">
    <Sidebar />
    <main class="main">
      <Header />
      <div class="content">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </div>
    </main>
  </div>
</template>

<style scoped>
.app {
  display: flex;
  min-height: 100vh;
  background: var(--bg-primary);
}

.main {
  flex: 1;
  display: flex;
  flex-direction: column;
  margin-left: 240px;
}

.content {
  flex: 1;
  padding: 24px;
  overflow-y: auto;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
