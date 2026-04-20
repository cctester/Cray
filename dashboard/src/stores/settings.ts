import { reactive, watch } from 'vue'

export type Theme = 'light' | 'dark'

export interface Settings {
  theme: Theme
}

const STORAGE_KEY = 'cray-settings'

const defaultSettings: Settings = {
  theme: 'dark'
}

function loadSettings(): Settings {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored) {
      return { ...defaultSettings, ...JSON.parse(stored) }
    }
  } catch (e) {
    console.error('[Settings] Failed to load:', e)
  }
  return { ...defaultSettings }
}

function saveSettings(settings: Settings): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(settings))
}

const settings = reactive<Settings>(loadSettings())

watch(
  () => settings.theme,
  (theme) => {
    document.documentElement.setAttribute('data-theme', theme)
    saveSettings({ theme })
  }
)

export function useSettings() {
  function setTheme(theme: Theme) {
    settings.theme = theme
  }

  function toggleTheme() {
    settings.theme = settings.theme === 'dark' ? 'light' : 'dark'
  }

  return {
    settings,
    setTheme,
    toggleTheme
  }
}