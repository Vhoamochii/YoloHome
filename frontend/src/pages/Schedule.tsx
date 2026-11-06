import { FormEvent, useEffect, useState } from 'react'
import { deviceAPI, Device, errorMessage, scheduleAPI, Schedule, ScheduleInput } from '../services/api'

const emptyForm = {
  device_id: 0,
  action: 'on',
  scheduled_time: '07:30',
  repeat_mode: 'daily',
  is_active: true,
  speed: 70
}

const actionLabel: Record<string, string> = {
  on: 'Bật',
  off: 'Tắt',
  set_speed: 'Đặt tốc độ',
  alert: 'Bật đèn đỏ',
  safe: 'Tắt đèn đỏ'
}

const actionsFor = (type: string | null | undefined) =>
  type === 'led' ? ['alert', 'safe'] : ['on', 'off', 'set_speed']

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
      is_active: row.is_active,
      speed: row.speed ?? 70
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
      is_active: form.is_active,
      speed: form.action === 'set_speed' ? form.speed : null
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

  return (
    <div className="flex min-h-[640px] items-center justify-center">
      <section className="glass w-full max-w-3xl rounded-[28px] p-5">
        <div className="mb-4 flex items-center justify-between">
          <h1 className="text-2xl font-semibold">Lập lịch điều khiển</h1>
          <button onClick={startCreate} className="rounded-full bg-white px-4 py-2 text-sm font-semibold text-black">
            Tạo lịch mới
          </button>
        </div>
        {error && <p className="mb-3 text-sm text-red-200">{error}</p>}

        <div className="overflow-hidden rounded-2xl bg-white/10">
          <table className="w-full text-left text-sm">
            <thead className="text-white/70">
              <tr>
                <th className="px-4 py-3 font-medium">Thiết bị</th>
                <th className="px-4 py-3 font-medium">Thời gian</th>
                <th className="px-4 py-3 font-medium">Hành động</th>
                <th className="px-4 py-3 font-medium">Lặp</th>
                <th className="px-4 py-3 font-medium"></th>
              </tr>
            </thead>
            <tbody>
              {schedules.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-6 text-white/70">Chưa có lịch nào.</td>
                </tr>
              )}
              {schedules.map((row) => (
                <tr key={row.id} className="border-t border-white/10">
                  <td className="px-4 py-3">{row.device_name}</td>
                  <td className="px-4 py-3">{row.scheduled_time?.slice(0, 5)}</td>
                  <td className="px-4 py-3">{actionLabel[row.action] || row.action}{row.action === 'set_speed' && row.speed != null ? ` ${row.speed}%` : ''}</td>
                  <td className="px-4 py-3">{repeatLabel[row.repeat_mode] || row.repeat_mode}{row.is_active ? '' : ' · tạm dừng'}</td>
                  <td className="px-4 py-3 text-right">
                    <button onClick={() => toggle(row)} className="mr-3 text-white/80">{row.is_active ? 'Tạm dừng' : 'Bật'}</button>
                    <button onClick={() => startEdit(row)} className="mr-3">Sửa</button>
                    <button onClick={() => remove(row.id)}>Xóa</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {open && (
        <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/35 p-4">
          <form onSubmit={save} className="w-full max-w-md rounded-2xl bg-white p-6 text-neutral-900 shadow-2xl">
            <h2 className="text-center text-lg font-semibold">{editing ? 'Chỉnh sửa lịch' : 'Tạo lịch mới'}</h2>
            <label className="mt-4 block text-sm">
              Thiết bị
              <select
                value={form.device_id}
                onChange={(event) => {
                  const id = Number(event.target.value)
                  const allowed = actionsFor(devices.find((device) => device.id === id)?.type)
                  setForm({ ...form, device_id: id, action: allowed.includes(form.action) ? form.action : allowed[0] })
                }}
                className="mt-1 w-full rounded-lg border px-3 py-2"
              >
                {devices.map((device) => (
                  <option key={device.id} value={device.id}>{device.name}</option>
                ))}
              </select>
            </label>
            <label className="mt-3 block text-sm">
              Thời gian
              <input
                type="time"
                value={form.scheduled_time}
                onChange={(event) => setForm({ ...form, scheduled_time: event.target.value })}
                className="mt-1 w-full rounded-lg border px-3 py-2"
                required
              />
            </label>
            <label className="mt-3 block text-sm">
              Hành động
              <select
                value={form.action}
                onChange={(event) => setForm({ ...form, action: event.target.value })}
                className="mt-1 w-full rounded-lg border px-3 py-2"
              >
                {actionsFor(devices.find((device) => device.id === form.device_id)?.type).map((value) => (
                  <option key={value} value={value}>{actionLabel[value]}</option>
                ))}
              </select>
            </label>
            {form.action === 'set_speed' && (
              <label className="mt-3 block text-sm">
                Tốc độ (%)
                <input
                  type="number"
                  min={0}
                  max={100}
                  value={form.speed}
                  onChange={(event) => setForm({ ...form, speed: Number(event.target.value) })}
                  className="mt-1 w-full rounded-lg border px-3 py-2"
                  required
                />
              </label>
            )}
            <label className="mt-3 block text-sm">
              Lặp lại
              <select
                value={form.repeat_mode}
                onChange={(event) => setForm({ ...form, repeat_mode: event.target.value })}
                className="mt-1 w-full rounded-lg border px-3 py-2"
              >
                {Object.entries(repeatLabel).map(([value, label]) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>
            </label>
            {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
            <div className="mt-5 flex justify-end gap-2">
              <button type="button" onClick={() => setOpen(false)} className="rounded-lg px-4 py-2 text-sm">Hủy</button>
              <button className="rounded-lg bg-black px-4 py-2 text-sm text-white">Lưu</button>
            </div>
          </form>
        </div>
      )}
    </div>
  )
}
