import { useEffect, useState } from 'react'

export default function Devices() {
  const [devices, setDevices] = useState([])

  const handleDeviceControl = (deviceId: number, action: string) => {
    // TODO: Send control command via API
  }

  return (
    <div className="p-6">
      <h1 className="text-3xl font-bold mb-6">Devices</h1>
      
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* TODO: Map devices */}
      </div>
    </div>
  )
}
