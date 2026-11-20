import { useCallback, useEffect, useState } from 'react'
import { authAPI, errorMessage, FaceCounts } from '../services/api'
import FaceCapture from './FaceCapture'

type Kind = 'plain' | 'mask'

// Enrolling the bare face is enough: the server adds synthetic-mask samples, so a masked face
// still logs in. Real-mask samples are optional, for people who get rejected while masked.
const CAPTURE: Record<Kind, { title: string; hint: string }> = {
  plain: {
    title: 'Chụp khuôn mặt',
    hint: 'Không đeo khẩu trang. Hay đeo kính thì cứ đeo như mọi ngày. Bấm chụp rồi từ từ quay đầu nhẹ sang trái, sang phải.'
  },
  mask: {
    title: 'Chụp khi đeo khẩu trang',
    hint: 'Đeo khẩu trang như khi ra đường. Bấm chụp rồi từ từ quay đầu nhẹ sang trái, sang phải.'
  }
}

interface FaceSetupProps {
  onClose: () => void
  onChanged: () => void // the user's has_face may have changed
}

export default function FaceSetup({ onClose, onChanged }: FaceSetupProps) {
  const [counts, setCounts] = useState<FaceCounts | null>(null)
  const [capturing, setCapturing] = useState<Kind | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const load = useCallback(() => {
    authAPI
      .faceStatus()
      .then((response) => setCounts(response.data.counts))
      .catch((err) => setError(errorMessage(err, 'Không tải được trạng thái Face ID')))
  }, [])

  useEffect(load, [load])

  const enroll = async (kind: Kind, images: string[]) => {
    try {
      const { data } = await authAPI.faceEnroll(kind, images)
      onChanged()
      const skipped = data.rejected.length ? ` Bỏ ${data.rejected.length} ảnh: ${data.rejected[0].reason}.` : ''
      const masked = kind === 'plain' ? ' Đeo khẩu trang vẫn đăng nhập được.' : ''
      return `Đã lưu ${data.accepted}/${images.length} ảnh.${skipped}${masked}`
    } catch (err) {
      throw new Error(errorMessage(err, 'Không lưu được khuôn mặt'))
    }
  }

  const remove = async () => {
    if (!window.confirm('Xoá toàn bộ ảnh khuôn mặt của bạn? Sau đó chỉ đăng nhập được bằng mật khẩu.')) return
    setBusy(true)
    try {
      await authAPI.faceDelete()
      onChanged()
      load()
    } catch (err) {
      setError(errorMessage(err, 'Không xoá được Face ID'))
    } finally {
      setBusy(false)
    }
  }

  if (capturing) {
    return (
      <FaceCapture
        title={CAPTURE[capturing].title}
        hint={CAPTURE[capturing].hint}
        submitLabel="Bắt đầu chụp"
        frames={10}
        intervalMs={400}
        onSubmit={(images) => enroll(capturing, images)}
        onClose={() => {
          setCapturing(null)
          load()
        }}
      />
    )
  }

  const enrolled = counts !== null && counts.plain + counts.mask > 0
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-6">
      <div className="glass w-full max-w-md rounded-[28px] p-6 text-white">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-xl font-semibold">Face ID</h2>
          <button onClick={onClose} className="rounded-full px-3 py-1 text-sm text-white/80 hover:bg-white/10">
            Đóng
          </button>
        </div>

        {error && <p className="mb-3 text-sm text-red-300">{error}</p>}
        {counts && (
          <p className="text-sm text-white/80">
            {enrolled
              ? `Đã lưu ${counts.plain} ảnh khuôn mặt${counts.mask ? ` và ${counts.mask} ảnh đeo khẩu trang` : ''}. Đeo khẩu trang vẫn đăng nhập được.`
              : 'Chưa có Face ID. Chụp khuôn mặt khoảng 4 giây là xong, sau đó đeo khẩu trang vẫn đăng nhập được.'}
          </p>
        )}

        <div className="mt-5 flex flex-col gap-2">
          <button
            onClick={() => setCapturing('plain')}
            disabled={!counts}
            className="rounded-full bg-white py-2 text-sm font-semibold text-black disabled:opacity-50"
          >
            {enrolled ? 'Chụp thêm (ví dụ lúc có hoặc không đeo kính)' : 'Chụp khuôn mặt'}
          </button>
          {enrolled && (
            <>
              <button
                onClick={() => setCapturing('mask')}
                className="rounded-full border border-white/40 py-2 text-sm hover:bg-white/10"
              >
                Thêm ảnh đeo khẩu trang (nếu hay bị từ chối khi đeo)
              </button>
              <button
                onClick={remove}
                disabled={busy}
                className="py-1 text-xs text-red-300 hover:text-red-200 disabled:opacity-50"
              >
                Xoá Face ID
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
