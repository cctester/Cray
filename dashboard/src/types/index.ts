export interface Workflow {
  id: string
  name: string
  version: string
  description: string
  file_path: string
  steps: WorkflowStep[]
  updated_at: string
}

export interface WorkflowStep {
  name: string
  plugin: string
  action: string
  params: Record<string, any>
  depends_on?: string[]
  condition?: string
  retry?: number
  retry_delay?: number
  on_error?: Record<string, any>
  continue_on_error?: boolean
}

export interface WorkflowRun {
  id: string
  workflow_id: string
  workflow_name: string
  status: RunStatus
  started_at: string
  completed_at?: string
  duration?: number
  steps: RunStep[]
  input?: Record<string, any>
  output?: Record<string, any>
}

export type RunStatus = 'pending' | 'running' | 'success' | 'failed' | 'stopped'

export interface RunStep {
  name: string
  status: RunStatus
  duration?: number
  error?: string
  output?: any
  logs?: LogEntry[]
}

export interface LogEntry {
  timestamp: string
  level: LogLevel
  message: string
}

export type LogLevel = 'debug' | 'info' | 'warning' | 'error'

export interface Plugin {
  name: string
  version: string
  description: string
  actions: PluginAction[]
}

export interface PluginAction {
  name: string
  description: string
  params: PluginParam[]
}

export interface PluginParam {
  name: string
  type: string
  required: boolean
  default?: any
  description: string
}

export interface Stats {
  workflows: number
  runs: number
  running: number
  successRate: number
}

export interface Settings {
  serverUrl: string
  theme: 'dark' | 'light' | 'auto'
  autoRefresh: boolean
  refreshInterval: number
  showNotifications: boolean
  logLevel: LogLevel
}
