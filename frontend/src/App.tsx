import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Devices from './pages/Devices'
import Schedule from './pages/Schedule'
import ProtectedLayout from './components/ProtectedLayout'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route element={<ProtectedLayout />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/devices" element={<Devices />} />
          <Route path="/schedule" element={<Schedule />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
