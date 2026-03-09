import React from 'react'

function EmptyState({ 
  icon = '📊', 
  title = 'No data available', 
  message = 'Try adjusting your filters or fetch new posts.',
  actionButton 
}) {
  return (
    <div className="empty-state">
      <div className="empty-icon">{icon}</div>
      <h3>{title}</h3>
      <p>{message}</p>
      {actionButton && (
        <div className="empty-action">
          {actionButton}
        </div>
      )}
    </div>
  )
}

export default EmptyState
