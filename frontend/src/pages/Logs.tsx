import { useEffect, useState } from 'react'
import { activityAPI, ActivityEntry, activityStatusLabel, sensorAPI, SensorPoint } from '../services/api'

function formatStamp(value: string | null) {
  if (!value) return '--'
  const date = new Date(value)
  const time = date.toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  const day = date.toLocaleDateString('vi-VN')
  return `${time}, ${day}`
}

export default function Logs() {
  const [rows, setRows] = useState<SensorPoint[]>([])
  const [events, setEvents] = useState<ActivityEntry[]>([])
  const [hours, setHours] = useState(24)
  const [error, setError] = useState('')
  const [activeTab, setActiveTab] = useState<'sensors' | 'events'>('sensors')

  const loadData = () => {
    sensorAPI
      .getHistory(hours)
      .then((response) => setRows([...response.data.data].reverse()))
      .catch(() => setError('Không tải được dữ liệu cảm biến'))

    activityAPI
      .list(100)
      .then((response) => setEvents(response.data))
      .catch(() => undefined)
  }

  useEffect(() => {
    loadData()
    const timer = setInterval(loadData, 3000)
    return () => clearInterval(timer)
  }, [hours])

  const downloadCSV = () => {
    if (activeTab === 'sensors') {
      window.open(`/api/sensors/export-csv?hours=${hours}`, '_blank')
    } else {
      const headers = ['ID', 'Mã lệnh', 'Thiết bị', 'Hành động', 'Nguồn phát (Actor)', 'Thời gian', 'Trạng thái', 'Lý do', 'Độ trễ RTT (ms)']
      const csvRows = events.map((e) => [
        e.id,
        `"${e.cmd_id || ''}"`,
        `"${e.device || ''}"`,
        `"${e.action || ''}"`,
        `"${e.actor || ''}"`,
        `"${formatStamp(e.created_at)}"`,
        `"${activityStatusLabel[e.status || ''] || e.status || ''}"`,
        `"${e.reason || ''}"`,
        e.rtt_ms != null ? e.rtt_ms : ''
      ])
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
              Dữ liệu đồng bộ thời gian thực từ cảm biến, lệnh điều khiển và bo mạch ESP32
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={downloadCSV}
              className="flex items-center gap-1.5 rounded-full bg-yellow-400 px-4 py-2 text-xs font-semibold text-black shadow-lg transition hover:bg-yellow-300 active:scale-95"
            >
              <span>Xuất file .CSV</span>
            </button>
          </div>
        </div>

        {/* Filter and Tabs */}
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2 border-b border-white/10 pb-3">
          <div className="flex gap-2">
            <button
              onClick={() => setActiveTab('sensors')}
              className={`rounded-full px-4 py-1.5 text-xs font-semibold transition ${
                activeTab === 'sensors' ? 'bg-white text-black shadow' : 'text-white/80 hover:bg-white/10'
              }`}
            >
              Cảm biến Adafruit ({rows.length})
            </button>
            <button
              onClick={() => setActiveTab('events')}
              className={`rounded-full px-4 py-1.5 text-xs font-semibold transition ${
                activeTab === 'events' ? 'bg-white text-black shadow' : 'text-white/80 hover:bg-white/10'
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

        {error && <p className="mb-3 text-xs text-red-200 bg-red-950/40 p-2.5 rounded-xl">{error}</p>}

        {/* Sensor Table View */}
        {activeTab === 'sensors' && (
          <div className="max-h-[420px] overflow-y-auto rounded-2xl bg-white/10">
            <table className="w-full text-left text-sm">
              <thead className="sticky top-0 bg-neutral-900/90 text-white/70 backdrop-blur-md">
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
              <thead className="sticky top-0 bg-neutral-900/90 text-white/70 backdrop-blur-md">
                <tr>
                  <th className="px-4 py-3 font-medium">Thiết bị</th>
                  <th className="px-4 py-3 font-medium">Hành động / Chi tiết</th>
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
                      <td className="px-4 py-3 font-medium">
                        <span className="capitalize">{evt.device}</span>
                      </td>
                      <td className="px-4 py-3 text-white/90">
                        {evt.action}
                        {evt.rtt_ms != null && (
                          <span className="ml-2 font-mono text-[11px] text-white/50">({evt.rtt_ms}ms)</span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <span className="rounded-full bg-white/10 px-2.5 py-0.5 text-xs font-mono text-yellow-300">
                          {evt.actor || 'USER'}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-xs text-white/60 font-mono">{formatStamp(evt.created_at)}</td>
                      <td className="px-4 py-3">
                        <span
                          className={`rounded-md px-2 py-0.5 text-xs font-medium ${
                            evt.status === 'OK' || evt.status === 'EVENT'
                              ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                              : evt.status === 'PENDING'
                              ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                              : 'bg-red-500/20 text-red-300 border border-red-500/30'
                          }`}
                        >
                          {activityStatusLabel[evt.status || ''] || evt.status}
                          {evt.reason ? ` (${evt.reason})` : ''}
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
