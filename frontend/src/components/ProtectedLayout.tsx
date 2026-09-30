import { Outlet, Navigate } from 'react-router-dom'
import VoiceControl from './VoiceControl'

export default function ProtectedLayout() {
  const token = localStorage.getItem('token')
  
  if (!token) {
    return <Navigate to="/login" />
  }

  return (
    <div className="min-h-screen bg-gray-100">
      <nav className="bg-white shadow">
        <div className="container mx-auto px-4 py-4">
          <div className="flex gap-4">
            <a href="/" className="text-blue-600">Dashboard</a>
            <a href="/devices" className="text-blue-600">Devices</a>
            <a href="/schedule" className="text-blue-600">Schedule</a>
          </div>
        </div>
      </nav>
      
      <main>
        <Outlet />
      </main>
      
      <VoiceControl />
    </div>
  )
}
