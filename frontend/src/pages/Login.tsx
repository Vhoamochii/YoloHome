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
  const [faceLoginOpen, setFaceLoginOpen] = useState(false)
  const [faceRegisterOpen, setFaceRegisterOpen] = useState(false)
  const [busy, setBusy] = useState(false)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError('')
    setInfo('')
    try {
      const response =
        mode === 'login'
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
            {mode === 'login' ? (
              <>
                Welcome
                <br />
                back!
              </>
            ) : (
              'Create account'
            )}
          </h1>

          {mode === 'register' && (
            <label className="mt-8 block text-sm font-medium">
              Tên người dùng
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
            Mật khẩu
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="mt-1 w-full rounded-full border border-neutral-300 px-4 py-2 outline-none focus:border-black"
              placeholder="Nhập mật khẩu (tối thiểu 4 ký tự)"
              required
            />
          </label>

          {mode === 'login' && (
            <button
              type="button"
              onClick={() => setInfo('Liên hệ quản trị viên hoặc đăng nhập bằng Face ID.')}
              className="mt-2 block w-full text-right text-xs text-neutral-500"
            >
              Quên mật khẩu?
            </button>
          )}

          {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
          {info && <p className="mt-3 text-sm text-neutral-600">{info}</p>}

          <button
            disabled={busy}
            className="mt-4 w-full rounded-lg bg-black py-2.5 text-sm font-medium text-white transition hover:bg-neutral-800 disabled:opacity-60"
          >
            {busy ? 'Đang xử lý...' : mode === 'login' ? 'Đăng nhập' : 'Tạo tài khoản'}
          </button>

          {mode === 'login' ? (
            <>
              <p className="mt-4 text-center text-xs text-neutral-500">Chưa có tài khoản?</p>
              <button
                type="button"
                onClick={() => {
                  setMode('register')
                  setError('')
                  setInfo('')
                }}
                className="mt-2 w-full rounded-lg bg-neutral-200 py-2.5 text-sm font-medium hover:bg-neutral-300"
              >
                Tạo tài khoản mới
              </button>

              <div className="mt-4 flex flex-col gap-2 border-t border-neutral-200 pt-3">
                <button
                  type="button"
                  onClick={() => setFaceLoginOpen(true)}
                  className="flex w-full items-center justify-center gap-2 rounded-lg border border-neutral-800 py-2 text-sm font-medium text-neutral-900 transition hover:bg-neutral-100"
                >
                  <span>👤</span> Đăng nhập bằng khuôn mặt
                </button>
                <button
                  type="button"
                  onClick={() => setFaceRegisterOpen(true)}
                  className="w-full text-center text-xs text-neutral-500 hover:text-black"
                >
                  📸 Đăng ký Face ID cho tài khoản hiện có
                </button>
              </div>
            </>
          ) : (
            <>
              <button
                type="button"
                onClick={() => {
                  setMode('login')
                  setError('')
                  setInfo('')
                }}
                className="mt-4 w-full text-sm text-neutral-600 hover:text-black"
              >
                Đã có tài khoản? Đăng nhập
              </button>
            </>
          )}
        </form>
      </div>

      <div className="relative hidden flex-1 md:block">
        <HomeScene className="absolute inset-0" />
      </div>

      {/* Face Login Modal */}
      {faceLoginOpen && (
        <FaceCapture
          title="Đăng nhập bằng khuôn mặt"
          submitLabel="Xác thực Face ID"
          onClose={() => setFaceLoginOpen(false)}
          onSubmit={async (image) => {
            try {
              const response = await authAPI.faceLogin(image)
              saveSession(response.data)
              navigate('/')
            } catch (err) {
              throw new Error(errorMessage(err, 'Không nhận diện được khuôn mặt'))
            }
          }}
        />
      )}

      {/* Face Register Modal */}
      {faceRegisterOpen && (
        <FaceCapture
          title={`Đăng ký khuôn mặt cho ${email || 'tài khoản'}`}
          submitLabel="Lưu khuôn mặt vào DB"
          onClose={() => setFaceRegisterOpen(false)}
          onSubmit={async (image) => {
            if (!email) {
              throw new Error('Vui lòng nhập email trước khi đăng ký khuôn mặt!')
            }
            try {
              const res = await authAPI.registerFace(image, email)
              setInfo(res.data.message || 'Đã lưu khuôn mặt thành công!')
              setFaceRegisterOpen(false)
            } catch (err) {
              throw new Error(errorMessage(err, 'Không lưu được khuôn mặt'))
            }
          }}
        />
      )}
    </div>
  )
}
