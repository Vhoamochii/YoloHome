import { useEffect, useState } from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend } from 'recharts'

export default function Dashboard() {
  const [sensorData, setSensorData] = useState({ temperature: 0, humidity: 0 })
  const [history, setHistory] = useState([])

  useEffect(() => {
    // TODO: Fetch sensor data
  }, [])

  return (
    <div className="p-6">
      <h1 className="text-3xl font-bold mb-6">Dashboard</h1>
      
      <div className="grid grid-cols-2 gap-4 mb-6">
        <div className="bg-white p-4 rounded shadow">
          <h3 className="text-lg font-semibold">Temperature</h3>
          <p className="text-3xl">{sensorData.temperature}°C</p>
        </div>
        <div className="bg-white p-4 rounded shadow">
          <h3 className="text-lg font-semibold">Humidity</h3>
          <p className="text-3xl">{sensorData.humidity}%</p>
        </div>
      </div>

      <div className="bg-white p-4 rounded shadow">
        <h3 className="text-lg font-semibold mb-4">24h History</h3>
        {/* TODO: Add LineChart */}
      </div>
    </div>
  )
}
