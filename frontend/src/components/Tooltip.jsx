import React, { useState } from 'react'

function Tooltip({ text, children }) {
  const [visible, setVisible] = useState(false)

  return (
    <div className="tooltip-container">
      <span
        className="tooltip-trigger"
        onMouseEnter={() => setVisible(true)}
        onMouseLeave={() => setVisible(false)}
        onClick={() => setVisible(!visible)}
      >
        {children || <span className="info-icon">ℹ️</span>}
      </span>
      {visible && (
        <div className="tooltip-bubble">
          {text}
        </div>
      )}
    </div>
  )
}

export default Tooltip
