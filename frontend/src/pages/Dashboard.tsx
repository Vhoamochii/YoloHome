import { useEffect, useMemo, useState } from 'react'
import { useOutletContext } from 'react-router-dom'
import { deviceAPI, Device, FireStatus, latestOnly, sensorAPI, SensorCurrent, SensorPoint, User } from '../services/api'
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
  const [fireStatus, setFireStatus] = useState<FireStatus>({ state: 'OK', score: null, is_alarm: false, updated_at: null })
  const [history, setHistory] = useState<SensorPoint[]>([])
  const [devices, setDevices] = useState<Device[]>([])
  const [error, setError] = useState('')
  const thresholds = loadThresholds()

  const load = useMemo(() => {
    const current = latestOnly(sensorAPI.getCurrent, (response) => {
      setSensors(response.data)
      setError('')
    })
    const fire = latestOnly(sensorAPI.getFireStatus, (response) => {
      setFireStatus(response.data)
    })
    const recent = latestOnly(() => sensorAPI.getHistory(24), (response) => setHistory(response.data.data.slice(-6).reverse()))
    const list = latestOnly(deviceAPI.getAll, (response) => setDevices(response.data))
    return () => {
      current().catch(() => setError('Không đọc được cảm biến'))
      fire().catch(() => undefined)
      recent().catch(() => undefined)
      list().catch(() => undefined)
    }
  }, [])

  useEffect(() => {
    load()
    const timer = window.setInterval(load, 5000)
    return () => window.clearInterval(timer)
  }, [load])

  const name = user?.name || 'bạn'
  const hot = sensors.temperature !== null && sensors.temperature >= thresholds.maxTemp
  const humid = sensors.humidity !== null && sensors.humidity >= thresholds.maxHumidity

  return (
    <div className="flex min-h-[70vh] flex-col justify-center gap-6 lg:flex-row lg:items-center">
      <div className="lg:w-[42%] lg:pl-6">
        <h1 className="text-4xl font-semibold text-white drop-shadow-[0_2px_10px_rgba(0,0,0,0.55)] lg:text-5xl">Hey, {name}!</h1>
        <p className="mt-3 text-lg text-white drop-shadow-[0_2px_8px_rgba(0,0,0,0.5)] lg:text-xl">Ready to control your smart home?</p>
        {fireStatus.is_alarm && (
          <div className="mt-4 max-w-xs rounded-2xl bg-red-600/95 px-4 py-3 text-sm font-semibold text-white shadow-lg animate-pulse border border-red-300">
            🚨 CẢNH BÁO NGUY CƠ CHÁY (TinyML)!
            <div className="mt-1 text-xs font-normal opacity-90">
              Điểm rủi ro: {fireStatus.score !== null ? (fireStatus.score * 100).toFixed(1) + '%' : '--'} (Score: {fireStatus.score !== null ? fireStatus.score.toFixed(2) : '--'})
            </div>
          </div>
        )}
        {(hot || humid) && !fireStatus.is_alarm && (
          <p className="mt-4 max-w-xs rounded-2xl bg-yellow-300/90 px-4 py-2 text-sm font-medium text-black">
            {hot ? `Nhiệt độ đã chạm ngưỡng ${thresholds.maxTemp}°C. ` : ''}
            {humid ? `Độ ẩm đã chạm ngưỡng ${thresholds.maxHumidity}%.` : ''}
          </p>
        )}
      </div>

      <div className="glass w-full space-y-3 rounded-[28px] p-4 lg:ml-auto lg:w-[340px]">
        <section className="glass-card rounded-2xl p-4">
          <h2 className="font-semibold">Tổng quan môi trường</h2>
          <p className="mt-3 text-sm">Nhiệt độ: {sensors.temperature != null ? `${sensors.temperature}°C` : '--'}</p>
          <p className="text-sm">Độ ẩm: {sensors.humidity != null ? `${sensors.humidity}%` : '--'}</p>
          <div className="mt-3 flex items-center justify-between border-t border-white/10 pt-2 text-xs">
            <span className="text-white/70">Giám sát cháy TinyML:</span>
            <span className={`font-semibold ${fireStatus.is_alarm ? 'text-red-400 font-bold animate-pulse' : 'text-emerald-400'}`}>
              {fireStatus.is_alarm ? `CẢNH BÁO (${fireStatus.score !== null ? fireStatus.score.toFixed(2) : 'ALERT'})` : `An toàn (${fireStatus.score !== null ? fireStatus.score.toFixed(2) : 'OK'})`}
            </span>
          </div>
          <p className="mt-2 text-xs text-white/70">{sensors.timestamp ? `Cập nhật ${formatTime(sensors.timestamp)}` : 'Chưa có dữ liệu cảm biến'}</p>
          {error && <p className="mt-2 text-xs text-yellow-200">{error}</p>}
        </section>

        <section className="glass-card rounded-2xl p-4">
          <h2 className="font-semibold">Thiết bị</h2>
          <ul className="mt-3 space-y-1 text-sm">
            {devices.length === 0 && <li>Chưa có thiết bị</li>}
            {devices.map((device) => (
              <li key={device.id}>
                • {device.name}:{' '}
                {device.type === 'led'
                  ? device.alert_level === 'SAFETY'
                    ? '🔴 QUÁ NHIỆT (> 45°C)'
                    : device.alert_level === 'HOT'
                    ? '🟠 Cảnh báo nóng (≥ 33°C)'
                    : device.alert_level === 'TEST'
                    ? '🔴 Đang test đèn đỏ'
                    : '🟢 Bình thường'
                  : `${device.status ? 'bật' : 'tắt'}${device.type === 'fan' ? ` ${device.speed}%` : ''}`}
              </li>
            ))}
          </ul>
        </section>

        <section className="glass-card rounded-2xl p-4">
          <h2 className="font-semibold">Nhật ký cảm biến gần đây</h2>
          <ul className="mt-3 space-y-1 text-sm">
            {history.length === 0 && <li className="text-xs text-white/60">Chưa có dữ liệu lịch sử từ ESP32</li>}
            {history.map((point) => (
              <li key={point.id}>{formatTime(point.recorded_at)} · {point.temperature ?? '--'}°C · {point.humidity ?? '--'}%</li>
            ))}
          </ul>
        </section>
      </div>
    </div>
  )
}
