import { useEffect, useRef, useState } from 'react'

interface FaceCaptureProps {
  title: string
  submitLabel: string
  onSubmit: (image: string) => Promise<void>
  onClose: () => void
}

type Phase = 'preview' | 'checking' | 'success' | 'failed'

export default function FaceCapture({ title, submitLabel, onSubmit, onClose }: FaceCaptureProps) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const [phase, setPhase] = useState<Phase>('preview')
  const [message, setMessage] = useState('Đưa khuôn mặt vào khung hình')
  const [cameraError, setCameraError] = useState('')

  useEffect(() => {
    let stream: MediaStream | null = null
    let cancelled = false

    navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user' } })
      .then((media) => {
        if (cancelled) {
          media.getTracks().forEach((track) => track.stop())
          return
        }
        stream = media
        if (videoRef.current) {
          videoRef.current.srcObject = media
        }
      })
      .catch(() => {
        setCameraError('Không mở được camera. Hãy cấp quyền truy cập camera rồi thử lại.')
      })

    return () => {
      cancelled = true
      stream?.getTracks().forEach((track) => track.stop())
    }
  }, [])

  const capture = async () => {
    const video = videoRef.current
    if (!video || !video.videoWidth) return
    const canvas = document.createElement('canvas')
    canvas.width = video.videoWidth
    canvas.height = video.videoHeight
    const context = canvas.getContext('2d')
    if (!context) return
    context.drawImage(video, 0, 0)
    setPhase('checking')
    setMessage('Đang xác thực...')
    try {
      await onSubmit(canvas.toDataURL('image/jpeg', 0.8))
      setPhase('success')
      setMessage('Đã xác thực')
    } catch (error) {
      setPhase('failed')
      setMessage(error instanceof Error ? error.message : 'Không nhận diện được')
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-6">
      <div className="glass w-full max-w-xl rounded-[28px] p-6 text-white">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-xl font-semibold">{title}</h2>
          <button onClick={onClose} className="rounded-full px-3 py-1 text-sm text-white/80 hover:bg-white/10">
            Đóng
          </button>
        </div>

        <div className="relative overflow-hidden rounded-2xl bg-black/40">
          {cameraError ? (
            <div className="flex h-72 items-center justify-center px-6 text-center text-sm">{cameraError}</div>
          ) : (
            <video ref={videoRef} autoPlay playsInline muted className="h-72 w-full object-cover" />
          )}
          <div className="pointer-events-none absolute inset-6 rounded-2xl border-2 border-white/80" />
        </div>

        <div className="mt-4 flex items-center justify-between gap-3">
          <div>
            <p className="text-sm text-white/70">Kết quả nhận diện</p>
            <p className="font-semibold">
              {phase === 'success' && <span className="text-yellow-300">✓ {message}</span>}
              {phase === 'failed' && <span>{message}</span>}
              {phase !== 'success' && phase !== 'failed' && message}
            </p>
          </div>
          <button
            onClick={capture}
            disabled={phase === 'checking' || Boolean(cameraError)}
            className="rounded-full bg-white px-5 py-2 text-sm font-semibold text-black disabled:opacity-50"
          >
            {phase === 'checking' ? 'Đang xử lý' : submitLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
