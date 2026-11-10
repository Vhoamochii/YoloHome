import { FormEvent, useEffect, useState } from 'react'
import { deviceAPI, Device, errorMessage, scheduleAPI, Schedule, ScheduleInput } from '../services/api'

const emptyForm = {
  device_id: 0,
  action: 'on',
  scheduled_time: '07:30',
  repeat_mode: 'daily',
  speed: 70,
  is_active: true
}

const actionLabel: Record<string, string> = {
  on: 'Bật',
  off: 'Tắt',
  set_speed: 'Đặt tốc độ quạt',
  alert: 'Kích hoạt cảnh báo'
}

const repeatLabel: Record<string, string> = {
  once: 'Một lần',
  daily: 'Hằng ngày',
  weekly: 'Hằng tuần'
}

export default function SchedulePage() {
  const [devices, setDevices] = useState<Device[]>([])
  const [schedules, setSchedules] = useState<Schedule[]>([])
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState<Schedule | null>(null)
  const [form, setForm] = useState(emptyForm)
  const [error, setError] = useState('')

  const load = () => {
    scheduleAPI.list().then((response) => setSchedules(response.data)).catch(() => setError('Không tải được lịch'))
    deviceAPI.getAll().then((response) => {
      setDevices(response.data)
      setForm((current) => ({ ...current, device_id: current.device_id || response.data[0]?.id || 0 }))
    }).catch(() => undefined)
  }

  useEffect(() => {
    load()
  }, [])

  const startCreate = () => {
    setEditing(null)
    setForm({ ...emptyForm, device_id: devices[0]?.id || 0 })
    setOpen(true)
  }

  const startEdit = (row: Schedule) => {
    setEditing(row)
    setForm({
      device_id: row.device_id,
      action: row.action,
      scheduled_time: (row.scheduled_time || '07:30:00').slice(0, 5),
      repeat_mode: row.repeat_mode,
      speed: row.speed ?? 70,
      is_active: row.is_active
    })
    setOpen(true)
  }

  const save = async (event: FormEvent) => {
    event.preventDefault()
    setError('')
    const body: ScheduleInput = {
      device_id: Number(form.device_id),
      action: form.action,
      scheduled_time: form.scheduled_time,
      repeat_mode: form.repeat_mode,
      speed: form.action === 'set_speed' ? Number(form.speed) : undefined,
      is_active: form.is_active
    }
    try {
      if (editing) {
        await scheduleAPI.update(editing.id, body)
      } else {
        await scheduleAPI.create(body)
      }
      setOpen(false)
      load()
    } catch (err) {
      setError(errorMessage(err, 'Không lưu được lịch'))
    }
  }

  const remove = async (id: number) => {
    await scheduleAPI.remove(id)
    load()
  }

  const toggle = async (row: Schedule) => {
    await scheduleAPI.update(row.id, { is_active: !row.is_active })
    load()
  }

  const selectedDevice = devices.find((d) => d.id === form.device_id)

  return (
    <div className="flex min-h-[640px] items-center justify-center py-6">
      <section className="glass w-full max-w-3xl rounded-[28px] p-6 shadow-2xl">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">Lập lịch điều khiển</h1>
            <p className="text-xs text-white/70">Tự động kích hoạt thiết bị theo thời gian định sẵn</p>
          </div>
          <button onClick={startCreate} className="rounded-full bg-yellow-400 px-4 py-2 text-xs font-semibold text-black transition hover:bg-yellow-300 shadow">
            + Tạo lịch mới
          </button>
        </div>
        {error && <p className="mb-3 text-xs text-red-200 bg-red-950/40 p-2.5 rounded-xl">{error}</p>}

        <div className="overflow-hidden rounded-2xl bg-white/10">
          <table className="w-full text-left text-sm">
            <thead className="text-white/70 bg-black/20">
              <tr>
                <th className="px-4 py-3 font-medium">Thiết bị</th>
                <th className="px-4 py-3 font-medium">Thời gian</th>
                <th className="px-4 py-3 font-medium">Hành động</th>
                <th className="px-4 py-3 font-medium">Lặp lại</th>
                <th className="px-4 py-3 font-medium text-right">Thao tác</th>
              </tr>
            </thead>
            <tbody>
              {schedules.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-white/60">
                    Chưa có lịch trình nào. Bấm "+ Tạo lịch mới" để thêm.
                  </td>
                </tr>
              )}
              {schedules.map((row) => (
                <tr key={row.id} className="border-t border-white/10 hover:bg-white/5 transition">
                  <td className="px-4 py-3 font-medium">{row.device_name}</td>
                  <td className="px-4 py-3 font-mono text-yellow-300 font-semibold">{row.scheduled_time?.slice(0, 5)}</td>
                  <td className="px-4 py-3">
                    {row.action === 'set_speed' ? (
                      <span>
                        Đặt tốc độ <span className="font-mono text-yellow-300 font-bold">({row.speed ?? 70}%)</span>
                      </span>
                    ) : (
                      actionLabel[row.action] || row.action
                    )}
                  </td>
                  <td className="px-4 py-3 text-xs text-white/80">
                    <span className="rounded-md bg-white/10 px-2 py-0.5">
                      {repeatLabel[row.repeat_mode] || row.repeat_mode}
                    </span>
                    {!row.is_active && <span className="ml-1 text-white/50">· tạm dừng</span>}
                  </td>
                  <td className="px-4 py-3 text-right text-xs">
                    <button
                      onClick={() => toggle(row)}
                      className={`mr-2.5 px-2.5 py-1 rounded-lg font-medium transition ${
                        row.is_active ? 'bg-white/15 text-white/80 hover:bg-white/25' : 'bg-emerald-500/30 text-emerald-300'
                      }`}
                    >
                      {row.is_active ? 'Tạm dừng' : 'Kích hoạt'}
                    </button>
                    <button onClick={() => startEdit(row)} className="mr-2 text-white/80 hover:text-white underline">
                      Sửa
                    </button>
                    <button onClick={() => remove(row.id)} className="text-red-300 hover:text-red-200">
                      Xóa
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {open && (
        <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/45 p-4 backdrop-blur-sm">
          <form onSubmit={save} className="w-full max-w-md rounded-2xl bg-white p-6 text-neutral-900 shadow-2xl">
            <h2 className="text-center text-lg font-bold">{editing ? 'Chỉnh sửa lịch trình' : 'Tạo lịch trình mới'}</h2>

            <label className="mt-4 block text-sm font-medium">
              Thiết bị
              <select
                value={form.device_id}
                onChange={(event) => setForm({ ...form, device_id: Number(event.target.value) })}
                className="mt-1 w-full rounded-lg border border-neutral-300 px-3 py-2 outline-none focus:border-black"
              >
                {devices.map((device) => (
                  <option key={device.id} value={device.id}>
                    {device.name} ({device.type === 'fan' ? 'Quạt' : 'Đèn LED'})
                  </option>
                ))}
              </select>
            </label>

            <label className="mt-3 block text-sm font-medium">
              Thời gian chạy
              <input
                type="time"
                value={form.scheduled_time}
                onChange={(event) => setForm({ ...form, scheduled_time: event.target.value })}
                className="mt-1 w-full rounded-lg border border-neutral-300 px-3 py-2 font-mono outline-none focus:border-black"
                required
              />
            </label>

            <label className="mt-3 block text-sm font-medium">
              Hành động
              <select
                value={form.action}
                onChange={(event) => setForm({ ...form, action: event.target.value })}
                className="mt-1 w-full rounded-lg border border-neutral-300 px-3 py-2 outline-none focus:border-black"
              >
                {selectedDevice?.type === 'fan' ? (
                  <>
                    <option value="on">Bật quạt (Mặc định)</option>
                    <option value="set_speed">Đặt tốc độ cụ thể</option>
                    <option value="off">Tắt quạt</option>
                  </>
                ) : (
                  <>
                    <option value="alert">Kích hoạt cảnh báo ĐỎ</option>
                    <option value="safe">Tắt cảnh báo (Về an toàn)</option>
                  </>
                )}
              </select>
            </label>

            {/* Custom Speed Selection Box for Fan */}
            {form.action === 'set_speed' && (
              <div className="mt-3 rounded-xl border border-neutral-200 bg-neutral-50 p-3.5">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-semibold text-neutral-700">Tốc độ quạt mong muốn:</span>
                  <span className="font-mono text-sm font-bold text-black">{form.speed}%</span>
                </div>

                {/* Quick Presets matching ESP32 step buttons */}
                <div className="mt-2 grid grid-cols-3 gap-2">
                  {[40, 70, 100].map((spd) => (
                    <button
                      key={spd}
                      type="button"
                      onClick={() => setForm({ ...form, speed: spd })}
                      className={`rounded-lg py-1.5 text-xs font-semibold transition ${
                        form.speed === spd
                          ? 'bg-black text-white shadow'
                          : 'bg-white border border-neutral-300 text-neutral-700 hover:bg-neutral-100'
                      }`}
                    >
                      {spd}%
                    </button>
                  ))}
                </div>

                {/* Slider */}
                <input
                  type="range"
                  min={10}
                  max={100}
                  step={5}
                  value={form.speed}
                  onChange={(e) => setForm({ ...form, speed: Number(e.target.value) })}
                  className="mt-3 w-full accent-black cursor-pointer"
                />
              </div>
            )}

            <label className="mt-3 block text-sm font-medium">
              Chế độ lặp lại
              <select
                value={form.repeat_mode}
                onChange={(event) => setForm({ ...form, repeat_mode: event.target.value })}
                className="mt-1 w-full rounded-lg border border-neutral-300 px-3 py-2 outline-none focus:border-black"
              >
                {Object.entries(repeatLabel).map(([value, label]) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>
            </label>

            {error && <p className="mt-3 text-xs text-red-600 font-medium">{error}</p>}

            <div className="mt-6 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="rounded-lg px-4 py-2 text-xs font-medium text-neutral-600 hover:bg-neutral-100"
              >
                Hủy
              </button>
              <button
                type="submit"
                className="rounded-lg bg-black px-5 py-2 text-xs font-semibold text-white shadow hover:bg-neutral-800"
              >
                Lưu lịch trình
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  )
}
