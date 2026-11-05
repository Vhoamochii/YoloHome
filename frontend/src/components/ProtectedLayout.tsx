import { useEffect, useState } from 'react'
import { NavLink, Navigate, Outlet, useNavigate } from 'react-router-dom'
import { authAPI, deviceAPI, Device, readUser, User } from '../services/api'
import HomeScene from './HomeScene'
import ThresholdModal from './ThresholdModal'
import VoiceModal from './VoiceModal'

const links = [
  { to: '/', label: 'Tổng quan', icon: 'home' },
  { to: '/devices', label: 'Thiết bị', icon: 'light' },
  { to: '/schedule', label: 'Lịch', icon: 'calendar' },
  { to: '/logs', label: 'Nhật ký', icon: 'chart' }
]

function Icon({ name }: { name: string }) {
  const common = 'h-5 w-5'
  if (name === 'home') {
    return (
      <svg viewBox="0 0 24 24" className={common} fill="none" stroke="currentColor" strokeWidth="1.8">
        <path d="M4 10.5 12 4l8 6.5V20a1 1 0 0 1-1 1h-5v-6H10v6H5a1 1 0 0 1-1-1z" />
      </svg>
    )
  }
  if (name === 'light') {
    return (
      <svg viewBox="0 0 24 24" className={common} fill="none" stroke="currentColor" strokeWidth="1.8">
        <path d="M9 18h6M10 21h4M12 3a6 6 0 0 0-3 11c.4.4.7 1 .8 1.6h4.4c.1-.6.4-1.2.8-1.6A6 6 0 0 0 12 3z" />
      </svg>
    )
  }
  if (name === 'calendar') {
    return (
      <svg viewBox="0 0 24 24" className={common} fill="none" stroke="currentColor" strokeWidth="1.8">
        <rect x="4" y="5" width="16" height="15" rx="2" />
        <path d="M8 3v4M16 3v4M4 10h16" />
      </svg>
    )
  }
  return (
    <svg viewBox="0 0 24 24" className={common} fill="none" stroke="currentColor" strokeWidth="1.8">
      <path d="M4 19V5M4 19h16M7 15l4-5 3 3 4-6" />
    </svg>
  )
}

export default function ProtectedLayout() {
  const navigate = useNavigate()
  const token = localStorage.getItem('token')
  const [user, setUser] = useState<User | null>(readUser)
  const [devices, setDevices] = useState<Device[]>([])
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [voiceOpen, setVoiceOpen] = useState(false)
  const [alertsOpen, setAlertsOpen] = useState(false)

  useEffect(() => {
    if (!token) return
    authAPI.me().then((response) => {
      setUser(response.data)
      localStorage.setItem('user', JSON.stringify(response.data))
    }).catch(() => undefined)
    deviceAPI.getAll().then((response) => setDevices(response.data)).catch(() => undefined)
  }, [token])

  if (!token) {
    return <Navigate to="/login" />
  }

  const logout = () => {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    navigate('/login')
  }

  return (
    <div className="relative min-h-screen overflow-hidden text-white">
      <HomeScene className="fixed inset-0 z-0" />
      <div className="relative z-10 mx-auto flex min-h-screen max-w-6xl flex-col gap-4 px-3 py-4 lg:flex-row lg:items-center lg:gap-6 lg:px-4 lg:py-8">
        <nav className="nav-pill flex flex-row items-center justify-center gap-2 self-center rounded-full px-3 py-2 lg:flex-col lg:px-2 lg:py-3">
          {links.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              end={link.to === '/'}
              title={link.label}
              className={({ isActive }) =>
                `flex h-11 w-11 items-center justify-center rounded-full ${isActive ? 'bg-white text-black' : 'text-white hover:bg-white/10'}`
              }
            >
              <Icon name={link.icon} />
            </NavLink>
          ))}
          <button
            title="Giọng nói"
            onClick={() => setVoiceOpen(true)}
            className="flex h-11 w-11 items-center justify-center rounded-full text-white hover:bg-white/10"
          >
            <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.8">
              <path d="M12 3v3M8 8a4 4 0 1 0 8 0M12 16v5M8 21h8M5 12a7 7 0 0 0 14 0" />
            </svg>
          </button>
        </nav>

        <div className="relative min-h-[640px] flex-1">
          <div className="absolute right-0 top-0 z-10 flex gap-2">
            <button
              onClick={() => setSettingsOpen(true)}
              className="nav-pill flex h-11 w-11 items-center justify-center rounded-full"
              title="Cài đặt"
            >
              <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.8">
                <circle cx="12" cy="12" r="3" />
                <path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6l1.4 1.4M17 17l1.4 1.4M18.4 5.6 17 7M7 17l-1.4 1.4" />
              </svg>
            </button>
            <button
              onClick={() => setAlertsOpen((open) => !open)}
              className="nav-pill flex h-11 w-11 items-center justify-center rounded-full"
              title="Thông báo"
            >
              <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.8">
                <path d="M6 16V11a6 6 0 1 1 12 0v5l1.5 2h-15zM10 19a2 2 0 0 0 4 0" />
              </svg>
            </button>
          </div>

          {alertsOpen && (
            <div className="glass absolute right-0 top-14 z-10 w-64 rounded-2xl p-4 text-sm">
              <p className="font-semibold">{user?.name || user?.email}</p>
              <p className="mt-1 text-white/70">Phiên đăng nhập đang hoạt động.</p>
              <button onClick={logout} className="mt-3 text-yellow-200">
                Đăng xuất
              </button>
            </div>
          )}

          <Outlet context={{ user, refreshDevices: () => deviceAPI.getAll().then((response) => setDevices(response.data)) }} />
        </div>
      </div>

      {settingsOpen && <ThresholdModal onClose={() => setSettingsOpen(false)} />}
      {voiceOpen && (
        <VoiceModal
          devices={devices}
          onDone={() => deviceAPI.getAll().then((response) => setDevices(response.data)).catch(() => undefined)}
          onClose={() => setVoiceOpen(false)}
        />
      )}
    </div>
  )
}
