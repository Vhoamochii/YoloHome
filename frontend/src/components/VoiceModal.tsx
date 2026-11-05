import { useEffect, useState } from 'react'
import { deviceAPI, Device, errorMessage } from '../services/api'

interface VoiceModalProps {
  devices: Device[]
  onDone: () => void
  onClose: () => void
}

type Phase = 'ready' | 'listening' | 'result'

interface SpeechEvent {
  results: ArrayLike<ArrayLike<{ transcript: string }>>
}

interface SpeechRecognizer {
  lang: string
  onresult: ((event: SpeechEvent) => void) | null
  onerror: (() => void) | null
  onend: (() => void) | null
  start: () => void
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

export default function VoiceModal({ devices, onDone, onClose }: VoiceModalProps) {
  const [phase, setPhase] = useState<Phase>('ready')
  const [transcript, setTranscript] = useState('Hãy nói một lệnh')
  const [detail, setDetail] = useState('')

  useEffect(() => {
    const recognizer = getRecognizer()
    if (!recognizer) {
      setPhase('result')
      setTranscript('Trình duyệt không hỗ trợ nhận giọng nói')
      return
    }

    recognizer.lang = 'vi-VN'
    recognizer.onresult = (event) => {
      const text = event.results[0][0].transcript
      setTranscript(text)
      void runCommand(text)
    }
    recognizer.onerror = () => {
      setPhase('result')
      setTranscript('Không nghe rõ. Thử lại.')
    }
    recognizer.onend = () => {
      setPhase((current) => (current === 'listening' ? 'result' : current))
    }

    const timer = window.setTimeout(() => {
      try {
        recognizer.start()
        setPhase('listening')
      } catch {
        setPhase('result')
        setTranscript('Không bật được micro')
      }
    }, 250)

    return () => window.clearTimeout(timer)
  }, [devices])

  const runCommand = async (text: string) => {
    const command = text.toLowerCase()
    const fan = findDevice(devices, 'fan')
    const led = findDevice(devices, 'led')
    try {
      if (command.includes('tắt quạt') && fan) {
        await deviceAPI.control(fan.id, 'off')
        setDetail('Đã tắt quạt')
      } else if (command.includes('bật quạt') && fan) {
        await deviceAPI.control(fan.id, 'on')
        setDetail('Đã bật quạt')
      } else if (command.includes('tắt đèn') && led) {
        await deviceAPI.control(led.id, 'off')
        setDetail('Đã tắt đèn')
      } else if (command.includes('bật đèn') && led) {
        await deviceAPI.control(led.id, 'on')
        setDetail('Đã bật đèn')
      } else if (led && command.includes('đỏ')) {
        await deviceAPI.control(led.id, 'set_color', { color: 'FF0000' })
        setDetail('Đã đổi đèn sang đỏ')
      } else if (led && command.includes('xanh dương')) {
        await deviceAPI.control(led.id, 'set_color', { color: '0000FF' })
        setDetail('Đã đổi đèn sang xanh dương')
      } else if (led && (command.includes('xanh lá') || command.includes('xanh'))) {
        await deviceAPI.control(led.id, 'set_color', { color: '00FF00' })
        setDetail('Đã đổi đèn sang xanh')
      } else if (led && command.includes('vàng')) {
        await deviceAPI.control(led.id, 'set_color', { color: 'FFFF00' })
        setDetail('Đã đổi đèn sang vàng')
      } else {
        setDetail('Chưa nhận ra lệnh. Thử "bật quạt" hoặc "tắt đèn".')
        setPhase('result')
        return
      }
      setPhase('result')
      onDone()
    } catch (error) {
      setDetail(errorMessage(error, 'Không gửi được lệnh'))
      setPhase('result')
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-6">
      <div className="glass w-full max-w-lg rounded-[28px] p-8 text-center text-white">
        <h2 className="text-2xl font-semibold">Điều khiển bằng giọng nói</h2>
        <p className="mt-2 text-sm text-white/75">
          {phase === 'ready' && 'Sẵn sàng'}
          {phase === 'listening' && 'Đang nghe...'}
          {phase === 'result' && 'Kết quả'}
        </p>

        <div className="mx-auto mt-8 flex h-24 w-24 items-center justify-center rounded-full bg-white/15">
          {phase === 'result' && detail.startsWith('Đã') ? (
            <span className="text-4xl text-yellow-300">✓</span>
          ) : (
            <svg viewBox="0 0 24 24" className="h-10 w-10 fill-white">
              <path d="M12 14a3 3 0 0 0 3-3V6a3 3 0 1 0-6 0v5a3 3 0 0 0 3 3zm5-3a5 5 0 0 1-10 0H5a7 7 0 0 0 6 6.92V21h2v-3.08A7 7 0 0 0 19 11h-2z" />
            </svg>
          )}
        </div>

        <p className="mt-6 text-lg font-medium">"{transcript}"</p>
        {detail && <p className="mt-2 text-sm text-white/80">{detail}</p>}

        <button onClick={onClose} className="mt-8 rounded-full bg-white px-6 py-2 text-sm font-semibold text-black">
          Đóng
        </button>
      </div>
    </div>
  )
}
