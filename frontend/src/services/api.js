import axios from 'axios'

const API_BASE = import.meta.env.VITE_API_URL || ''

const api = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
})

// Attach JWT token to every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Handle 401 globally (token expired)
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

// ── Auth ───────────────────────────────────────────
export const loginUser = (data) => api.post('/api/auth/login', data)
export const registerUser = (data) => api.post('/api/auth/register', data)
export const getMe = () => api.get('/api/auth/me')

// ── Tickets ────────────────────────────────────────
export const getTickets = (params) => api.get('/api/tickets/', { params })
export const getTicket = (id) => api.get(`/api/tickets/${id}`)
export const createTicket = (data) => api.post('/api/tickets/', data)
export const updateTicket = (id, data) => api.put(`/api/tickets/${id}`, data)
export const updateTicketStatus = (id, data) => api.patch(`/api/tickets/${id}/status`, data)
export const assignTicket = (id, data) => api.patch(`/api/tickets/${id}/assign`, data)
export const getTicketStats = () => api.get('/api/tickets/stats')

// ── Comments ───────────────────────────────────────
export const getComments = (ticketId) => api.get(`/api/tickets/${ticketId}/comments`)
export const addComment = (ticketId, data) => api.post(`/api/tickets/${ticketId}/comments`, data)

// ── Categories ─────────────────────────────────────
export const getCategories = () => api.get('/api/categories/')

// ── Users ──────────────────────────────────────────
export const getAgents = () => api.get('/api/users/agents')

// ── AI ─────────────────────────────────────────────
export const getAISuggestion = (data) => api.post('/api/ai/suggest-reply', data)

export default api
