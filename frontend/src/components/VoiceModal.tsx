import { useEffect, useRef, useState } from 'react'
import { deviceAPI, Device, errorMessage, sensorAPI } from '../services/api'

interface VoiceModalProps {
  devices: Device[]
  onDone: () => void
  onClose: () => void
}

type Phase = 'ready' | 'listening' | 'processing' | 'result'

interface SpeechEvent {
  results: ArrayLike<ArrayLike<{ transcript: string }>>
}

interface SpeechRecognizer {
  lang: string
  continuous: boolean
  interimResults: boolean
  onresult: ((event: SpeechEvent) => void) | null
  onerror: ((event: { error: string }) => void) | null
  onend: (() => void) | null
  start: () => void
  stop: () => void
}

function getRecognizer(): SpeechRecognizer | null {
  const speechWindow = window as Window & {
    webkitSpeechRecognition?: new () => SpeechRecognizer
    SpeechRecognition?: new () => SpeechRecognizer
  }
  const Ctor = speechWindow.SpeechRecognition || speechWindow.webkitSpeechRecognition
  return Ctor ? new Ctor() : null
}

function findDevice(devices: Device[], type: string) {
  return devices.find((device) => device.type === type)
}

function speakFeedback(text: string) {
  if (!('speechSynthesis' in window)) return
  try {
    window.speechSynthesis.cancel() // stop any ongoing speech
    const utterance = new SpeechSynthesisUtterance(text)
    utterance.lang = 'vi-VN'
    utterance.rate = 1.05
    window.speechSynthesis.speak(utterance)
  } catch {
    // Ignore speech synthesis errors
  }
}

