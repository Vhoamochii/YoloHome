import { FormEvent, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import FaceCapture from '../components/FaceCapture'
import HomeScene from '../components/HomeScene'
import { authAPI, errorMessage, saveSession } from '../services/api'

export default function Login() {
  const navigate = useNavigate()
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [email, setEmail] = useState('admin@yolohome.local')
  const [password, setPassword] = useState('')
  const [name, setName] = useState('')
  const [error, setError] = useState('')
  const [info, setInfo] = useState('')
  const [faceOpen, setFaceOpen] = useState(false)
  const [busy, setBusy] = useState(false)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      const response = mode === 'login'
        ? await authAPI.login(email, password)
        : await authAPI.register(email, password, name)
      saveSession(response.data)
      navigate('/')
    } catch (err) {
      setError(errorMessage(err, mode === 'login' ? 'Đăng nhập thất bại' : 'Không tạo được tài khoản'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex min-h-screen flex-col bg-white text-neutral-900 md:flex-row">
      <div className="relative h-44 shrink-0 md:hidden">
        <HomeScene className="absolute inset-0" />
      </div>
      <div className="flex w-full flex-1 items-center justify-center px-8 py-12 md:w-[46%] md:flex-none">
        <form onSubmit={submit} className="w-full max-w-sm">
          <h1 className="serif text-5xl font-semibold leading-tight">
            {mode === 'login' ? <>Welcome<br />back!</> : 'Create account'}
          </h1>

          {mode === 'register' && (
            <label className="mt-8 block text-sm font-medium">
              Name
              <input
                value={name}
                onChange={(event) => setName(event.target.value)}
                className="mt-1 w-full rounded-full border border-neutral-300 px-4 py-2 outline-none focus:border-black"
                placeholder="Tên của bạn"
              />
            </label>
          )}

          <label className="mt-6 block text-sm font-medium">
            Email
            <input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className="mt-1 w-full rounded-full border border-neutral-300 px-4 py-2 outline-none focus:border-black"
              placeholder="yolohome@gmail.com"
              required
            />
          </label>

          <label className="mt-4 block text-sm font-medium">
            Password
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="mt-1 w-full rounded-full border border-neutral-300 px-4 py-2 outline-none focus:border-black"
              placeholder="Enter your password"
              required
            />
          </label>

          {mode === 'login' && (
            <button
              type="button"
              onClick={() => setInfo('Liên hệ quản trị viên để đặt lại mật khẩu.')}
              className="mt-2 block w-full text-right text-xs text-neutral-500"
            >
              Forgot your password?
            </button>
          )}

          {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
          {info && <p className="mt-3 text-sm text-neutral-600">{info}</p>}

          <button
            disabled={busy}
            className="mt-4 w-full rounded-lg bg-black py-2.5 text-sm font-medium text-white disabled:opacity-60"
          >
            {busy ? 'Đang xử lý...' : mode === 'login' ? 'Login' : 'Create account'}
          </button>

          {mode === 'login' ? (
            <>
              <p className="mt-4 text-center text-xs text-neutral-500">Don't have an account?</p>
              <button
                type="button"
                onClick={() => { setMode('register'); setError(''); setInfo('') }}
                className="mt-2 w-full rounded-lg bg-neutral-200 py-2.5 text-sm"
              >
                Create account
              </button>
              <button
                type="button"
                onClick={() => setFaceOpen(true)}
                className="mt-3 w-full text-sm text-neutral-700 underline"
              >
                Nhận diện khuôn mặt
              </button>
            </>
          ) : (
            <button
              type="button"
              onClick={() => { setMode('login'); setError('') }}
              className="mt-4 w-full text-sm text-neutral-600"
            >
              Đã có tài khoản? Đăng nhập
            </button>
          )}
        </form>
      </div>

      <div className="relative hidden flex-1 md:block">
        <HomeScene className="absolute inset-0" />
      </div>

      {faceOpen && (
        <FaceCapture
          title="Nhận diện khuôn mặt"
          submitLabel="Xác thực"
          onClose={() => setFaceOpen(false)}
          onSubmit={async (image) => {
            try {
              const response = await authAPI.faceLogin(image)
              saveSession(response.data)
              navigate('/')
            } catch (err) {
              throw new Error(errorMessage(err, 'Không nhận diện được'))
            }
          }}
        />
      )}
    </div>
  )
}
