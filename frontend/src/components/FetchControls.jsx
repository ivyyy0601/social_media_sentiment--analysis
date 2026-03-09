import React, { useState } from 'react'

function FetchControls({ onFetch, loading }) {
  const [fetchLimit, setFetchLimit] = useState(100)
  const [fetchStartDate, setFetchStartDate] = useState('')
  const [fetchEndDate, setFetchEndDate] = useState('')
  const [showAdvanced, setShowAdvanced] = useState(false)

  const handleFetch = () => {
    const params = {
      limit: fetchLimit
    }
    
    if (fetchStartDate) {
      params.start_date = fetchStartDate
    }
    if (fetchEndDate) {
      params.end_date = fetchEndDate
    }
    
    onFetch(params)
  }

  return (
    <div style={{ display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
      <div style={{ display: 'flex', gap: '5px', alignItems: 'center' }}>
        <label htmlFor="fetch-limit" style={{ fontSize: '14px' }}>Posts to fetch:</label>
        <input
          id="fetch-limit"
          type="number"
          min="1"
          max="500"
          value={fetchLimit}
          onChange={(e) => setFetchLimit(Math.max(1, Math.min(500, parseInt(e.target.value) || 100)))}
          style={{ width: '80px', padding: '5px' }}
        />
      </div>

      {showAdvanced && (
        <>
          <div style={{ display: 'flex', gap: '5px', alignItems: 'center' }}>
            <label htmlFor="fetch-start-date" style={{ fontSize: '14px' }}>From:</label>
            <input
              id="fetch-start-date"
              type="date"
              value={fetchStartDate}
              onChange={(e) => setFetchStartDate(e.target.value)}
              style={{ padding: '5px' }}
            />
          </div>
          <div style={{ display: 'flex', gap: '5px', alignItems: 'center' }}>
            <label htmlFor="fetch-end-date" style={{ fontSize: '14px' }}>To:</label>
            <input
              id="fetch-end-date"
              type="date"
              value={fetchEndDate}
              onChange={(e) => setFetchEndDate(e.target.value)}
              style={{ padding: '5px' }}
            />
          </div>
        </>
      )}

      <button 
        onClick={() => setShowAdvanced(!showAdvanced)} 
        className="btn-secondary"
        style={{ fontSize: '12px' }}
      >
        {showAdvanced ? '▲ Hide Dates' : '▼ Historical Fetch'}
      </button>

      <button onClick={handleFetch} disabled={loading} className="btn-primary">
        {loading ? 'Fetching & Analyzing...' : 'Fetch New Posts'}
      </button>
    </div>
  )
}

export default FetchControls
