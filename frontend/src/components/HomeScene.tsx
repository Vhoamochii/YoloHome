import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'

interface HomeSceneProps {
  className?: string
}

const LIGHTS_KEY = 'yolohome-lights'
const LIGHTS_EVENT = 'yolohome-lights'

function lightsAreOn() {
  try {
    return sessionStorage.getItem(LIGHTS_KEY) !== 'off'
  } catch {
    return true
  }
}

export default function HomeScene({ className = '' }: HomeSceneProps) {
  const sceneRef = useRef<HTMLDivElement>(null)
  const [lightsOn, setLightsOn] = useState(lightsAreOn)
  const [anchor, setAnchor] = useState<{ x: number; y: number } | null>(null)

  useEffect(() => {
    const sync = () => setLightsOn(lightsAreOn())
    window.addEventListener(LIGHTS_EVENT, sync)
    return () => window.removeEventListener(LIGHTS_EVENT, sync)
  }, [])

  useEffect(() => {
    const node = sceneRef.current
    if (!node) return

    const place = () => {
      const rect = node.getBoundingClientRect()
      if (rect.width < 8 || rect.height < 8) {
        setAnchor(null)
        return
      }
      const wide = rect.width >= 700
      setAnchor({
        x: rect.left + (wide ? rect.width * 0.045 : 18),
        y: rect.top + rect.height * (wide ? 0.38 : 0.34)
      })
    }

    place()
    const observer = new ResizeObserver(place)
    observer.observe(node)
    window.addEventListener('resize', place)
    return () => {
      observer.disconnect()
      window.removeEventListener('resize', place)
    }
  }, [])

  const toggleLights = () => {
    const next = !lightsAreOn()
    try {
      sessionStorage.setItem(LIGHTS_KEY, next ? 'on' : 'off')
    } catch {
      setLightsOn(next)
      return
    }
    window.dispatchEvent(new Event(LIGHTS_EVENT))
  }

  const switchButton = (
    <button
      type="button"
      className="home-scene__switch"
      style={anchor ? { left: anchor.x, top: anchor.y } : undefined}
      aria-pressed={lightsOn}
      aria-label={lightsOn ? 'Tắt đèn' : 'Bật đèn'}
      title={lightsOn ? 'Tắt đèn' : 'Bật đèn'}
      onClick={toggleLights}
    >
      <span className={`home-scene__switch-rocker ${lightsOn ? 'is-on' : ''}`} />
    </button>
  )

  return (
    <div ref={sceneRef} className={`home-scene ${lightsOn ? '' : 'is-dark'} ${className}`}>
      <div className="home-scene__photo" />
      <div className="home-scene__shade" />
      <div className="home-scene__glow home-scene__glow--warm" />
      <div className="home-scene__glow home-scene__glow--cool" />
      <div className="home-scene__beam" />
      <div className="home-scene__rays" aria-hidden="true">
        <span />
        <span />
        <span />
      </div>
      <div className="home-scene__lamp">
        <span className="home-scene__cord" />
        <span className="home-scene__bulb" />
      </div>
      <div className="home-scene__windows">
        <span />
        <span />
        <span />
      </div>
      <div className="home-scene__floor" />
      {anchor && createPortal(switchButton, document.body)}
    </div>
  )
}
