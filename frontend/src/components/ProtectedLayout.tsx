import { useEffect, useState } from 'react'
import { NavLink, Navigate, Outlet, useNavigate } from 'react-router-dom'
import { authAPI, deviceAPI, Device, readUser, User, errorMessage } from '../services/api'
import FaceCapture from './FaceCapture'
import HomeScene from './HomeScene'
import ThresholdModal from './ThresholdModal'
import VoiceModal from './VoiceModal'

const links = [
  { to: '/', label: 'Tổng quan', icon: 'home' },
  { to: '/devices', label: 'Thiết bị', icon: 'light' },
  { to: '/schedule', label: 'Lịch', icon: 'calendar' },
  { to: '/logs', label: 'Nhật ký & CSV', icon: 'chart' }
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
  const [faceModalOpen, setFaceModalOpen] = useState(false)
  const [toast, setToast] = useState('')

  useEffect(() => {
    if (!token) return
    authAPI
      .me()
      .then((response) => {
        setUser(response.data)
        localStorage.setItem('user', JSON.stringify(response.data))
      })
      .catch(() => undefined)
    deviceAPI
      .getAll()
      .then((response) => setDevices(response.data))
      .catch(() => undefined)
  }, [token])

  if (!token) {
    return <Navigate to="/login" />
  }

  const logout = () => {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    navigate('/login')
  }

  const showToast = (msg: string) => {
    setToast(msg)
    setTimeout(() => setToast(''), 4000)
  }

  return (
    <div className="relative min-h-screen overflow-hidden text-white">
      <HomeScene className="fixed inset-0 z-0" />
      
      {/* Toast Alert */}
      {toast && (
        <div className="fixed top-5 left-1/2 z-50 -translate-x-1/2 rounded-full bg-emerald-500/90 px-5 py-2.5 text-sm font-medium text-white shadow-xl backdrop-blur-md">
          {toast}
        </div>
      )}

      <div className="relative z-10 mx-auto flex min-h-screen max-w-6xl flex-col gap-4 px-3 py-4 lg:flex-row lg:items-center lg:gap-6 lg:px-4 lg:py-8">
        <nav className="nav-pill flex flex-row items-center justify-center gap-2 self-center rounded-full px-3 py-2 lg:flex-col lg:px-2 lg:py-3">
          {links.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              end={link.to === '/'}
              title={link.label}
              className={({ isActive }) =>
                `flex h-11 w-11 items-center justify-center rounded-full transition ${
                  isActive ? 'bg-white text-black' : 'text-white hover:bg-white/10'
                }`
              }
            >
              <Icon name={link.icon} />
            </NavLink>
          ))}
          <button
            title="Giọng nói (Voice)"
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
            {/* Face Registration Button */}
            <button
              onClick={() => setFaceModalOpen(true)}
              className="nav-pill flex h-11 items-center justify-center rounded-full px-3.5 text-xs font-semibold transition hover:scale-105 active:scale-95"
              title="Đăng ký hoặc cập nhật khuôn mặt Face ID"
            >
              <span className={user?.has_face ? 'text-emerald-300' : 'text-yellow-300'}>
                {user?.has_face ? 'Face ID ✓' : '+ Face ID'}
              </span>
            </button>

            <button
              onClick={() => setSettingsOpen(true)}
              className="nav-pill flex h-11 w-11 items-center justify-center rounded-full transition hover:scale-105 active:scale-95"
              title="Cài đặt ngưỡng"
            >
              <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.8">
                <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z" />
                <circle cx="12" cy="12" r="3" />
              </svg>
            </button>
            <button
              onClick={() => setAlertsOpen((open) => !open)}
              className="nav-pill flex h-11 w-11 items-center justify-center rounded-full transition hover:scale-105 active:scale-95"
              title="Tài khoản"
            >
              <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.8">
                <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                <circle cx="12" cy="7" r="4" />
              </svg>
            </button>
          </div>

          {alertsOpen && (
            <div className="glass absolute right-0 top-14 z-20 w-64 rounded-2xl p-4 text-sm">
              <p className="font-semibold">{user?.name || user?.email}</p>
              <p className="text-xs text-white/70">{user?.email}</p>
              <p className="mt-2 text-xs text-emerald-300">
                {user?.has_face ? '✓ Đã kích hoạt nhận diện khuôn mặt' : 'Chưa đăng ký Face ID'}
              </p>
              <div className="mt-3 flex gap-2 border-t border-white/10 pt-2">
                <button
                  onClick={() => {
                    setAlertsOpen(false)
                    setFaceModalOpen(true)
                  }}
                  className="text-xs text-yellow-300 underline"
                >
                  Đăng ký Face ID
                </button>
                <button onClick={logout} className="ml-auto text-xs text-red-300 hover:text-red-200">
                  Đăng xuất
                </button>
              </div>
            </div>
          )}

          <Outlet
            context={{
              user,
              refreshDevices: () => deviceAPI.getAll().then((response) => setDevices(response.data))
            }}
          />
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

      {/* Face Registration Modal */}
      {faceModalOpen && (
        <FaceCapture
          title="Đăng ký nhận diện khuôn mặt (Face ID)"
          submitLabel="Lưu khuôn mặt vào hệ thống"
          onClose={() => setFaceModalOpen(false)}
          onSubmit={async (image) => {
            try {
              const res = await authAPI.registerFace(image)
              showToast(res.data.message || 'Đăng ký khuôn mặt thành công!')
              setFaceModalOpen(false)
              // Update user state
              authAPI.me().then((r) => {
                setUser(r.data)
                localStorage.setItem('user', JSON.stringify(r.data))
              })
            } catch (err) {
              throw new Error(errorMessage(err, 'Lỗi khi lưu khuôn mặt.'))
            }
          }}
        />
      )}
    </div>
  )
}
