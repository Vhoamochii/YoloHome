import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json'
  }
})

// Add JWT token to requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

export const authAPI = {
  login: (email: string, password: string) => 
    api.post('/auth/login', { email, password }),
  
  faceLogin: (imageData: string) => 
    api.post('/auth/face-login', { image: imageData }),
  
  registerFace: (imageData: string) => 
    api.post('/auth/register-face', { image: imageData })
}

export const deviceAPI = {
  getAll: () => api.get('/devices/'),
  
  control: (deviceId: number, action: string, params?: any) => 
    api.post(`/devices/${deviceId}/control`, { action, ...params })
}

export const sensorAPI = {
  getCurrent: () => api.get('/sensors/current'),
  
  getHistory: (hours: number = 24) => 
    api.get(`/sensors/history?hours=${hours}`)
}

export default api
