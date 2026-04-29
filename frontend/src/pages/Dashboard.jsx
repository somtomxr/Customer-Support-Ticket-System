import { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { getTickets, getTicketStats, assignTicket } from '../services/api'
import { StatusBadge, PriorityBadge } from '../components/Badges'
import toast from 'react-hot-toast'
import {
  HiOutlinePlus, HiOutlineSearch, HiOutlineFilter,
  HiOutlineClipboardList, HiOutlineClock, HiOutlineCheckCircle,
  HiOutlineExclamation, HiOutlineChat
} from 'react-icons/hi'

export default function Dashboard() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [tickets, setTickets] = useState([])
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [filters, setFilters] = useState({ status: '', priority: '', search: '' })

  useEffect(() => {
    fetchData()
  }, [filters.status, filters.priority])

  const fetchData = async () => {
    try {
      const params = {}
      if (filters.status) params.status = filters.status
      if (filters.priority) params.priority = filters.priority
      if (filters.search) params.search = filters.search

      const [ticketRes, statsRes] = await Promise.all([
        getTickets(params),
        getTicketStats(),
      ])
      setTickets(ticketRes.data)
      setStats(statsRes.data)
    } catch (err) {
      toast.error('Failed to load dashboard data')
    } finally {
      setLoading(false)
    }
  }

  const handleSearch = (e) => {
    e.preventDefault()
    fetchData()
  }

  const handleAssignToMe = async (ticketId) => {
    try {
      await assignTicket(ticketId, { agent_id: user.id })
      toast.success('Ticket assigned to you')
      fetchData()
    } catch (err) {
      toast.error('Failed to assign ticket')
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-primary-600"></div>
      </div>
    )
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-8">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            {user.role === 'agent' ? 'Agent Dashboard' : 'My Tickets'}
          </h1>
          <p className="text-gray-500 mt-1">
            {user.role === 'agent'
              ? 'Manage and resolve customer support tickets'
              : 'Track your support requests'}
          </p>
        </div>
        <Link
          to="/tickets/new"
          className="inline-flex items-center gap-2 bg-primary-600 text-white px-4 py-2.5 rounded-lg font-medium hover:bg-primary-700 transition shadow-sm"
        >
          <HiOutlinePlus className="w-5 h-5" />
          New Ticket
        </Link>
      </div>

      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          <StatCard
            icon={<HiOutlineClipboardList className="w-6 h-6" />}
            label="Total"
            value={stats.total_tickets}
            color="bg-gray-100 text-gray-600"
          />
          <StatCard
            icon={<HiOutlineExclamation className="w-6 h-6" />}
            label="Open"
            value={stats.open_tickets}
            color="bg-yellow-100 text-yellow-600"
          />
          <StatCard
            icon={<HiOutlineClock className="w-6 h-6" />}
            label="In Progress"
            value={stats.in_progress_tickets}
            color="bg-blue-100 text-blue-600"
          />
          <StatCard
            icon={<HiOutlineCheckCircle className="w-6 h-6" />}
            label="Resolved"
            value={stats.resolved_tickets}
            color="bg-green-100 text-green-600"
          />
        </div>
      )}

      {/* Filters */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm mb-6">
        <div className="p-4 flex flex-col sm:flex-row gap-3">
          <form onSubmit={handleSearch} className="flex-1 relative">
            <HiOutlineSearch className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 w-5 h-5" />
            <input
              type="text"
              placeholder="Search tickets..."
              value={filters.search}
              onChange={(e) => setFilters({ ...filters, search: e.target.value })}
              className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 outline-none transition text-sm"
            />
          </form>
          <div className="flex gap-3">
            <select
              value={filters.status}
              onChange={(e) => setFilters({ ...filters, status: e.target.value })}
              className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary-500 outline-none"
            >
              <option value="">All Status</option>
              <option value="open">Open</option>
              <option value="in_progress">In Progress</option>
              <option value="resolved">Resolved</option>
            </select>
            <select
              value={filters.priority}
              onChange={(e) => setFilters({ ...filters, priority: e.target.value })}
              className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary-500 outline-none"
            >
              <option value="">All Priority</option>
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
              <option value="urgent">Urgent</option>
            </select>
          </div>
        </div>
      </div>

      {/* Ticket List */}
      <div className="space-y-3">
        {tickets.length === 0 ? (
          <div className="bg-white rounded-xl border border-gray-200 p-12 text-center">
            <HiOutlineClipboardList className="w-12 h-12 text-gray-300 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-1">No tickets found</h3>
            <p className="text-gray-500 mb-4">
              {filters.status || filters.priority || filters.search
                ? 'Try adjusting your filters'
                : 'Create your first support ticket to get started'}
            </p>
            {!filters.status && !filters.priority && (
              <Link
                to="/tickets/new"
                className="inline-flex items-center gap-2 bg-primary-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-primary-700 transition"
              >
                <HiOutlinePlus className="w-4 h-4" />
                Create Ticket
              </Link>
            )}
          </div>
        ) : (
          tickets.map((ticket) => (
            <div
              key={ticket.id}
              className="bg-white rounded-xl border border-gray-200 p-5 hover:shadow-md transition cursor-pointer group"
              onClick={() => navigate(`/tickets/${ticket.id}`)}
            >
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs text-gray-400 font-mono">#{ticket.id}</span>
                    <StatusBadge status={ticket.status} />
                    <PriorityBadge priority={ticket.priority} />
                  </div>
                  <h3 className="font-medium text-gray-900 group-hover:text-primary-600 transition truncate">
                    {ticket.title}
                  </h3>
                  <div className="flex items-center gap-4 mt-2 text-xs text-gray-500">
                    {ticket.customer_name && (
                      <span>By: {ticket.customer_name}</span>
                    )}
                    {ticket.agent_name && (
                      <span>Agent: {ticket.agent_name}</span>
                    )}
                    {ticket.category_name && (
                      <span className="bg-gray-100 px-2 py-0.5 rounded">{ticket.category_name}</span>
                    )}
                    <span className="flex items-center gap-1">
                      <HiOutlineChat className="w-3.5 h-3.5" />
                      {ticket.comment_count}
                    </span>
                    <span>{new Date(ticket.created_at).toLocaleDateString()}</span>
                  </div>
                </div>

                {/* Assign to me button (agents only, unassigned tickets) */}
                {user.role === 'agent' && !ticket.agent_id && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      handleAssignToMe(ticket.id)
                    }}
                    className="text-xs bg-primary-50 text-primary-600 px-3 py-1.5 rounded-lg font-medium hover:bg-primary-100 transition whitespace-nowrap"
                  >
                    Assign to me
                  </button>
                )}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}

function StatCard({ icon, label, value, color }) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
      <div className="flex items-center gap-3">
        <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${color}`}>
          {icon}
        </div>
        <div>
          <p className="text-2xl font-bold text-gray-900">{value}</p>
          <p className="text-xs text-gray-500">{label}</p>
        </div>
      </div>
    </div>
  )
}
