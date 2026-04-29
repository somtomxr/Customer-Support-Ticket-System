import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { loginUser, getMe } from '../services/api'
import toast from 'react-hot-toast'
import { HiOutlineTicket, HiOutlineMail, HiOutlineLockClosed } from 'react-icons/hi'

export default function Login() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const { login } = useAuth()
  const navigate = useNavigate()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)

    try {
      const res = await loginUser({ email, password })
      const { access_token } = res.data

      // Set token first, then fetch user profile
      localStorage.setItem('token', access_token)
      const userRes = await getMe()
      login(access_token, userRes.data)
      toast.success(`Welcome back, ${userRes.data.name}!`)
      navigate('/dashboard')
    } catch (err) {
      const msg = err.response?.data?.detail || 'Login failed. Please try again.'
      toast.error(msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex">
      {/* Left panel - branding */}
      <div className="hidden lg:flex lg:w-1/2 bg-gradient-to-br from-primary-600 to-primary-800 text-white p-12 flex-col justify-between">
        <div>
          <div className="flex items-center gap-3 mb-8">
            <div className="w-10 h-10 bg-white/20 rounded-xl flex items-center justify-center">
              <HiOutlineTicket className="w-6 h-6" />
            </div>
            <span className="text-2xl font-bold">SupportDesk</span>
          </div>
          <h1 className="text-4xl font-bold leading-tight mb-4">
            Streamline Your Customer Support
          </h1>
          <p className="text-lg text-primary-100 leading-relaxed">
            Manage tickets, collaborate with your team, and resolve customer issues faster 
            with our intelligent support platform.
          </p>
        </div>
        <div className="space-y-4">
          <div className="flex items-center gap-3 text-primary-100">
            <div className="w-8 h-8 bg-white/10 rounded-lg flex items-center justify-center text-sm">✓</div>
            <span>Role-based access for Customers & Agents</span>
          </div>
          <div className="flex items-center gap-3 text-primary-100">
            <div className="w-8 h-8 bg-white/10 rounded-lg flex items-center justify-center text-sm">✓</div>
            <span>Complete ticket lifecycle management</span>
          </div>
          <div className="flex items-center gap-3 text-primary-100">
            <div className="w-8 h-8 bg-white/10 rounded-lg flex items-center justify-center text-sm">✓</div>
            <span>AI-powered reply suggestions</span>
          </div>
        </div>
      </div>

      {/* Right panel - login form */}
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="w-full max-w-md">
          <div className="lg:hidden flex items-center gap-3 mb-8 justify-center">
            <div className="w-10 h-10 bg-primary-600 rounded-xl flex items-center justify-center">
              <HiOutlineTicket className="w-6 h-6 text-white" />
            </div>
            <span className="text-2xl font-bold text-gray-900">SupportDesk</span>
          </div>

          <h2 className="text-2xl font-bold text-gray-900 mb-1">Welcome back</h2>
          <p className="text-gray-500 mb-8">Sign in to your account to continue</p>

          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">Email</label>
              <div className="relative">
                <HiOutlineMail className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 w-5 h-5" />
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  placeholder="you@example.com"
                  className="w-full pl-10 pr-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 outline-none transition"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">Password</label>
              <div className="relative">
                <HiOutlineLockClosed className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 w-5 h-5" />
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  placeholder="••••••••"
                  className="w-full pl-10 pr-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 outline-none transition"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-primary-600 text-white py-2.5 rounded-lg font-medium hover:bg-primary-700 focus:ring-4 focus:ring-primary-200 transition disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Signing in...' : 'Sign In'}
            </button>
          </form>

          <p className="mt-6 text-center text-sm text-gray-500">
            Don&apos;t have an account?{' '}
            <Link to="/register" className="text-primary-600 font-medium hover:underline">
              Create one
            </Link>
          </p>

          {/* Demo credentials */}
          <div className="mt-8 p-4 bg-gray-50 rounded-lg border border-gray-200">
            <p className="text-xs font-medium text-gray-500 mb-2">Demo Accounts</p>
            <div className="space-y-1 text-xs text-gray-600">
              <p><span className="font-medium">Customer:</span> rahul@example.com / password123</p>
              <p><span className="font-medium">Agent:</span> som@support.com / password123</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
