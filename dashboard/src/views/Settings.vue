<script setup lang="ts">
import { ref, onMounted } from 'vue'

const settings = ref({
  serverUrl: 'http://localhost:8000',
  theme: 'dark',
  autoRefresh: true,
  refreshInterval: 5,
  showNotifications: true,
  logLevel: 'info',
})

const saving = ref(false)
const saved = ref(false)

onMounted(() => {
  const stored = localStorage.getItem('cray-settings')
  if (stored) {
    settings.value = { ...settings.value, ...JSON.parse(stored) }
  }
})

async function saveSettings() {
  saving.value = true
  try {
    localStorage.setItem('cray-settings', JSON.stringify(settings.value))
    const theme = settings.value.theme || 'dark'
    document.documentElement.setAttribute('data-theme', theme)
    console.log('Theme set to:', theme)
    await new Promise(r => setTimeout(r, 500))
    saved.value = true
    setTimeout(() => { saved.value = false }, 2000)
  } finally {
    saving.value = false
  }
}

function resetSettings() {
  settings.value = {
    serverUrl: 'http://localhost:8000',
    theme: 'dark',
    autoRefresh: true,
    refreshInterval: 5,
    showNotifications: true,
    logLevel: 'info',
  }
  onThemeChange()
  saveSettings()
}

function onThemeChange() {
  const theme = settings.value.theme
  if (theme === 'auto') {
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
    document.documentElement.setAttribute('data-theme', prefersDark ? 'dark' : 'light')
  } else {
    document.documentElement.setAttribute('data-theme', theme)
  }
  console.log('Theme changed to:', document.documentElement.getAttribute('data-theme'))
}
</script>

<template>
  <div class="settings-page">
    <div class="page-header">
      <h1>Settings</h1>
    </div>

    <div class="settings-content">
      <div class="settings-section">
        <h2>Connection</h2>
        
        <div class="setting-item">
          <label class="setting-label">
            Server URL
            <span class="setting-desc">Backend API endpoint</span>
          </label>
          <input 
            v-model="settings.serverUrl"
            type="text"
            class="setting-input"
            placeholder="http://localhost:8000"
          />
        </div>
      </div>

      <div class="settings-section">
        <h2>Appearance</h2>
        
        <div class="setting-item">
          <label class="setting-label">
            Theme
            <span class="setting-desc">Color scheme</span>
          </label>
          <select v-model="settings.theme" class="setting-select" @change="onThemeChange">
            <option value="dark">Dark</option>
            <option value="light">Light</option>
            <option value="auto">Auto</option>
          </select>
        </div>
      </div>

      <div class="settings-section">
        <h2>Behavior</h2>
        
        <div class="setting-item">
          <label class="setting-label">
            Auto Refresh
            <span class="setting-desc">Automatically update dashboard data</span>
          </label>
          <label class="toggle">
            <input type="checkbox" v-model="settings.autoRefresh" />
            <span class="toggle-slider"></span>
          </label>
        </div>

        <div class="setting-item" v-if="settings.autoRefresh">
          <label class="setting-label">
            Refresh Interval
            <span class="setting-desc">Seconds between refreshes</span>
          </label>
          <input 
            v-model.number="settings.refreshInterval"
            type="number"
            min="1"
            max="60"
            class="setting-input small"
          />
        </div>

        <div class="setting-item">
          <label class="setting-label">
            Show Notifications
            <span class="setting-desc">Browser notifications for workflow events</span>
          </label>
          <label class="toggle">
            <input type="checkbox" v-model="settings.showNotifications" />
            <span class="toggle-slider"></span>
          </label>
        </div>

        <div class="setting-item">
          <label class="setting-label">
            Log Level
            <span class="setting-desc">Minimum log level to display</span>
          </label>
          <select v-model="settings.logLevel" class="setting-select">
            <option value="debug">Debug</option>
            <option value="info">Info</option>
            <option value="warning">Warning</option>
            <option value="error">Error</option>
          </select>
        </div>
      </div>

      <div class="settings-actions">
        <button class="btn btn-secondary" @click="resetSettings">
          Reset to Defaults
        </button>
        <button 
          class="btn btn-primary"
          @click="saveSettings"
          :disabled="saving"
        >
          {{ saving ? 'Saving...' : saved ? '✓ Saved' : 'Save Settings' }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.settings-page {
  display: flex;
  flex-direction: column;
  gap: 24px;
  max-width: 600px;
}

.page-header h1 {
  font-size: 24px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.settings-content {
  display: flex;
  flex-direction: column;
  gap: 32px;
}

.settings-section {
  background: var(--bg-secondary);
  border-radius: 12px;
  padding: 20px;
}

.settings-section h2 {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 20px 0;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--border-color);
}

.setting-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 0;
}

.setting-item:not(:last-child) {
  border-bottom: 1px solid var(--border-color);
}

.setting-label {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.setting-label span:first-child {
  font-size: 14px;
  color: var(--text-primary);
}

.setting-desc {
  font-size: 12px;
  color: var(--text-muted);
}

.setting-input {
  padding: 8px 12px;
  border: 1px solid var(--border-color);
  border-radius: 6px;
  background: var(--bg-primary);
  color: var(--text-primary);
  font-size: 14px;
  min-width: 200px;
}

.setting-input.small {
  width: 80px;
  min-width: 80px;
}

.setting-input:focus {
  outline: none;
  border-color: var(--primary-color);
}

.setting-select {
  padding: 8px 12px;
  border: 1px solid var(--border-color);
  border-radius: 6px;
  background: var(--bg-primary);
  color: var(--text-primary);
  font-size: 14px;
  min-width: 120px;
}

.toggle {
  position: relative;
  display: inline-block;
  width: 48px;
  height: 26px;
}

.toggle input {
  opacity: 0;
  width: 0;
  height: 0;
}

.toggle-slider {
  position: absolute;
  cursor: pointer;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 26px;
  transition: 0.3s;
}

.toggle-slider:before {
  position: absolute;
  content: "";
  height: 18px;
  width: 18px;
  left: 4px;
  bottom: 3px;
  background-color: var(--text-muted);
  border-radius: 50%;
  transition: 0.3s;
}

.toggle input:checked + .toggle-slider {
  background-color: var(--primary-color);
  border-color: var(--primary-color);
}

.toggle input:checked + .toggle-slider:before {
  transform: translateX(22px);
  background-color: white;
}

.settings-actions {
  display: flex;
  gap: 12px;
  justify-content: flex-end;
}

.btn {
  padding: 10px 20px;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  border: none;
}

.btn:disabled {
  opacity: 0.6;
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
</style>