export default function VoiceModal({ devices, onDone, onClose }: VoiceModalProps) {
  const [phase, setPhase] = useState<Phase>('ready')
  const [transcript, setTranscript] = useState('Đang sẵn sàng lắng nghe...')
  const [detail, setDetail] = useState('')
  const [activeMic, setActiveMic] = useState<string>('')
  const recognizerRef = useRef<SpeechRecognizer | null>(null)

  const updateAudioDevices = async () => {
    if (!navigator.mediaDevices?.enumerateDevices) return
    try {
      const allDevs = await navigator.mediaDevices.enumerateDevices()
      const mics = allDevs.filter((d) => d.kind === 'audioinput')
      if (mics.length > 0) {
        const named = mics.find((m) => m.label && m.deviceId === 'default') || mics.find((m) => m.label) || mics[0]
        setActiveMic(named.label ? named.label : `Đã kết nối (${mics.length} micro)`)
      } else {
        setActiveMic('Không tìm thấy thiết bị micro')
      }
    } catch {
      // Ignore
    }
  }

  const startListening = () => {
    const recognizer = getRecognizer()
    if (!recognizer) {
      setPhase('result')
      setTranscript('Trình duyệt không hỗ trợ Web Speech API')
      setDetail('Vui lòng sử dụng Google Chrome hoặc Microsoft Edge để dùng tính năng giọng nói.')
      return
    }

    recognizerRef.current = recognizer
    recognizer.lang = 'vi-VN'
    recognizer.continuous = false
    recognizer.interimResults = false

    recognizer.onresult = (event: SpeechEvent) => {
      const phrase = event.results[0]?.[0]?.transcript || ''
      setTranscript(`"${phrase}"`)
      executeCommand(phrase)
      updateAudioDevices()
    }

    recognizer.onerror = (err) => {
      setPhase('result')
      if (err.error === 'not-allowed') {
        setDetail('Quyền truy cập micro đã bị chặn. Vui lòng cấp quyền trong cài đặt trình duyệt (biểu tượng ổ khóa ở thanh địa chỉ).')
      } else if (err.error === 'no-speech') {
        setDetail(
          'Không nhận được âm thanh. Nếu đang cắm tai nghe: hãy kiểm tra tai nghe có micro tích hợp không (tai nghe không mic có thể khiến máy ngắt mic laptop), hoặc kiểm tra âm lượng mic trong Cài đặt Windows.'
        )
      } else if (err.error === 'audio-capture') {
        setDetail('Không thu được tín hiệu từ micro (thiết bị bị chiếm dụng hoặc jack cắm chưa nhận diện mic). Hãy thử rút ra cắm lại.')
      } else if (err.error === 'network') {
        setDetail('Lỗi kết nối mạng tới dịch vụ nhận diện giọng nói Google.')
      } else {
        setDetail(`Lỗi micro: ${err.error || 'không xác định'}.`)
      }
      updateAudioDevices()
    }

    recognizer.onend = () => {
      setPhase((prev) => (prev === 'listening' ? 'result' : prev))
    }

    setPhase('listening')
    setTranscript('Hãy nói câu lệnh của bạn...')
    setDetail('')
    try {
      recognizer.start()
      updateAudioDevices()
    } catch {
      setPhase('result')
      setDetail('Không thể khởi động micro. Vui lòng thử lại.')
    }
  }

  useEffect(() => {
    updateAudioDevices()
    startListening()

    const handleDeviceChange = () => {
      updateAudioDevices()
    }
    navigator.mediaDevices?.addEventListener('devicechange', handleDeviceChange)

    return () => {
      navigator.mediaDevices?.removeEventListener('devicechange', handleDeviceChange)
      if (recognizerRef.current) {
        try {
          recognizerRef.current.stop()
        } catch {
          // Ignore
        }
      }
      if ('speechSynthesis' in window) {
        window.speechSynthesis.cancel()
      }
    }
  }, [])

  const executeCommand = async (phrase: string) => {
    setPhase('processing')
    const command = phrase.toLowerCase().trim()
    const fan = findDevice(devices, 'fan')
    const led = findDevice(devices, 'led')

    try {
      // 1. Lệnh hỏi đáp trạng thái cảm biến môi trường (Query environment)
      if (
        command.includes('nhiệt độ') ||
        command.includes('độ ẩm') ||
        command.includes('thời tiết') ||
        command.includes('môi trường') ||
        command.includes('bao nhiêu độ')
      ) {
        const res = await sensorAPI.getCurrent()
        const t = res.data.temperature != null ? `${res.data.temperature}°C` : 'chưa xác định'
        const h = res.data.humidity != null ? `${res.data.humidity}%` : 'chưa xác định'
        const reply = `Nhiệt độ hiện tại là ${t}, độ ẩm ${h}.`
        setDetail(reply)
        speakFeedback(`Nhiệt độ hiện tại là ${res.data.temperature ?? '--'} độ C, độ ẩm ${res.data.humidity ?? '--'} phần trăm.`)
        setPhase('result')
        return
      }

      // 2. Chế độ quạt tự động (AUTO_AI mode)
      if (
        command.includes('tự động') ||
        command.includes('chế độ ai') ||
        command.includes('bật auto') ||
        command.includes('auto')
      ) {
        if (fan) {
          await deviceAPI.control(fan.id, 'auto', { actor: 'VOICE' })
          const reply = 'Đã chuyển sang chế độ Quạt Tự động (AUTO_AI)'
          setDetail(reply)
          speakFeedback(reply)
          setPhase('result')
          onDone()
          return
        }
      }

      // 3. Tắt quạt (Shutdown / 0%)
      if (
        (command.includes('tắt') || command.includes('dừng') || command.includes('ngừng') || command.includes('ngắt')) &&
        (command.includes('quạt') || command.includes('gió'))
      ) {
        if (fan) {
          await deviceAPI.control(fan.id, 'off', { actor: 'VOICE' })
          const reply = 'Đã tắt quạt'
          setDetail(reply)
          speakFeedback(reply)
          setPhase('result')
          onDone()
          return
        }
      }

      // 4. Quạt theo các nấc tốc độ phần cứng (40%, 70%, 100%) hoặc số cụ thể
      const isFanIntent = command.includes('quạt') || command.includes('tốc độ') || command.includes('mức')
      if (isFanIntent && fan) {
        // Kiểm tra số phần trăm rõ ràng: e.g. "quạt 40%", "quạt 100%", "tốc độ 70"
        const numMatch = command.match(/(\d{1,3})\s*(%|phần trăm)?/)
        let targetSpeed: number | null = null

        if (numMatch) {
          const val = parseInt(numMatch[1], 10)
          if (!isNaN(val) && val >= 0 && val <= 100) {
            targetSpeed = val
          }
        } else if (command.includes('nhẹ') || command.includes('số một') || command.includes('số 1') || command.includes('mức 1')) {
          targetSpeed = 40
        } else if (command.includes('vừa') || command.includes('số hai') || command.includes('số 2') || command.includes('mức 2')) {
          targetSpeed = 70
        } else if (command.includes('mạnh') || command.includes('tối đa') || command.includes('hết cỡ') || command.includes('số ba') || command.includes('số 3') || command.includes('mức 3')) {
          targetSpeed = 100
        }

        if (targetSpeed !== null) {
          await deviceAPI.control(fan.id, 'set_speed', { speed: targetSpeed, actor: 'VOICE' })
          const reply = `Đã đặt tốc độ quạt là ${targetSpeed}%`
          setDetail(reply)
          speakFeedback(reply)
          setPhase('result')
          onDone()
          return
        }
      }

      // 5. Bật quạt thông thường (Mặc định nấc 70%)
      if (
        (command.includes('bật') || command.includes('mở') || command.includes('chạy') || command.includes('khởi động')) &&
        (command.includes('quạt') || command.includes('gió'))
      ) {
        if (fan) {
          await deviceAPI.control(fan.id, 'on', { actor: 'VOICE' })
          const reply = 'Đã bật quạt (tốc độ tiêu chuẩn 70%)'
          setDetail(reply)
          speakFeedback('Đã bật quạt')
          setPhase('result')
          onDone()
          return
        }
      }

      // 6. Đèn LED Cảnh báo Quá nhiệt (Alert indicator)
      if (led) {
        // Ưu tiên 1: Lệnh TẮT / HỦY cảnh báo hoặc đưa về an toàn
        const isTurnOffAlert =
          command.includes('tắt cảnh báo') ||
          command.includes('hủy cảnh báo') ||
          command.includes('dừng cảnh báo') ||
          command.includes('ngừng cảnh báo') ||
          command.includes('hết cảnh báo') ||
          command.includes('tắt báo động') ||
          command.includes('hủy báo động') ||
          command.includes('dừng báo động') ||
          command.includes('tắt đèn đỏ') ||
          command.includes('tắt đèn') ||
          command.includes('an toàn') ||
          command.includes('đèn xanh') ||
          command.includes('bình thường') ||
          ((command.includes('tắt') || command.includes('hủy') || command.includes('ngừng') || command.includes('dừng')) &&
            (command.includes('cảnh báo') || command.includes('báo động') || command.includes('đèn') || command.includes('alert')))

        if (isTurnOffAlert) {
          await deviceAPI.control(led.id, 'safe', { actor: 'VOICE' })
          const reply = 'Đã tắt đèn cảnh báo, đưa hệ thống về trạng thái an toàn'
          setDetail(reply)
          speakFeedback('Đã tắt cảnh báo, hệ thống trở về trạng thái an toàn')
          setPhase('result')
          onDone()
          return
        }

        // Ưu tiên 2: Lệnh KÍCH HOẠT cảnh báo đỏ / test báo động
        const isTurnOnAlert =
          command.includes('cảnh báo') ||
          command.includes('báo động') ||
          command.includes('đèn đỏ') ||
          command.includes('quá nhiệt') ||
          command.includes('nguy hiểm') ||
          command.includes('bật đèn')

        if (isTurnOnAlert) {
          await deviceAPI.control(led.id, 'alert', { actor: 'VOICE' })
          const reply = 'Đã kích hoạt Đèn Cảnh báo Đỏ (> 35°C)'
          setDetail(reply)
          speakFeedback('Đã kích hoạt cảnh báo đỏ')
          setPhase('result')
          onDone()
          return
        }
      }

      // Không khớp lệnh nào
      const notFoundMsg = 'Chưa nhận ra câu lệnh. Vui lòng nói theo các gợi ý bên dưới.'
      setDetail(notFoundMsg)
      speakFeedback('Chưa nhận ra câu lệnh.')
      setPhase('result')
    } catch (error) {
      setDetail(errorMessage(error, 'Không thể gửi lệnh điều khiển'))
      setPhase('result')
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm">
      <div className="glass w-full max-w-md rounded-[28px] p-6 text-center text-white shadow-2xl border border-white/10">
        <div className="flex items-center justify-between pb-3 border-b border-white/10">
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-yellow-400 animate-pulse" />
            <span className="text-xs font-semibold uppercase tracking-wider text-white/90">Trợ lý giọng nói</span>
          </div>
          <span className="text-[11px] text-white/40">Voice Assistant</span>
        </div>

        {/* Microphone animation orb */}
        <div className="my-6 flex flex-col items-center justify-center">
          <div className="relative flex items-center justify-center">
            {phase === 'listening' && (
              <>
                <div className="absolute h-28 w-28 rounded-full bg-yellow-400/20 animate-ping pointer-events-none" />
                <div className="absolute h-24 w-24 rounded-full bg-yellow-400/30 animate-pulse pointer-events-none" />
              </>
            )}
            <button
              type="button"
              onClick={startListening}
              className={`relative z-10 flex h-20 w-20 items-center justify-center rounded-full shadow-xl transition-all duration-300 ${
                phase === 'listening'
                  ? 'bg-yellow-400 text-black shadow-yellow-400/40 scale-105 ring-4 ring-yellow-300/40'
                  : 'bg-white/10 text-white hover:bg-white/20 active:scale-95 border border-white/20'
              }`}
              title="Bấm để nói lại"
            >
              <svg
                viewBox="0 0 24 24"
                className={`h-8 w-8 transition-transform duration-200 ${phase === 'listening' ? 'scale-110' : ''}`}
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" />
                <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
                <line x1="12" x2="12" y1="19" y2="22" />
              </svg>
            </button>
          </div>
          <span className="mt-3 text-xs font-medium text-white/70">
            {phase === 'listening'
              ? 'Đang lắng nghe câu lệnh...'
              : phase === 'processing'
              ? 'Đang phân tích lệnh...'
              : 'Bấm micro để bắt đầu nói'}
          </span>
          {activeMic && (
            <div className="mt-2 flex items-center gap-1.5 text-[11px] text-white/50 bg-white/5 px-2.5 py-0.5 rounded-full border border-white/5 max-w-[90%]">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 flex-shrink-0" />
              <span className="truncate">Mic: {activeMic}</span>
            </div>
          )}
        </div>

        {/* Recognized Transcript */}
        <div className="min-h-[3.2rem] flex items-center justify-center px-4 py-2 rounded-xl bg-white/5 border border-white/5 text-sm font-medium text-white">
          {transcript}
        </div>

        {/* Action result detail */}
        {detail && (
          <div className="mt-3 rounded-xl bg-white/10 p-3 text-xs font-medium text-emerald-300 border border-emerald-400/20 text-left leading-relaxed">
            {detail}
          </div>
        )}

        {/* Suggested Voice Commands */}
        <div className="mt-5 rounded-2xl bg-black/25 p-3.5 text-left border border-white/5">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[11px] font-semibold text-white/70 uppercase tracking-wide">
              Khẩu lệnh hỗ trợ
            </span>
            <span className="text-[10px] text-white/40">Tiếng Việt</span>
          </div>
          <div className="grid grid-cols-2 gap-1.5 text-[11px] text-white/80">
            <span className="rounded-lg bg-white/5 px-2.5 py-1 border border-white/5">Bật quạt / Tắt quạt</span>
            <span className="rounded-lg bg-white/5 px-2.5 py-1 border border-white/5">Quạt 40% / 70% / 100%</span>
            <span className="rounded-lg bg-white/5 px-2.5 py-1 border border-white/5">Chế độ tự động</span>
            <span className="rounded-lg bg-white/5 px-2.5 py-1 border border-white/5">Nhiệt độ phòng</span>
            <span className="rounded-lg bg-white/5 px-2.5 py-1 border border-white/5">Cảnh báo quá nhiệt</span>
            <span className="rounded-lg bg-white/5 px-2.5 py-1 border border-white/5">Tắt cảnh báo</span>
          </div>
        </div>

        {/* Footer controls */}
        <div className="mt-5 flex gap-2 justify-center">
          {phase === 'result' && (
            <button
              type="button"
              onClick={startListening}
              className="flex items-center gap-1.5 rounded-full bg-yellow-400 px-5 py-2 text-xs font-semibold text-black transition hover:bg-yellow-300 shadow-md"
            >
              <svg viewBox="0 0 24 24" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M3 12a9 9 0 0 1 15-6.7L21 8" />
                <path d="M21 3v5h-5" />
                <path d="M21 12a9 9 0 0 1-15 6.7L3 16" />
                <path d="M3 21v-5h5" />
              </svg>
              <span>Nói lại</span>
            </button>
          )}
          <button
            type="button"
            onClick={onClose}
            className="rounded-full bg-white/20 px-5 py-2 text-xs font-medium text-white transition hover:bg-white/30"
          >
            Đóng
          </button>
        </div>
      </div>
    </div>
  )
}
