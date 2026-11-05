import { useEffect, useState } from 'react'
import { deviceAPI, Device, errorMessage } from '../services/api'

const COLORS = [
  { name: 'xanh lá', value: '00FF00', swatch: '#22c55e' },
  { name: 'đỏ', value: 'FF0000', swatch: '#ef4444' },
  { name: 'xanh dương', value: '0000FF', swatch: '#3b82f6' },
  { name: 'vàng', value: 'FFFF00', swatch: '#facc15' }
]

function colorName(value: string | null) {
  return COLORS.find((color) => color.value.toLowerCase() === (value || '').toLowerCase())?.name || value || 'chưa đặt'
}

export default function Devices() {
  const [devices, setDevices] = useState<Device[]>([])
  const [speeds, setSpeeds] = useState<Record<number, number>>({})
  const [notice, setNotice] = useState('')
  const [error, setError] = useState('')

  const load = () => {
    deviceAPI.getAll()
      .then((response) => {
        setDevices(response.data)
        const next: Record<number, number> = {}
        response.data.forEach((device) => {
          next[device.id] = device.speed
        })
        setSpeeds(next)
      })
      .catch(() => setError('Không tải được danh sách thiết bị'))
  }

  useEffect(() => {
    load()
  }, [])

  const send = async (device: Device, action: string, params?: { speed?: number; color?: string }) => {
    setError('')
    try {
      const response = await deviceAPI.control(device.id, action, params)
      setNotice(response.data.mqtt_sent ? '' : response.data.message)
      load()
    } catch (err) {
      setError(errorMessage(err, 'Không điều khiển được thiết bị'))
    }
  }

  return (
    <div className="flex min-h-[640px] items-center justify-center">
      <section className="glass w-full max-w-3xl rounded-[28px] p-5">
        <h1 className="mb-4 text-2xl font-semibold">Thiết bị</h1>
        {notice && <p className="mb-3 text-sm text-yellow-100">{notice}</p>}
        {error && <p className="mb-3 text-sm text-red-200">{error}</p>}

        <div className="grid gap-3 md:grid-cols-2">
          {devices.map((device) => (
            <article key={device.id} className="glass-card rounded-2xl p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h2 className="text-lg font-semibold">{device.name}</h2>
                  <p className="text-sm">Trạng thái: {device.status ? 'bật' : 'tắt'}</p>
                  {device.type === 'fan' && <p className="text-sm">Tốc độ: {device.speed}%</p>}
                  {device.type === 'led' && <p className="text-sm">Màu sắc: {colorName(device.color)}</p>}
                </div>
                <button
                  onClick={() => send(device, device.status ? 'off' : 'on')}
                  className={`relative h-7 w-12 rounded-full ${device.status ? 'bg-yellow-400' : 'bg-white/40'}`}
                  aria-label={device.status ? 'Tắt' : 'Bật'}
                >
                  <span className={`absolute top-0.5 h-6 w-6 rounded-full bg-white transition ${device.status ? 'left-5' : 'left-0.5'}`} />
                </button>
              </div>

              {device.type === 'fan' && (
                <label className="mt-4 block text-xs">
                  <input
                    type="range"
                    min={0}
                    max={100}
                    value={speeds[device.id] ?? device.speed}
                    onChange={(event) => setSpeeds({ ...speeds, [device.id]: Number(event.target.value) })}
                    onMouseUp={() => send(device, 'set_speed', { speed: speeds[device.id] ?? device.speed })}
                    onTouchEnd={() => send(device, 'set_speed', { speed: speeds[device.id] ?? device.speed })}
                    className="w-full accent-yellow-400"
                  />
                  <span className="mt-1 flex justify-between text-white/80">
                    <span>0</span>
                    <span>{speeds[device.id] ?? device.speed}</span>
                    <span>100</span>
                  </span>
                </label>
              )}

              {device.type === 'led' && (
                <div className="mt-4 flex gap-2">
                  {COLORS.map((color) => (
                    <button
                      key={color.value}
                      onClick={() => send(device, 'set_color', { color: color.value })}
                      title={color.name}
                      className={`h-8 w-8 rounded-md ${device.color?.toLowerCase() === color.value.toLowerCase() ? 'ring-2 ring-white' : ''}`}
                      style={{ background: color.swatch }}
                    />
                  ))}
                </div>
              )}
            </article>
          ))}
        </div>
      </section>
    </div>
  )
}
