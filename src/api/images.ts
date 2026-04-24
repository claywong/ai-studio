import { api } from './client'

export interface GenerateImagePayload {
  prompt: string
  aspect_ratio: string
  size_label: string
  model: string
  reference_images: File[]
  token_id: number
}

export interface GeneratedImage {
  b64_json: string
  mime_type: string
  revised_prompt?: string
}

export interface GenerateImageResult {
  user_id?: number
  model: string
  size: string
  images: GeneratedImage[]
}

export async function generateImage(payload: GenerateImagePayload) {
  if (payload.reference_images.length > 0) {
    const formData = new FormData()
    formData.append('prompt', payload.prompt)
    formData.append('aspect_ratio', payload.aspect_ratio)
    formData.append('size_label', payload.size_label)
    formData.append('model', payload.model)
    formData.append('token_id', String(payload.token_id))
    for (const image of payload.reference_images) {
      formData.append('reference_images', image)
    }

    const response = await api.post('/images/edits', formData)
    return response.data.data as GenerateImageResult
  }

  const response = await api.post('/images/generations', {
    prompt: payload.prompt,
    aspect_ratio: payload.aspect_ratio,
    size_label: payload.size_label,
    model: payload.model,
    reference_images: [],
    token_id: payload.token_id,
  })
  return response.data.data as GenerateImageResult
}
