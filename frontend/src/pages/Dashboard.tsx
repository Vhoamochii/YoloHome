import { useEffect, useState } from 'react'
import { useOutletContext } from 'react-router-dom'
import { deviceAPI, Device, sensorAPI, SensorCurrent, SensorPoint, User } from '../services/api'
import { loadThresholds } from '../components/ThresholdModal'

interface ShellContext {
  user: User | null
}

function formatTime(value: string | null) {
  if (!value) return '--:--'
  return new Date(value).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })
}

export default function Dashboard() {
  const { user } = useOutletContext<ShellContext>()
  const [sensors, setSensors] = useState<SensorCurrent>({ temperature: null, humidity: null, timestamp: null })
  const [history, setHistory] = useState<SensorPoint[]>([])
  const [devices, setDevices] = useState<Device[]>([])
  const [error, setError] = useState('')
  const thresholds = loadThresholds()

  const load = () => {
    sensorAPI.getCurrent().then((response) => setSensors(response.data)).catch(() => setError('Không đọc được cảm biến'))
    sensorAPI.getHistory(24).then((response) => setHistory(response.data.data.slice(-6).reverse())).catch(() => undefined)
    deviceAPI.getAll().then((response) => setDevices(response.data)).catch(() => undefined)
  }

  useEffect(() => {
    load()
    const timer = window.setInterval(load, 5000)
    return () => window.clearInterval(timer)
  }, [])

  const name = user?.name || 'bạn'
  const hot = sensors.temperature !== null && sensors.temperature >= thresholds.maxTemp
  const humid = sensors.humidity !== null && sensors.humidity >= thresholds.maxHumidity

  return (
    <div className="flex min-h-[70vh] flex-col justify-center gap-6 lg:flex-row lg:items-center">
      <div className="lg:w-[42%] lg:pl-6">
        <h1 className="text-4xl font-semibold text-white drop-shadow-[0_2px_10px_rgba(0,0,0,0.55)] lg:text-5xl">Hey, {name}!</h1>
        <p className="mt-3 text-lg text-white drop-shadow-[0_2px_8px_rgba(0,0,0,0.5)] lg:text-xl">Ready to control your smart home?</p>
        {(hot || humid) && (
          <p className="mt-4 max-w-xs rounded-2xl bg-yellow-300/90 px-4 py-2 text-sm font-medium text-black">
            {hot ? `Nhiệt độ đã chạm ngưỡng ${thresholds.maxTemp}°C. ` : ''}
            {humid ? `Độ ẩm đã chạm ngưỡng ${thresholds.maxHumidity}%.` : ''}
          </p>
        )}
      </div>

      <div className="glass w-full space-y-3 rounded-[28px] p-4 lg:ml-auto lg:w-[340px]">
        <section className="glass-card rounded-2xl p-4">
          <h2 className="font-semibold">Tổng quan</h2>
          <p className="mt-3 text-sm">Nhiệt độ: {sensors.temperature ?? '--'}°C</p>
          <p className="text-sm">Độ ẩm: {sensors.humidity ?? '--'}%</p>
          <p className="mt-2 text-xs text-white/70">{sensors.timestamp ? `Cập nhật ${formatTime(sensors.timestamp)}` : 'Chưa có dữ liệu cảm biến'}</p>
          {error && <p className="mt-2 text-xs text-yellow-200">{error}</p>}
        </section>

        <section className="glass-card rounded-2xl p-4">
          <h2 className="font-semibold">Thiết bị</h2>
          <ul className="mt-3 space-y-1 text-sm">
            {devices.length === 0 && <li>Chưa có thiết bị</li>}
            {devices.map((device) => (
              <li key={device.id}>• {device.name}: {device.status ? 'bật' : 'tắt'}{device.type === 'fan' ? ` ${device.speed}%` : ''}</li>
            ))}
          </ul>
        </section>

        <section className="glass-card rounded-2xl p-4">
          <h2 className="font-semibold">Nhật ký</h2>
          <ul className="mt-3 space-y-1 text-sm">
            {history.length === 0 && <li>Chưa có lịch sử</li>}
            {history.map((point) => (
              <li key={point.id}>{formatTime(point.recorded_at)} · {point.temperature ?? '--'}°C · {point.humidity ?? '--'}%</li>
            ))}
          </ul>
        </section>
      </div>
    </div>
  )
}
