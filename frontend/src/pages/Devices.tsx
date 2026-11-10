import { useEffect, useMemo, useRef, useState } from 'react'
import { activityAPI, ActivityEntry, activityStatusLabel, deviceAPI, Device, errorMessage, latestOnly } from '../services/api'

// After a command the board needs a moment to report; keep showing what the user chose until then.
const SPEED_HOLD_MS = 1500

function formatTime(value: string | null) {
  return value ? new Date(value).toLocaleTimeString('vi-VN') : '--'
}

export default function Devices() {
  const [devices, setDevices] = useState<Device[]>([])
  const [speeds, setSpeeds] = useState<Record<number, number>>({})
  const [notice, setNotice] = useState('')
  const [error, setError] = useState('')
  const [activityLogs, setActivityLogs] = useState<ActivityEntry[]>([])
  const dragging = useRef(false)
  const holdUntil = useRef(0)

  const load = useMemo(() => {
    const list = latestOnly(deviceAPI.getAll, (response) => {
      setDevices(response.data)
      // A poll must not move the slider while it is dragged or just after a command.
      if (dragging.current || Date.now() < holdUntil.current) return
      const next: Record<number, number> = {}
      response.data.forEach((device) => {
        next[device.id] = device.speed
      })
      setSpeeds(next)
    })
    const activity = latestOnly(() => activityAPI.list(10), (response) => setActivityLogs(response.data))
    return () => {
      list().catch(() => setError('Không tải được danh sách thiết bị'))
      activity().catch(() => undefined)
    }
  }, [])

  useEffect(() => {
    load()
    const timer = setInterval(load, 2000)
    return () => clearInterval(timer)
  }, [load])

  const inFlight = useRef<Record<number, boolean>>({})
  const queuedCommand = useRef<Record<number, { action: string; params?: { speed?: number } } | null>>({})

  const send = async (device: Device, action: string, params?: { speed?: number }) => {
    setError('')
    holdUntil.current = Date.now() + SPEED_HOLD_MS

    // Optimistic UI state update so buttons and badges react in 0 ms
    setDevices((prev) =>
      prev.map((d) => {
        if (d.id !== device.id) return d
        if (d.type === 'fan') {
          const isOff = action === 'off' || (action === 'set_speed' && params?.speed === 0)
          const newSpeed = params?.speed !== undefined ? params.speed : isOff ? 0 : d.speed || 70
          return {
            ...d,
            status: !isOff,
            speed: newSpeed,
            mode: action === 'auto' ? 'AUTO_AI' : d.mode
          }
        }
        if (d.type === 'led') {
          const isAlert = action === 'alert' || action === 'on'
          return {
            ...d,
            status: isAlert,
            is_alert: isAlert,
            alert_level: isAlert ? 'TEST' : null,
            color: isAlert ? 'FF0000' : '00FF00'
          }
        }
        return d
      })
    )

    // If a command for this device is already in-flight (rapid clicking),
    // queue the latest desired action so Adafruit IO is not flooded with outdated commands.
    if (inFlight.current[device.id]) {
      queuedCommand.current[device.id] = { action, params }
      return
    }

    inFlight.current[device.id] = true
    try {
      const response = await deviceAPI.control(device.id, action, params)
      setNotice(response.data.message)
      if (!response.data.mqtt_sent) holdUntil.current = 0
    } catch (err) {
      holdUntil.current = 0
      setError(errorMessage(err, 'Không điều khiển được thiết bị'))
    } finally {
      inFlight.current[device.id] = false
      const next = queuedCommand.current[device.id]
      if (next) {
        queuedCommand.current[device.id] = null
        send(device, next.action, next.params)
      } else {
        load()
      }
    }
  }

  const exportActivityCSV = () => {
    const headers = ['ID', 'Thiết bị', 'Hành động điều khiển', 'Thời gian', 'Trạng thái']
    const csvRows = activityLogs.map((l) => [l.id, `"${l.device}"`, `"${l.action}"`, `"${formatTime(l.created_at)}"`, `"${l.status}"`])
    const csvContent = '\ufeff' + [headers.join(','), ...csvRows.map((r) => r.join(','))].join('\n')
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', `yolohome_device_actions_${new Date().toISOString().slice(0, 10)}.csv`)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }

  return (
    <div className="flex min-h-[640px] items-center justify-center py-6">
      <section className="glass w-full max-w-3xl rounded-[28px] p-6 shadow-2xl">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
          <div>
            <h1 className="text-2xl font-bold">Điều khiển thiết bị</h1>
            <p className="text-xs text-white/70">Quạt làm mát tự động & Đèn LED cảnh báo quá ngưỡng an toàn</p>
          </div>
          <button
            onClick={exportActivityCSV}
            className="flex items-center gap-1 rounded-full bg-yellow-400 px-3.5 py-1.5 text-xs font-semibold text-black transition hover:bg-yellow-300"
            title="Xuất file CSV ghi nhận lịch sử điều khiển"
          >
            <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3" />
            </svg>
            <span>Xuất log CSV</span>
          </button>
        </div>

        {notice && <p className="mb-3 text-xs text-yellow-200 bg-yellow-950/40 px-3 py-2 rounded-xl">{notice}</p>}
        {error && <p className="mb-3 text-xs text-red-200 bg-red-950/40 px-3 py-2 rounded-xl">{error}</p>}

        <div className="grid gap-4 md:grid-cols-2">
          {devices.map((device) => {
            const isLed = device.type === 'led'
            const level = device.alert_level
            const isAlertActive = isLed && Boolean(level)

            return (
              <article key={device.id} className="glass-card rounded-2xl p-4 transition hover:bg-white/15">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h2 className="text-base font-semibold">{device.name}</h2>
                    {isLed ? (
                      <p className="text-xs text-white/80">
                        Chức năng: <span className="text-yellow-300 font-medium">Cam khi ≥ 33°C, đỏ khi &gt; 45°C</span>
                      </p>
                    ) : (
                      <>
                        <div className="flex flex-wrap items-center gap-1.5 pt-0.5">
                          <span className={device.status ? 'text-xs text-emerald-300 font-medium' : 'text-xs text-white/60'}>
                            {device.status ? '● Đang chạy' : '○ Đang tắt'}
                          </span>
                          {device.mode && device.mode.includes('MANUAL') ? (
                            <span className="rounded-full bg-amber-500/20 border border-amber-400/30 px-2 py-0.5 text-[10px] font-semibold text-amber-200">
                              Thủ công
                            </span>
                          ) : (
                            <span className="rounded-full bg-emerald-500/20 border border-emerald-400/30 px-2 py-0.5 text-[10px] font-semibold text-emerald-200">
                              Tự động (AI)
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-white/80 mt-1">
                          Tốc độ hiện tại: <span className="font-mono font-bold text-yellow-300">{device.speed}%</span>
                        </p>
                      </>
                    )}
                  </div>

                  {!isLed ? (
                    <button
                      onClick={() => send(device, device.status ? 'off' : 'on')}
                      className={`relative h-7 w-12 rounded-full transition ${device.status ? 'bg-yellow-400' : 'bg-white/30'}`}
                      aria-label={device.status ? 'Tắt' : 'Bật'}
                    >
                      <span className={`absolute top-0.5 h-6 w-6 rounded-full bg-white shadow-md transition-all ${device.status ? 'left-5' : 'left-0.5'}`} />
                    </button>
                  ) : null}
                </div>

                {/* Fan speed control & Hardware sync */}
                {device.type === 'fan' && (
                  <div className="mt-4 space-y-3">
                    {/* Preset speed step buttons matching ESP32 hardware button */}
                    <div>
                      <div className="flex items-center justify-between text-xs text-white/70">
                        <span>Nấc tốc độ (Đồng bộ nút SW1):</span>
                        <span className="font-mono text-[11px] text-yellow-300">
                          {device.speed === 0 ? 'Tắt' : `${device.speed}%`}
                        </span>
                      </div>
                      <div className="mt-1.5 grid grid-cols-4 gap-1.5">
                        {[
                          { label: 'Tắt (0%)', value: 0 },
                          { label: '40%', value: 40 },
                          { label: '70%', value: 70 },
                          { label: '100%', value: 100 }
                        ].map((step) => {
                          const isActive =
                            (step.value === 0 && (!device.status || device.speed === 0)) ||
                            (step.value > 0 && device.status && device.speed === step.value)
                          return (
                            <button
                              key={step.value}
                              type="button"
                              onClick={() => {
                                setSpeeds((prev) => ({ ...prev, [device.id]: step.value }))
                                send(device, step.value === 0 ? 'off' : 'set_speed', { speed: step.value })
                              }}
                              className={`rounded-xl py-1.5 text-xs font-semibold transition ${
                                isActive
                                  ? 'bg-yellow-400 text-black shadow-md shadow-yellow-500/20 ring-2 ring-yellow-300'
                                  : 'bg-white/10 text-white/80 hover:bg-white/20'
                              }`}
                            >
                              {step.label}
                            </button>
                          )
                        })}
                      </div>
                    </div>

                    {/* Continuous slider */}
                    <label className="block text-xs">
                      <div className="flex justify-between text-white/70">
                        <span>Điều chỉnh công suất mịn:</span>
                        <span className="font-mono font-medium text-yellow-300">{speeds[device.id] ?? device.speed}%</span>
                      </div>
                      <input
                        type="range"
                        min={0}
                        max={100}
                        value={speeds[device.id] ?? device.speed}
                        onPointerDown={() => {
                          dragging.current = true
                        }}
                        onChange={(event) => setSpeeds((prev) => ({ ...prev, [device.id]: Number(event.target.value) }))}
                        onPointerUp={() => {
                          dragging.current = false
                          send(device, 'set_speed', { speed: speeds[device.id] ?? device.speed })
                        }}
                        onKeyUp={(event) => {
                          if (event.key.startsWith('Arrow')) send(device, 'set_speed', { speed: speeds[device.id] ?? device.speed })
                        }}
                        className="mt-1 w-full accent-yellow-400"
                      />
                    </label>

                    {/* Mode reset & hardware guide */}
                    <div className="rounded-xl border border-white/10 bg-black/25 p-2.5 text-[11px] space-y-1.5">
                      <div className="flex items-center justify-between">
                        <span className="text-white/60">Cơ chế phần cứng (ESP32):</span>
                        {device.mode && device.mode.includes('MANUAL') && (
                          <button
                            type="button"
                            onClick={() => send(device, 'auto')}
                            className="rounded-lg bg-emerald-500/80 px-2 py-0.5 text-[10px] font-semibold text-black hover:bg-emerald-400"
                            title="Hủy manual lockdown, đưa về tự động"
                          >
                            Trả về AUTO
                          </button>
                        )}
                      </div>
                      <p className="text-white/70 leading-relaxed">
                        • <span className="font-semibold text-yellow-300">Nút SW1</span>: Chuyển tuần tự <span className="font-mono">40% ➔ 70% ➔ 100% ➔ Tắt (0%)</span>.
                        <br />
                        • <span className="font-semibold text-emerald-300">Nút SW2</span>: Hủy khóa thủ công, kích hoạt lại <span className="font-mono">AUTO_AI</span>.
                      </p>
                    </div>
                  </div>
                )}

                {/* LED Warning & Alert Indicator (No color swatches) */}
                {isLed && (
                  <div className="mt-3 space-y-3">
                    {isAlertActive ? (
                      <div className="flex items-center gap-2.5 rounded-xl border border-red-500/40 bg-red-950/60 p-3 text-red-200">
                        <span className="relative flex h-3 w-3">
                          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-red-400 opacity-75"></span>
                          <span className="relative inline-flex h-3 w-3 rounded-full bg-red-500"></span>
                        </span>
                        <div>
                          <p className="text-xs font-semibold text-red-100">
                            {level === 'SAFETY' ? 'QUÁ NHIỆT' : level === 'HOT' ? 'CẢNH BÁO NÓNG' : 'ĐANG TEST ĐÈN ĐỎ'}
                          </p>
                          <p className="text-[10px] text-red-300/80">
                            {level === 'SAFETY' ? 'Nhiệt độ vượt 45°C, mạch đang chạy quạt 100%.' : level === 'HOT' ? 'Nhiệt độ đã đạt từ 33°C.' : 'Do bạn bật thủ công, không phải do nhiệt độ.'}
                          </p>
                        </div>
                      </div>
                    ) : (
                      <div className="flex items-center gap-2 rounded-xl border border-emerald-500/20 bg-emerald-950/40 p-3 text-emerald-200">
                        <span className="h-2.5 w-2.5 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)]" />
                        <div>
                          <p className="text-xs font-medium text-emerald-100">Bình thường (An toàn)</p>
                          <p className="text-[10px] text-emerald-300/70">Nhiệt độ trong giới hạn bình thường.</p>
                        </div>
                      </div>
                    )}

                    <div className="flex gap-2 pt-1">
                      <button
                        onClick={() => send(device, level === 'TEST' ? 'safe' : 'alert')}
                        className={`w-full rounded-xl py-2 text-xs font-medium transition ${
                          level === 'TEST'
                            ? 'bg-neutral-800 text-white hover:bg-neutral-700'
                            : 'bg-red-600/80 text-white hover:bg-red-500'
                        }`}
                      >
                        {level === 'TEST' ? 'Tắt đèn test' : 'Test đèn đỏ'}
                      </button>
                    </div>
                  </div>
                )}
              </article>
            )
          })}
        </div>

        {/* Live Activity Recording Section */}
        <div className="mt-6 border-t border-white/10 pt-4">
          <div className="mb-2 flex items-center justify-between text-xs text-white/70">
            <span className="font-semibold uppercase tracking-wider">Ghi nhận hoạt động gần đây</span>
            <span className="text-[10px] text-white/50">{activityLogs.length} sự kiện</span>
          </div>
          <div className="max-h-32 overflow-y-auto space-y-1 rounded-xl bg-black/20 p-2.5 text-xs font-mono">
            {activityLogs.length === 0 ? (
              <div className="py-2 text-center text-white/50 text-[11px]">
                Chưa có thao tác nào. Lịch sử điều khiển sẽ hiển thị tại đây khi bạn bấm công tắc hoặc chỉnh tốc độ.
              </div>
            ) : (
              activityLogs.map((log) => (
                <div key={log.id} className="flex items-center justify-between py-0.5 text-white/80">
                  <span>
                    <span className="text-white/40">[{formatTime(log.created_at)}]</span> <span className="text-yellow-300">{log.device}</span>: {log.action}
                  </span>
                  <span className={`text-[11px] ${log.status === 'OK' || log.status === 'EVENT' ? 'text-emerald-400' : log.status === 'PENDING' ? 'text-white/60' : 'text-red-300'}`}>
                    {activityStatusLabel[log.status || ''] || log.status}{log.reason ? ` (${log.reason})` : ''}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>
      </section>
    </div>
  )
}
