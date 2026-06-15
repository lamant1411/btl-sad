import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { authAPI } from '../services/api'
import { useAuthStore } from '../store'
import toast from 'react-hot-toast'

export function LoginPage() {
  const [form, setForm]     = useState({ username: '', password: '' })
  const [loading, setLoading] = useState(false)
  const { login }           = useAuthStore()
  const navigate            = useNavigate()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    try {
      const { data } = await authAPI.login(form)
      login(data.user, data.access, data.refresh)
      toast.success('👋 Chào mừng trở lại!')
      navigate('/')
    } catch (err) {
      const msg = err.response?.data?.non_field_errors?.[0] || 'Đăng nhập thất bại'
      toast.error(msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="auth-page">
      <div className="card auth-card fade-in">
        <div style={{ textAlign:'center', marginBottom:28 }}>
          <div style={{ fontSize:48, marginBottom:8 }}>🛍️</div>
          <h1 className="auth-title">Đăng nhập</h1>
          <p className="auth-sub">Chào mừng trở lại EcomAI!</p>
        </div>
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label" htmlFor="username">Tên đăng nhập</label>
            <input
              id="username"
              className="input"
              type="text"
              placeholder="Nhập tên đăng nhập..."
              value={form.username}
              onChange={e => setForm({...form, username: e.target.value})}
              required
            />
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="password">Mật khẩu</label>
            <input
              id="password"
              className="input"
              type="password"
              placeholder="••••••••"
              value={form.password}
              onChange={e => setForm({...form, password: e.target.value})}
              required
            />
          </div>
          <button id="login-btn" type="submit" className="btn btn-primary" style={{ width:'100%', justifyContent:'center', marginTop:8 }} disabled={loading}>
            {loading ? '⏳ Đang đăng nhập...' : '🚀 Đăng nhập'}
          </button>
        </form>
        <p style={{ textAlign:'center', marginTop:20, fontSize:14, color:'var(--text-muted)' }}>
          Chưa có tài khoản? <Link to="/register" style={{ color:'var(--primary)', fontWeight:600 }}>Đăng ký ngay</Link>
        </p>
      </div>
    </div>
  )
}

export function RegisterPage() {
  const [form, setForm]     = useState({ username:'', email:'', full_name:'', password:'', password2:'' })
  const [loading, setLoading] = useState(false)
  const { login }           = useAuthStore()
  const navigate            = useNavigate()

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (form.password !== form.password2) { toast.error('Mật khẩu không khớp'); return }
    setLoading(true)
    try {
      const { data } = await authAPI.register(form)
      login(data.user, data.access, data.refresh)
      toast.success('🎉 Đăng ký thành công! Giỏ hàng đã được tạo.')
      navigate('/')
    } catch (err) {
      const errors = err.response?.data
      const msg    = typeof errors === 'object' ? Object.values(errors).flat()[0] : 'Đăng ký thất bại'
      toast.error(msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="auth-page">
      <div className="card auth-card fade-in">
        <div style={{ textAlign:'center', marginBottom:28 }}>
          <div style={{ fontSize:48, marginBottom:8 }}>✨</div>
          <h1 className="auth-title">Đăng ký</h1>
          <p className="auth-sub">Tạo tài khoản để trải nghiệm mua sắm AI</p>
        </div>
        <form onSubmit={handleSubmit}>
          {[
            { id:'full_name', label:'Họ và tên',       type:'text',     ph:'Nguyễn Văn A' },
            { id:'username',  label:'Tên đăng nhập',   type:'text',     ph:'nguyenvana' },
            { id:'email',     label:'Email',            type:'email',    ph:'abc@example.com' },
            { id:'password',  label:'Mật khẩu',        type:'password', ph:'••••••••' },
            { id:'password2', label:'Xác nhận mật khẩu', type:'password', ph:'••••••••' },
          ].map(f => (
            <div key={f.id} className="form-group">
              <label className="form-label" htmlFor={f.id}>{f.label}</label>
              <input
                id={f.id}
                className="input"
                type={f.type}
                placeholder={f.ph}
                value={form[f.id]}
                onChange={e => setForm({...form, [f.id]: e.target.value})}
                required
              />
            </div>
          ))}
          <button id="register-btn" type="submit" className="btn btn-primary" style={{ width:'100%', justifyContent:'center', marginTop:8 }} disabled={loading}>
            {loading ? '⏳ Đang tạo tài khoản...' : '🎉 Đăng ký'}
          </button>
        </form>
        <p style={{ textAlign:'center', marginTop:20, fontSize:14, color:'var(--text-muted)' }}>
          Đã có tài khoản? <Link to="/login" style={{ color:'var(--primary)', fontWeight:600 }}>Đăng nhập</Link>
        </p>
      </div>
    </div>
  )
}
