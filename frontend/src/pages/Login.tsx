import { useState } from 'react'
import axios from 'axios'

export default function Login() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')

  const handleLogin = async () => {
    // TODO: Implement login
  }

  const handleFaceLogin = async () => {
    // TODO: Implement face recognition login
  }

  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="bg-white p-8 rounded shadow-md w-96">
        <h1 className="text-2xl font-bold mb-4">YoloHome Login</h1>
        <input
          type="email"
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="w-full p-2 mb-3 border rounded"
        />
        <input
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="w-full p-2 mb-3 border rounded"
        />
        <button onClick={handleLogin} className="w-full bg-blue-500 text-white p-2 rounded mb-2">
          Login
        </button>
        <button onClick={handleFaceLogin} className="w-full bg-green-500 text-white p-2 rounded">
          Face Login
        </button>
      </div>
    </div>
  )
}
