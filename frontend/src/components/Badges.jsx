const statusConfig = {
  open: { label: 'Open', bg: 'bg-yellow-100', text: 'text-yellow-800', dot: 'bg-yellow-400' },
  in_progress: { label: 'In Progress', bg: 'bg-blue-100', text: 'text-blue-800', dot: 'bg-blue-400' },
  resolved: { label: 'Resolved', bg: 'bg-green-100', text: 'text-green-800', dot: 'bg-green-400' },
}

const priorityConfig = {
  low: { label: 'Low', bg: 'bg-gray-100', text: 'text-gray-700' },
  medium: { label: 'Medium', bg: 'bg-orange-100', text: 'text-orange-700' },
  high: { label: 'High', bg: 'bg-red-100', text: 'text-red-700' },
  urgent: { label: 'Urgent', bg: 'bg-red-200', text: 'text-red-800' },
}

export function StatusBadge({ status }) {
  const config = statusConfig[status] || statusConfig.open
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${config.bg} ${config.text}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${config.dot}`}></span>
      {config.label}
    </span>
  )
}

export function PriorityBadge({ priority }) {
  const config = priorityConfig[priority] || priorityConfig.medium
  return (
    <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium ${config.bg} ${config.text}`}>
      {config.label}
    </span>
  )
}
