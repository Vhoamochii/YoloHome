import { useEffect, useMemo, useState } from 'react'
import { activityAPI, ActivityEntry, activityStatusLabel, latestOnly, sensorAPI, SensorPoint } from '../services/api'

function formatStamp(value: string | null) {
  if (!value) return '--'
  const date = new Date(value)
  const time = date.toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  const day = date.toLocaleDateString('vi-VN')
  return `${time}, ${day}`
}

export default function Logs() {
  const [rows, setRows] = useState<SensorPoint[]>([])
  const [hours, setHours] = useState(24)
  const [error, setError] = useState('')
  const [activeTab, setActiveTab] = useState<'sensors' | 'events'>('sensors')
  const [events, setEvents] = useState<ActivityEntry[]>([])

  useEffect(() => {
    // Changing the range quickly must not let the slower, older request win.
    let cancelled = false
    sensorAPI
      .getHistory(hours)
      .then((response) => {
        if (!cancelled) setRows([...response.data.data].reverse())
      })
      .catch(() => {
        if (!cancelled) setError('Không tải được dữ liệu nhật ký')
      })
    return () => {
      cancelled = true
    }
  }, [hours])

  const loadEvents = useMemo(
    () => latestOnly(() => activityAPI.list(200), (response) => setEvents(response.data)),
    []
  )

  useEffect(() => {
    loadEvents().catch(() => setError('Không tải được nhật ký hoạt động'))
    const timer = window.setInterval(() => loadEvents().catch(() => undefined), 5000)
    return () => window.clearInterval(timer)
  }, [loadEvents])

  const downloadCSV = () => {
    if (activeTab === 'sensors') {
      // Use backend CSV export endpoint
      window.open(`/api/sensors/export-csv?hours=${hours}`, '_blank')
    } else {
      // Client-side CSV export for Activity Events
      const headers = ['ID', 'Thiết bị', 'Hành động', 'Nguồn phát (Actor)', 'Thời gian', 'Trạng thái', 'Lý do', 'RTT (ms)']
      const csvRows = events.map((e) => [e.id, e.device, `"${e.action}"`, e.actor, `"${formatStamp(e.created_at)}"`, e.status, e.reason ?? '', e.rtt_ms ?? ''])
      const csvContent = '\ufeff' + [headers.join(','), ...csvRows.map((r) => r.join(','))].join('\n')
      const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', `yolohome_activity_logs_${new Date().toISOString().slice(0, 10)}.csv`)
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
    }
  }

  return (
    <div className="flex min-h-[640px] items-center justify-center py-6">
      <section className="glass w-full max-w-4xl rounded-[28px] p-6 shadow-2xl">
        {/* Header with Title and CSV Export */}
        <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Ghi nhận hoạt động & Nhật ký</h1>
            <p className="text-xs text-white/70">
              Dữ liệu đồng bộ thời gian thực từ cảm biến và broker Adafruit IO
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={downloadCSV}
              className="flex items-center gap-1.5 rounded-full bg-yellow-400 px-4 py-2 text-xs font-semibold text-black shadow-lg transition hover:bg-yellow-300 active:scale-95"
            >
              <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3" />
              </svg>
              <span>Xuất file .CSV</span>
            </button>
          </div>
        </div>

        {/* Filter and Tabs */}
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2 border-b border-white/10 pb-3">
          <div className="flex gap-2">
            <button
              onClick={() => setActiveTab('sensors')}
              className={`rounded-full px-4 py-1.5 text-xs font-medium transition ${
                activeTab === 'sensors' ? 'bg-white text-black' : 'text-white/80 hover:bg-white/10'
              }`}
            >
              Cảm biến Adafruit ({rows.length})
            </button>
            <button
              onClick={() => setActiveTab('events')}
              className={`rounded-full px-4 py-1.5 text-xs font-medium transition ${
                activeTab === 'events' ? 'bg-white text-black' : 'text-white/80 hover:bg-white/10'
              }`}
            >
              Nhật ký lệnh & Thiết bị ({events.length})
            </button>
          </div>

          {activeTab === 'sensors' && (
            <div className="flex items-center gap-1 text-xs text-white/80">
              <span>Khoảng thời gian:</span>
              <select
                value={hours}
                onChange={(e) => setHours(Number(e.target.value))}
                className="rounded-lg bg-black/40 px-2.5 py-1 text-xs text-white outline-none focus:ring-1 focus:ring-yellow-400"
              >
                <option value={24}>24 giờ qua</option>
                <option value={72}>3 ngày qua</option>
                <option value={168}>7 ngày qua</option>
                <option value={720}>30 ngày qua</option>
              </select>
            </div>
          )}
        </div>

        {error && <p className="mb-3 text-sm text-red-200">{error}</p>}

        {/* Sensor Table View */}
        {activeTab === 'sensors' && (
          <div className="max-h-[420px] overflow-y-auto rounded-2xl bg-white/10">
            <table className="w-full text-left text-sm">
              <thead className="sticky top-0 bg-neutral-900/80 text-white/70 backdrop-blur-md">
                <tr>
                  <th className="px-4 py-3 font-medium">#ID</th>
                  <th className="px-4 py-3 font-medium">Thời gian</th>
                  <th className="px-4 py-3 font-medium">Nhiệt độ</th>
                  <th className="px-4 py-3 font-medium">Độ ẩm</th>
                  <th className="px-4 py-3 font-medium">Nguồn dữ liệu</th>
                </tr>
              </thead>
              <tbody>
                {rows.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="px-4 py-8 text-center text-white/70">
                      Chưa có dữ liệu cảm biến. Dữ liệu sẽ xuất hiện tự động khi mạch ESP32 gửi thông số lên Adafruit IO.
                    </td>
                  </tr>
                ) : (
                  rows.map((row) => (
                    <tr key={row.id} className="border-t border-white/5 transition hover:bg-white/5">
                      <td className="px-4 py-2.5 text-xs text-white/60">#{row.id}</td>
                      <td className="px-4 py-2.5 font-mono text-xs">{formatStamp(row.recorded_at)}</td>
                      <td className="px-4 py-2.5 font-medium text-emerald-300">
                        {row.temperature != null ? `${row.temperature.toFixed(1)}°C` : '--'}
                      </td>
                      <td className="px-4 py-2.5 font-medium text-cyan-300">
                        {row.humidity != null ? `${row.humidity.toFixed(1)}%` : '--'}
                      </td>
                      <td className="px-4 py-2.5 text-xs text-white/60">DHT20 via MQTT</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}

        {/* Activity & Events Table View */}
        {activeTab === 'events' && (
          <div className="max-h-[420px] overflow-y-auto rounded-2xl bg-white/10">
            <table className="w-full text-left text-sm">
              <thead className="sticky top-0 bg-neutral-900/80 text-white/70 backdrop-blur-md">
                <tr>
                  <th className="px-4 py-3 font-medium">Thiết bị</th>
                  <th className="px-4 py-3 font-medium">Hành động / Giá trị</th>
                  <th className="px-4 py-3 font-medium">Nguồn ra lệnh</th>
                  <th className="px-4 py-3 font-medium">Thời gian</th>
                  <th className="px-4 py-3 font-medium">Trạng thái</th>
                </tr>
              </thead>
              <tbody>
                {events.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="px-4 py-8 text-center text-white/70">
                      Chưa có sự kiện nào. Dữ liệu sẽ xuất hiện khi bạn điều khiển thiết bị hoặc khi ESP32 phản hồi.
                    </td>
                  </tr>
                ) : (
                  events.map((evt) => (
                    <tr key={evt.id} className="border-t border-white/5 transition hover:bg-white/5">
                      <td className="px-4 py-3 font-medium">{evt.device}</td>
                      <td className="px-4 py-3 text-white/90">{evt.action}</td>
                      <td className="px-4 py-3">
                        <span className="rounded-full bg-white/10 px-2.5 py-0.5 text-xs font-mono text-yellow-300">
                          {evt.actor}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-xs text-white/60">{formatStamp(evt.created_at)}</td>
                      <td className="px-4 py-3">
                        <span className={`rounded-md px-2 py-0.5 text-xs ${evt.status === 'OK' || evt.status === 'EVENT' ? 'bg-emerald-500/20 text-emerald-300' : evt.status === 'PENDING' ? 'bg-white/10 text-white/80' : 'bg-red-500/20 text-red-200'}`}>
                          {activityStatusLabel[evt.status || ''] || evt.status}{evt.reason ? ` (${evt.reason})` : ''}
                        </span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  )
}
