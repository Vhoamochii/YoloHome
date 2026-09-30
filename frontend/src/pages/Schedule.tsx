import { useState } from 'react'

export default function Schedule() {
  const [schedules, setSchedules] = useState([])

  const createSchedule = () => {
    // TODO: Create new schedule
  }

  return (
    <div className="p-6">
      <h1 className="text-3xl font-bold mb-6">Schedule</h1>
      
      <button 
        onClick={createSchedule}
        className="bg-blue-500 text-white px-4 py-2 rounded mb-4"
      >
        Add Schedule
      </button>

      <div className="bg-white rounded shadow">
        {/* TODO: Display schedules */}
      </div>
    </div>
  )
}
