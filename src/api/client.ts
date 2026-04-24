import axios from 'axios'

export const api = axios.create({
  baseURL: '/app/ai-api',
  timeout: 130000,
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('auth_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})
