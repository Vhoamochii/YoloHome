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
  abort: () => void
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
    recognizer.onresult = (event: SpeechEvent) => {
      const phrase = event.results[0]?.[0]?.transcript || ''
      setTranscript(phrase)
      executeCommand(phrase)
    }

    recognizer.onerror = () => {
      setPhase('result')
      setDetail('Lỗi mic hoặc quyền truy cập bị chặn.')
    }

    recognizer.onend = () => {
      setPhase((prev) => (prev === 'listening' ? 'result' : prev))
    }

    setPhase('listening')
    try {
      recognizer.start()
    } catch {
      setPhase('result')
      setDetail('Không khởi động được micro.')
    }
    return () => {
      // Closing the dialog must not run a command that is still being recognised.
      recognizer.onresult = null
      recognizer.abort()
    }
  }, [])

  const executeCommand = async (phrase: string) => {
    const command = phrase.toLowerCase()
    const fan = findDevice(devices, 'fan')
    const led = findDevice(devices, 'led')
    const voice = { actor: 'VOICE' as const }
    const sendTo = async (device: Device, action: string, done: string) => {
      const { data } = await deviceAPI.control(device.id, action, voice)
      setDetail(data.mqtt_sent ? done : data.message)
    }
    try {
      if (command.includes('tắt quạt') && fan) {
        await sendTo(fan, 'off', 'Đã gửi lệnh tắt quạt')
      } else if (command.includes('bật quạt') && fan) {
        await sendTo(fan, 'on', 'Đã gửi lệnh bật quạt')
      } else if (led && (command.includes('tắt cảnh báo') || command.includes('tắt báo động') || command.includes('an toàn') || command.includes('tắt đèn') || command.includes('xanh'))) {
        // Must come before the "cảnh báo" test below: "tắt cảnh báo" contains those words.
        await sendTo(led, 'safe', 'Đã gửi lệnh chuyển đèn về an toàn')
      } else if (led && (command.includes('cảnh báo') || command.includes('báo động') || command.includes('đỏ') || command.includes('bật đèn'))) {
        await sendTo(led, 'alert', 'Đã gửi lệnh bật đèn cảnh báo')
      } else {
        setDetail('Chưa nhận ra lệnh. Thử "bật quạt", "tắt quạt", hoặc "cảnh báo quá nhiệt".')
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
      <div className="glass w-full max-w-sm rounded-[28px] p-6 text-center text-white">
        <h2 className="text-xl font-semibold">Điều khiển bằng giọng nói</h2>
        <div className="my-6 flex justify-center">
          <div
            className={`flex h-20 w-20 items-center justify-center rounded-full bg-white/20 text-3xl shadow-lg transition ${
              phase === 'listening' ? 'animate-pulse ring-4 ring-yellow-400' : ''
            }`}
          >
            🎤
          </div>
        </div>
        <p className="text-base font-medium">{transcript}</p>
        {detail && <p className="mt-2 text-xs text-white/70">{detail}</p>}
        <button onClick={onClose} className="mt-6 rounded-full bg-white px-6 py-2 text-sm font-medium text-black">
          Đóng
        </button>
      </div>
    </div>
  )
}
