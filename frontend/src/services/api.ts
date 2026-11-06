import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json'
  }
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const url = error.config?.url || ''
    const isAuthAttempt =
      url.includes('/auth/login') ||
      url.includes('/auth/face-login') ||
      url.includes('/auth/register') ||
      url.includes('/auth/register-face')
    if (error.response?.status === 401 && !isAuthAttempt) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      if (!window.location.pathname.startsWith('/login')) {
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

export interface User {
  id: number
  email: string
  name: string | null
  has_face?: boolean
}

export interface AuthResponse {
  token: string
  user: User
  distance?: number
}

export interface Device {
  id: number
  name: string
  type: string | null
  location: string | null
  feed: string | null
  status: boolean
  speed: number
  color: string | null
  is_alert?: boolean
  alert_level?: 'SAFETY' | 'HOT' | 'TEST' | null
  mode?: string
  updated_at: string | null
}

export interface DeviceControlResult {
  success: boolean
  device_id: number
  action: string
  feed: string
  value: string
  cmd_id: string | null
  mqtt_sent: boolean
  message: string
}

export interface SensorCurrent {
  temperature: number | null
  humidity: number | null
  timestamp: string | null
}

export interface FireStatus {
  state: string
  score: number | null
  is_alarm: boolean
  updated_at: string | null
}

export interface SensorPoint {
  id: number
  temperature: number | null
  humidity: number | null
  recorded_at: string | null
}

export interface SensorHistory {
  data: SensorPoint[]
  from: string
  to: string
}

export interface Schedule {
  id: number
  device_id: number
  device_name: string | null
  action: string
  scheduled_time: string | null
  repeat_mode: string
  is_active: boolean
  speed: number | null
  created_at: string | null
}

export interface ActivityEntry {
  id: number
  cmd_id: string | null
  device: string | null
  action: string | null
  actor: string | null
  status: string | null
  reason: string | null
  rtt_ms: number | null
  created_at: string | null
}

export interface ScheduleInput {
  device_id: number
  action: string
  scheduled_time: string
  repeat_mode: string
  is_active?: boolean
  speed?: number | null
}

export const authAPI = {
  login: (email: string, password: string) =>
    api.post<AuthResponse>('/auth/login', { email, password }),

  register: (email: string, password: string, name: string) =>
    api.post<AuthResponse>('/auth/register', { email, password, name }),

  me: () => api.get<User>('/auth/me'),

  faceLogin: (imageData: string) =>
    api.post<AuthResponse>('/auth/face-login', { image: imageData }),

  registerFace: (imageData: string, email?: string) =>
    api.post<{ success: boolean; message: string; user_id: number }>('/auth/register-face', {
      image: imageData,
      email
    })
}

export const deviceAPI = {
  getAll: () => api.get<Device[]>('/devices/'),

  control: (deviceId: number, action: string, params?: { speed?: number; actor?: 'USER' | 'VOICE' }) =>
    api.post<DeviceControlResult>(`/devices/${deviceId}/control`, { action, ...params })
}

export const sensorAPI = {
  getCurrent: () => api.get<SensorCurrent>('/sensors/current'),

  getHistory: (hours: number = 24) =>
    api.get<SensorHistory>(`/sensors/history?hours=${hours}`),

  getExportCSVUrl: (hours: number = 168) => `/api/sensors/export-csv?hours=${hours}`,
  getFireStatus: () => api.get<FireStatus>('/sensors/fire-status')
}

export const scheduleAPI = {
  list: () => api.get<Schedule[]>('/schedules/'),

  create: (body: ScheduleInput) => api.post<Schedule>('/schedules/', body),

  update: (id: number, body: Partial<ScheduleInput> & { is_active?: boolean }) =>
    api.patch<Schedule>(`/schedules/${id}`, body),

  remove: (id: number) => api.delete(`/schedules/${id}`)
}

export const activityAPI = {
  list: (limit: number = 100) => api.get<ActivityEntry[]>(`/activity/?limit=${limit}`)
}

export const activityStatusLabel: Record<string, string> = {
  PENDING: 'Đang chờ mạch',
  OK: 'Mạch đã thực hiện',
  REJECTED: 'Mạch từ chối',
  TIMEOUT: 'Không có phản hồi',
  OFFLINE: 'Chưa gửi (ngoại tuyến)',
  EVENT: 'Sự kiện'
}

/**
 * Wraps a polling fetch so a slow, older response can never overwrite a newer one.
 * Responses arriving out of order are dropped.
 */
export function latestOnly<T>(fetcher: () => Promise<T>, apply: (value: T) => void) {
  let lastStarted = 0
  let lastApplied = 0
  return () => {
    const id = ++lastStarted
    return fetcher().then((value) => {
      if (id > lastApplied) {
        lastApplied = id
        apply(value)
      }
    })
  }
}

export function saveSession(auth: AuthResponse) {
  localStorage.setItem('token', auth.token)
  localStorage.setItem('user', JSON.stringify(auth.user))
}

export function errorMessage(error: unknown, fallback: string) {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail
    if (typeof detail === 'string') return detail
  }
  return fallback
}

export function readUser(): User | null {
  const raw = localStorage.getItem('user')
  if (!raw) return null
  try {
    return JSON.parse(raw) as User
  } catch {
    return null
  }
}

export default api
