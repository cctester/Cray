<script setup lang="ts">
defineProps<{
  title: string
  value: string | number
  icon: string
  color: string
}>()
</script>

<template>
  <div class="stats-card">
    <div class="stats-icon" :style="{ background: color + '20', color }">
      {{ icon }}
    </div>
    <div class="stats-content">
      <div class="stats-value">{{ value }}</div>
      <div class="stats-title">{{ title }}</div>
    </div>
  </div>
</template>

<style scoped>
.stats-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px;
  background: var(--bg-secondary);
  border-radius: 12px;
  transition: transform 0.2s;
}

.stats-card:hover {
  transform: translateY(-2px);
}

.stats-icon {
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
  font-size: 24px;
}

.stats-content {
  flex: 1;
}

.stats-value {
  font-size: 28px;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1;
}

.stats-title {
  font-size: 13px;
  color: var(--text-secondary);
  margin-top: 4px;
}
</style>
