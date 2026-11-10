import { FormEvent, useState } from 'react'

export interface Thresholds {
  maxTemp: number
  maxHumidity: number
  minLux: number
}

const STORAGE_KEY = 'yolohome-thresholds'

export function loadThresholds(): Thresholds {
  const raw = localStorage.getItem(STORAGE_KEY)
  if (!raw) return { maxTemp: 32, maxHumidity: 70, minLux: 60 }
  try {
    return { maxTemp: 32, maxHumidity: 70, minLux: 60, ...JSON.parse(raw) }
  } catch {
    return { maxTemp: 32, maxHumidity: 70, minLux: 60 }
  }
}

interface ThresholdModalProps {
  onClose: () => void
}

export default function ThresholdModal({ onClose }: ThresholdModalProps) {
  const [values, setValues] = useState<Thresholds>(loadThresholds)
  const [notice, setNotice] = useState('')

  const save = (event: FormEvent) => {
    event.preventDefault()
    localStorage.setItem(STORAGE_KEY, JSON.stringify(values))
    setNotice('Đã lưu cài đặt ngưỡng thành công.')
    setTimeout(() => {
      onClose()
    }, 800)
  }

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/45 p-4 backdrop-blur-sm">
      <form onSubmit={save} className="w-full max-w-md rounded-2xl bg-white p-6 text-neutral-900 shadow-2xl">
        <div className="flex items-center justify-between border-b pb-3 border-neutral-200">
          <h2 className="text-base font-bold text-neutral-900 flex items-center gap-2">
            ⚙️ Cài đặt ngưỡng môi trường
          </h2>
          <button type="button" onClick={onClose} className="text-neutral-400 hover:text-neutral-700 text-lg leading-none">
            &times;
          </button>
        </div>

        <label className="mt-4 block text-xs font-semibold text-neutral-700">
          Nhiệt độ tối đa (°C)
          <input
            type="number"
            step="0.5"
            min={20}
            max={60}
            value={values.maxTemp}
            onChange={(event) => setValues({ ...values, maxTemp: Number(event.target.value) })}
            className="mt-1 w-full rounded-lg border border-neutral-300 px-3 py-2 text-sm font-mono outline-none focus:border-black"
          />
          <span className="mt-1 block text-[11px] font-normal text-neutral-500">
            Hệ thống cảnh báo và bật quạt làm mát khi nhiệt độ phòng chạm ngưỡng này.
          </span>
        </label>

        <label className="mt-3 block text-xs font-semibold text-neutral-700">
          Độ ẩm tối đa (%)
          <input
            type="number"
            min={30}
            max={100}
            value={values.maxHumidity}
            onChange={(event) => setValues({ ...values, maxHumidity: Number(event.target.value) })}
            className="mt-1 w-full rounded-lg border border-neutral-300 px-3 py-2 text-sm font-mono outline-none focus:border-black"
          />
          <span className="mt-1 block text-[11px] font-normal text-neutral-500">
            Giới hạn độ ẩm không khí an toàn (mặc định 70%).
          </span>
        </label>

        <label className="mt-3 block text-xs font-semibold text-neutral-700">
          Quang thông tối thiểu (lux)
          <input
            type="number"
            min={0}
            max={500}
            value={values.minLux}
            onChange={(event) => setValues({ ...values, minLux: Number(event.target.value) })}
            className="mt-1 w-full rounded-lg border border-neutral-300 px-3 py-2 text-sm font-mono outline-none focus:border-black"
          />
          <span className="mt-1 block text-[11px] font-normal text-neutral-500">
            Ngưỡng ánh sáng tối thiểu phòng cần đạt.
          </span>
        </label>

        {notice && (
          <p className="mt-3 rounded-lg bg-emerald-50 p-2 text-xs font-medium text-emerald-700 border border-emerald-200">
            {notice}
          </p>
        )}

        <div className="mt-6 flex justify-end gap-2 border-t pt-4 border-neutral-100">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg px-4 py-2 text-xs font-medium text-neutral-600 hover:bg-neutral-100"
          >
            Hủy
          </button>
          <button
            type="submit"
            className="rounded-lg bg-black px-5 py-2 text-xs font-semibold text-white shadow hover:bg-neutral-800"
          >
            Lưu cài đặt
          </button>
        </div>
      </form>
    </div>
  )
}
