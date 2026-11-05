import { useEffect, useState } from 'react'
import { sensorAPI, SensorPoint } from '../services/api'

function formatStamp(value: string | null) {
  if (!value) return '--'
  const date = new Date(value)
  const time = date.toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })
  const day = date.toLocaleDateString('vi-VN')
  return `${time}, ${day}`
}

export default function Logs() {
  const [rows, setRows] = useState<SensorPoint[]>([])
  const [error, setError] = useState('')

  useEffect(() => {
    sensorAPI.getHistory(168)
      .then((response) => setRows([...response.data.data].reverse()))
      .catch(() => setError('Không tải được nhật ký'))
  }, [])

  return (
    <div className="flex min-h-[640px] items-center justify-center">
      <section className="glass w-full max-w-3xl rounded-[28px] p-5">
        <h1 className="mb-4 text-2xl font-semibold">Nhật ký cảm biến</h1>
        {error && <p className="mb-3 text-sm text-red-200">{error}</p>}
        <div className="overflow-hidden rounded-2xl bg-white/10">
          <table className="w-full text-left text-sm">
            <thead className="text-white/70">
              <tr>
                <th className="px-4 py-3 font-medium">Thời gian</th>
                <th className="px-4 py-3 font-medium">Nhiệt độ</th>
                <th className="px-4 py-3 font-medium">Độ ẩm</th>
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 && (
                <tr>
                  <td colSpan={3} className="px-4 py-6 text-white/70">Chưa có bản ghi. Dữ liệu sẽ xuất hiện khi cảm biến gửi về.</td>
                </tr>
              )}
              {rows.map((row) => (
                <tr key={row.id} className="border-t border-white/10">
                  <td className="px-4 py-3">{formatStamp(row.recorded_at)}</td>
                  <td className="px-4 py-3">{row.temperature ?? '--'}°C</td>
                  <td className="px-4 py-3">{row.humidity ?? '--'}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}
