export interface Scene {
  id: number
  action: string
  prompt: string
  role?: string
  shot_type?: string
  continuity_constraints?: string
}

export interface ScriptData {
  product_name: string
  master_description: string
  scenes: Scene[]
  tone?: 'UGC' | 'premium' | 'playful'
}

export interface Clip {
  id: string
  ad_id: string
  sequence_index: number
  role: string
  prompt: string
  wan_job_id?: string
  s3_url?: string
  local_path?: string
  duration: number
  status: 'pending' | 'generating' | 'completed' | 'failed'
}

export interface AdGeneration {
  id: string
  product_image_url: string
  script: ScriptData
  status: 'pending' | 'generating' | 'completed' | 'failed'
  clips: Clip[]
  final_video_url?: string
  created_at: string
  updated_at: string
}

