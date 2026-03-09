import React from 'react'

function DateRangeFilter({ startDate, endDate, onStartDateChange, onEndDateChange, granularity, onGranularityChange }) {
  const handleClear = () => {
    onStartDateChange('')
    onEndDateChange('')
  }

  return (
    <div className="filter-group date-range-filter">
      <label>Date Range</label>
      
      <div className="date-inputs">
        <div className="date-input-group">
          <label htmlFor="start-date" className="date-label">From</label>
          <input
            id="start-date"
            type="date"
            value={startDate}
            onChange={(e) => onStartDateChange(e.target.value)}
            className="date-input"
          />
        </div>
        
        <div className="date-input-group">
          <label htmlFor="end-date" className="date-label">To</label>
          <input
            id="end-date"
            type="date"
            value={endDate}
            onChange={(e) => onEndDateChange(e.target.value)}
            className="date-input"
          />
        </div>
      </div>

      {(startDate || endDate) && (
        <button onClick={handleClear} className="clear-dates">
          Clear Dates
        </button>
      )}

      {onGranularityChange && (
        <div className="granularity-selector">
          <label>Granularity</label>
          <div className="radio-group">
            <label className="radio-label">
              <input
                type="radio"
                value="day"
                checked={granularity === 'day'}
                onChange={(e) => onGranularityChange(e.target.value)}
              />
              Daily
            </label>
            <label className="radio-label">
              <input
                type="radio"
                value="week"
                checked={granularity === 'week'}
                onChange={(e) => onGranularityChange(e.target.value)}
              />
              Weekly
            </label>
          </div>
        </div>
      )}
    </div>
  )
}

export default DateRangeFilter
