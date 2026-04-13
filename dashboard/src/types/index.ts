export interface Workflow {
  id: string
  name: string
  version: string
  description: string
  file_path: string
  steps: WorkflowStep[]
  created_at: string
  updated_at: string
}

export interface WorkflowStep {
  name: string
  plugin: string
  action: string
  params: Record<string, any>
  condition?: string
  retry?: RetryConfig
  timeout?: number
}

export interface RetryConfig {
  max_attempts: number
  delay: number
  backoff: 'fixed' | 'exponential'
}

export interface WorkflowRun {
  id: string
  workflow_id: string
  workflow_name: string
  status: 'pending' | 'running' | 'success' | 'failed' | 'stopped'
  started_at: string
  completed_at?: string
  duration?: number
  input: Record<string, any>
  output?: Record<string, any>
  error?: string
  steps: StepResult[]
}

export interface StepResult {
  name: string
  status: 'pending' | 'running' | 'success' | 'failed' | 'skipped'
  started_at?: string
  completed_at?: string
  duration?: number
  output?: any
  error?: string
  logs: LogEntry[]
}

export interface LogEntry {
  timestamp: string
  level: 'debug' | 'info' | 'warning' | 'error'
  message: string
}

export interface Plugin {
  name: string
  description: string
  version: string
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

export interface DashboardStats {
  total_workflows: number
  total_runs: number
  success_rate: number
  avg_duration: number
  runs_today: number
  active_runs: number
}
