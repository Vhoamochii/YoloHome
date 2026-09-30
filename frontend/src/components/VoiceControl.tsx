import { useState } from 'react'

export default function VoiceControl() {
  const [isListening, setIsListening] = useState(false)

  const startVoiceRecognition = () => {
    const recognition = new (window as any).webkitSpeechRecognition()
    recognition.lang = 'vi-VN'
    
    recognition.onresult = (event: any) => {
      const transcript = event.results[0][0].transcript
      console.log('Voice command:', transcript)
      // TODO: Parse and send command
    }
    
    recognition.start()
    setIsListening(true)
  }

  return (
    <button
      onClick={startVoiceRecognition}
      className="fixed bottom-8 right-8 bg-blue-500 text-white p-4 rounded-full shadow-lg"
    >
      🎤
    </button>
  )
}
