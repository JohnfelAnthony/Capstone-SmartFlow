import { apiRequest } from "@/api/client"

export type RLModelRecord = {
  id: number
  algorithm: string
  name: string | null
  checkpoint_path: string | null
  training_date: string | null
  best_evaluation_score: number | null
}

export type RLTrainingJob = {
  id: number
  user_id: number | null
  status: string
  selected_algorithms: string[]
  settings: Record<string, unknown>
  progress_percent: number
  current_algorithm: string | null
  current_item_id: number | null
  log_path: string | null
  message: string | null
  started_at: string | null
  ended_at: string | null
  created_at: string | null
}

export type RLTrainingJobItem = {
  id: number
  job_id: number
  algorithm: string
  sequence_index: number
  status: string
  progress_percent: number
  latest_episode: number
  latest_reward: number | null
  latest_epsilon: number | null
  latest_timesteps: number
  artifact_path: string | null
  metadata_path: string | null
  rl_model_id: number | null
  evaluation_path: string | null
  message: string | null
  started_at: string | null
  ended_at: string | null
  created_at: string | null
}

export type RLLogLine = {
  ts: string | null
  type: string | null
  algorithm: string | null
  text: string
}

export type RLTrainingStatusResponse = {
  job: RLTrainingJob | null
  items: RLTrainingJobItem[]
  log_lines: RLLogLine[]
  models: RLModelRecord[]
}

export type RLTrainingSettings = {
  episodes: number
  seeds: string
  warmup_seconds: number
  evaluation_seconds: number
  intersection_id: string
  traffic_density: string
  pedestrian_density: string
  emergency_mode: string
  road_constraint: string
  checkpoint_every: number
  resume_model?: string | null
}

export type RLAdvancedSettings = {
  ql: {
    alpha: number
    gamma: number
    epsilon: number
  }
  dql: {
    learning_starts: number
    buffer_size: number
    batch_size: number
  }
  ppo: {
    n_steps: number
    batch_size: number
    n_epochs: number
  }
}

export function listRLModels(options: { algorithm?: string; limit?: number } = {}) {
  const params = new URLSearchParams()
  if (options.algorithm) params.set("algorithm", options.algorithm)
  if (options.limit) params.set("limit", String(options.limit))
  const query = params.toString()
  return apiRequest<{ models: RLModelRecord[] }>(`/api/rl/models${query ? `?${query}` : ""}`)
}

export function listRLTrainingJobs(options: { limit?: number } = {}) {
  const params = new URLSearchParams()
  if (options.limit) params.set("limit", String(options.limit))
  const query = params.toString()
  return apiRequest<{ jobs: RLTrainingJob[] }>(`/api/rl/jobs${query ? `?${query}` : ""}`)
}

export function getRLTrainingStatus(jobId?: number | null) {
  const query = jobId ? `?job_id=${jobId}` : ""
  return apiRequest<RLTrainingStatusResponse>(`/api/rl/status${query}`)
}

export function startRLTrainingJob(payload: {
  algorithms: string[]
  settings: RLTrainingSettings
  advanced: RLAdvancedSettings
}) {
  return apiRequest<{ message: string; job_id: number | null }>("/api/rl/jobs", {
    method: "POST",
    body: payload,
  })
}

export function stopRLTrainingJob(jobId: number) {
  return apiRequest<{ message: string; job_id: number | null }>(`/api/rl/jobs/${jobId}/stop`, {
    method: "POST",
  })
}

export function evaluateRLModel(payload: { model_id: number; settings: RLTrainingSettings }) {
  return apiRequest<{ message: string; job_id: number | null }>("/api/rl/evaluate", {
    method: "POST",
    body: payload,
  })
}
