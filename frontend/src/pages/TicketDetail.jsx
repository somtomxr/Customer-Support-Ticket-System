import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import {
  getTicket, updateTicketStatus, assignTicket,
  addComment, getAISuggestion, getAgents
} from '../services/api'
import { StatusBadge, PriorityBadge } from '../components/Badges'
import SimilarTickets from '../components/SimilarTickets'
import toast from 'react-hot-toast'
import {
  HiOutlineArrowLeft, HiOutlineUser, HiOutlineClock,
  HiOutlineLightningBolt, HiOutlineChat, HiOutlineSparkles
} from 'react-icons/hi'

export default function TicketDetail() {
  const { id } = useParams()
  const { user } = useAuth()
  const navigate = useNavigate()
  const [ticket, setTicket] = useState(null)
  const [loading, setLoading] = useState(true)
  const [comment, setComment] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [aiLoading, setAiLoading] = useState(false)
  const [agents, setAgents] = useState([])
  const [showAssign, setShowAssign] = useState(false)

  useEffect(() => {
    fetchTicket()
    if (user.role === 'agent') {
      getAgents().then((res) => setAgents(res.data)).catch(() => {})
    }
  }, [id])

  const fetchTicket = async () => {
    try {
      const res = await getTicket(id)
      setTicket(res.data)
    } catch (err) {
      toast.error('Ticket not found')
      navigate('/dashboard')
    } finally {
      setLoading(false)
    }
  }

  const handleStatusChange = async (newStatus) => {
    try {
      await updateTicketStatus(id, { status: newStatus })
      toast.success(`Status updated to ${newStatus.replace('_', ' ')}`)
      fetchTicket()
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to update status')
    }
  }

  const handleAssign = async (agentId) => {
    try {
      await assignTicket(id, { agent_id: agentId })
      toast.success('Ticket assigned')
      setShowAssign(false)
      fetchTicket()
    } catch (err) {
      toast.error('Failed to assign ticket')
    }
  }

  const handleCommentSubmit = async (e) => {
    e.preventDefault()
    if (!comment.trim()) return
    setSubmitting(true)

    try {
      await addComment(id, { content: comment })
      setComment('')
      toast.success('Comment added')
      fetchTicket()
    } catch (err) {
      toast.error('Failed to add comment')
    } finally {
      setSubmitting(false)
    }
  }

  const handleAISuggest = async () => {
    setAiLoading(true)
    try {
      const res = await getAISuggestion({ ticket_id: parseInt(id) })
      setComment(res.data.suggestion)
      toast.success(`Suggestion generated (${res.data.method})`)
    } catch (err) {
      toast.error('Failed to generate suggestion')
    } finally {
      setAiLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-primary-600"></div>
      </div>
    )
  }

  if (!ticket) return null

  const statusActions = {
    open: [{ label: 'Start Progress', value: 'in_progress', color: 'bg-blue-600 hover:bg-blue-700' }, { label: 'Resolve', value: 'resolved', color: 'bg-green-600 hover:bg-green-700' }],
    in_progress: [{ label: 'Reopen', value: 'open', color: 'bg-yellow-600 hover:bg-yellow-700' }, { label: 'Resolve', value: 'resolved', color: 'bg-green-600 hover:bg-green-700' }],
    resolved: [{ label: 'Reopen', value: 'open', color: 'bg-yellow-600 hover:bg-yellow-700' }],
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <button
        onClick={() => navigate('/dashboard')}
        className="flex items-center gap-2 text-gray-500 hover:text-gray-700 mb-6 text-sm"
      >
        <HiOutlineArrowLeft className="w-4 h-4" />
        Back to Dashboard
      </button>

      {/* 3-column grid: main | details sidebar | similar tickets */}
      <div className="grid grid-cols-1 lg:grid-cols-8 gap-5">
        {/* ── Col 1: Main Content (4/8) ── */}
        <div className="lg:col-span-4 space-y-6">
          {/* Ticket Header */}
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
            <div className="flex items-center gap-2 mb-3">
              <span className="text-sm text-gray-400 font-mono">#{ticket.id}</span>
              <StatusBadge status={ticket.status} />
              <PriorityBadge priority={ticket.priority} />
            </div>
            <h1 className="text-xl font-bold text-gray-900 mb-4">{ticket.title}</h1>
            <p className="text-gray-700 whitespace-pre-wrap leading-relaxed">{ticket.description}</p>
            <div className="flex items-center gap-4 mt-4 pt-4 border-t border-gray-100 text-sm text-gray-500">
              <span className="flex items-center gap-1">
                <HiOutlineUser className="w-4 h-4" />
                {ticket.customer_name}
              </span>
              <span className="flex items-center gap-1">
                <HiOutlineClock className="w-4 h-4" />
                {new Date(ticket.created_at).toLocaleString()}
              </span>
              {ticket.category_name && (
                <span className="bg-gray-100 px-2 py-0.5 rounded text-xs">{ticket.category_name}</span>
              )}
            </div>
          </div>

          {/* Comments */}
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm">
            <div className="p-4 border-b border-gray-200">
              <h2 className="font-semibold text-gray-900 flex items-center gap-2">
                <HiOutlineChat className="w-5 h-5" />
                Comments ({ticket.comments?.length || 0})
              </h2>
            </div>

            <div className="divide-y divide-gray-100">
              {ticket.comments?.length === 0 && (
                <div className="p-8 text-center text-gray-400 text-sm">
                  No comments yet. Be the first to respond.
                </div>
              )}
              {ticket.comments?.map((c) => (
                <div key={c.id} className="p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-medium ${
                      c.author_role === 'agent'
                        ? 'bg-primary-100 text-primary-700'
                        : 'bg-gray-100 text-gray-600'
                    }`}>
                      {c.author_name?.[0]?.toUpperCase() || '?'}
                    </div>
                    <span className="font-medium text-sm text-gray-900">{c.author_name}</span>
                    <span className="text-xs text-gray-400 capitalize">({c.author_role})</span>
                    {c.is_ai_generated && (
                      <span className="text-xs bg-purple-100 text-purple-700 px-1.5 py-0.5 rounded flex items-center gap-1">
                        <HiOutlineSparkles className="w-3 h-3" /> AI
                      </span>
                    )}
                    <span className="text-xs text-gray-400 ml-auto">
                      {new Date(c.created_at).toLocaleString()}
                    </span>
                  </div>
                  <p className="text-sm text-gray-700 ml-9 whitespace-pre-wrap">{c.content}</p>
                </div>
              ))}
            </div>

            {/* Add Comment */}
            <div className="p-4 border-t border-gray-200 bg-gray-50 rounded-b-xl">
              <form onSubmit={handleCommentSubmit}>
                <textarea
                  value={comment}
                  onChange={(e) => setComment(e.target.value)}
                  placeholder="Write a comment..."
                  rows={3}
                  className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 outline-none transition resize-none text-sm"
                />
                <div className="flex items-center justify-between mt-3">
                  {user.role === 'agent' && (
                    <button
                      type="button"
                      onClick={handleAISuggest}
                      disabled={aiLoading}
                      className="flex items-center gap-1.5 text-xs text-purple-600 hover:text-purple-700 font-medium bg-purple-50 px-3 py-1.5 rounded-lg hover:bg-purple-100 transition disabled:opacity-50"
                    >
                      <HiOutlineSparkles className="w-4 h-4" />
                      {aiLoading ? 'Generating...' : 'AI Suggest'}
                    </button>
                  )}
                  <button
                    type="submit"
                    disabled={submitting || !comment.trim()}
                    className="ml-auto bg-primary-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-primary-700 transition disabled:opacity-50"
                  >
                    {submitting ? 'Posting...' : 'Post Comment'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>

        {/* ── Col 2: Details Sidebar (2/8) ── */}
        <div className="lg:col-span-2 space-y-4 lg:sticky lg:top-6 lg:max-h-[calc(100vh-6rem)] lg:overflow-y-auto lg:pr-0.5">
          {/* Status Actions */}
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-4">
            <h3 className="text-sm font-semibold text-gray-900 mb-3">Actions</h3>
            <div className="space-y-2">
              {(statusActions[ticket.status] || []).map((action) => (
                <button
                  key={action.value}
                  onClick={() => handleStatusChange(action.value)}
                  className={`w-full text-white text-sm font-medium py-2 px-4 rounded-lg transition ${action.color}`}
                >
                  {action.label}
                </button>
              ))}
            </div>
          </div>

          {/* Agent Assignment (agents only) */}
          {user.role === 'agent' && (
            <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-4">
              <h3 className="text-sm font-semibold text-gray-900 mb-3">Assignment</h3>
              {ticket.agent_name ? (
                <div className="flex items-center gap-2 text-sm">
                  <div className="w-7 h-7 bg-primary-100 rounded-full flex items-center justify-center text-xs font-medium text-primary-700">
                    {ticket.agent_name[0]}
                  </div>
                  <span>{ticket.agent_name}</span>
                </div>
              ) : (
                <p className="text-sm text-gray-500 mb-2">Unassigned</p>
              )}
              <button
                onClick={() => setShowAssign(!showAssign)}
                className="mt-2 text-xs text-primary-600 hover:underline"
              >
                {showAssign ? 'Cancel' : 'Change Assignment'}
              </button>
              {showAssign && (
                <div className="mt-2 space-y-1">
                  {agents.map((agent) => (
                    <button
                      key={agent.id}
                      onClick={() => handleAssign(agent.id)}
                      className="w-full text-left text-sm px-3 py-2 rounded-lg hover:bg-gray-50 transition flex items-center gap-2"
                    >
                      <div className="w-6 h-6 bg-gray-100 rounded-full flex items-center justify-center text-xs">
                        {agent.name[0]}
                      </div>
                      {agent.name}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Ticket Details */}
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-4">
            <h3 className="text-sm font-semibold text-gray-900 mb-3">Details</h3>
            <dl className="space-y-3 text-sm">
              <div>
                <dt className="text-gray-500">Status</dt>
                <dd className="mt-0.5"><StatusBadge status={ticket.status} /></dd>
              </div>
              <div>
                <dt className="text-gray-500">Priority</dt>
                <dd className="mt-0.5"><PriorityBadge priority={ticket.priority} /></dd>
              </div>
              <div>
                <dt className="text-gray-500">Category</dt>
                <dd className="mt-0.5 font-medium">{ticket.category_name || 'Uncategorized'}</dd>
              </div>
              <div>
                <dt className="text-gray-500">Created</dt>
                <dd className="mt-0.5">{new Date(ticket.created_at).toLocaleDateString()}</dd>
              </div>
              {ticket.updated_at && (
                <div>
                  <dt className="text-gray-500">Updated</dt>
                  <dd className="mt-0.5">{new Date(ticket.updated_at).toLocaleDateString()}</dd>
                </div>
              )}
            </dl>
          </div>

        </div>{/* end Col 2 */}

        {/* ── Col 3: Similar Tickets (2/8) — agents only ── */}
        {user.role === 'agent' && (
          <div className="lg:col-span-2 lg:sticky lg:top-6 lg:max-h-[calc(100vh-6rem)] lg:overflow-y-auto">
            <SimilarTickets ticketId={id} />
          </div>
        )}

      </div>
    </div>
  )
}
