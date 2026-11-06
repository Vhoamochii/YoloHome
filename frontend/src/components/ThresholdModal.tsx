import { FormEvent, useState } from 'react'
import { authAPI, errorMessage } from '../services/api'
import FaceCapture from './FaceCapture'

export interface Thresholds {
  maxTemp: number
  maxHumidity: number
}

const STORAGE_KEY = 'yolohome-thresholds'

export function loadThresholds(): Thresholds {
  const raw = localStorage.getItem(STORAGE_KEY)
  if (!raw) return { maxTemp: 32, maxHumidity: 70 }
  try {
    return { maxTemp: 32, maxHumidity: 70, ...JSON.parse(raw) }
  } catch {
    return { maxTemp: 32, maxHumidity: 70 }
  }
}

interface ThresholdModalProps {
  onClose: () => void
}

export default function ThresholdModal({ onClose }: ThresholdModalProps) {
  const [values, setValues] = useState<Thresholds>(loadThresholds)
  const [faceOpen, setFaceOpen] = useState(false)
  const [notice, setNotice] = useState('')

  const save = (event: FormEvent) => {
    event.preventDefault()
    localStorage.setItem(STORAGE_KEY, JSON.stringify(values))
    setNotice('Đã lưu ngưỡng trên trình duyệt này.')
  }

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/35 p-4">
      <form onSubmit={save} className="w-full max-w-md rounded-2xl bg-white p-6 text-neutral-900 shadow-2xl">
        <h2 className="text-center text-lg font-semibold">Điều chỉnh ngưỡng</h2>

        <label className="mt-5 block text-sm">
          Nhiệt độ tối đa (°C)
          <input
            type="number"
            step="0.1"
            value={values.maxTemp}
            onChange={(event) => setValues({ ...values, maxTemp: Number(event.target.value) })}
            className="mt-1 w-full rounded-lg border px-3 py-2"
          />
          <span className="mt-1 block text-xs text-neutral-500">Chỉ hiện cảnh báo trên trang Tổng quan của trình duyệt này; quạt do AI trên mạch điều khiển.</span>
        </label>

        <label className="mt-4 block text-sm">
          Độ ẩm tối đa (%)
          <input
            type="number"
            value={values.maxHumidity}
            onChange={(event) => setValues({ ...values, maxHumidity: Number(event.target.value) })}
            className="mt-1 w-full rounded-lg border px-3 py-2"
          />
          <span className="mt-1 block text-xs text-neutral-500">Giới hạn tối đa của độ ẩm là 100%.</span>
        </label>

        {notice && <p className="mt-3 text-sm text-emerald-700">{notice}</p>}

        <button
          type="button"
          onClick={() => setFaceOpen(true)}
          className="mt-4 w-full rounded-lg border border-neutral-300 py-2 text-sm"
        >
          Đăng ký khuôn mặt
        </button>

        <div className="mt-5 flex justify-end gap-2">
          <button type="button" onClick={onClose} className="rounded-lg px-4 py-2 text-sm">
            Hủy
          </button>
          <button type="submit" className="rounded-lg bg-black px-4 py-2 text-sm text-white">
            Lưu
          </button>
        </div>
      </form>

      {faceOpen && (
        <FaceCapture
          title="Đăng ký khuôn mặt"
          submitLabel="Lưu khuôn mặt"
          onClose={() => setFaceOpen(false)}
          onSubmit={async (image) => {
            try {
              await authAPI.registerFace(image)
            } catch (error) {
              throw new Error(errorMessage(error, 'Không lưu được khuôn mặt'))
            }
          }}
        />
      )}
    </div>
  )
}
