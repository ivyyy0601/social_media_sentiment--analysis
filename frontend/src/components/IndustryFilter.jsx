import React from 'react'

function IndustryFilter({ industries, selectedIndustries, onChange }) {
  const handleToggle = (industry) => {
    const newSelected = selectedIndustries.includes(industry)
      ? selectedIndustries.filter(i => i !== industry)
      : [...selectedIndustries, industry]
    onChange(newSelected)
  }

  const handleClearAll = () => {
    onChange([])
  }

  return (
    <div className="filter-group industry-filter">
      <label>
        Filter by Industry
        {selectedIndustries.length > 0 && (
          <button onClick={handleClearAll} className="clear-filter-inline">
            Clear ({selectedIndustries.length})
          </button>
        )}
      </label>
      
      <div className="filter-select-wrapper">
        <select
          multiple
          value={selectedIndustries}
          onChange={(e) => {
            const selected = Array.from(e.target.selectedOptions, option => option.value)
            onChange(selected)
          }}
          className="filter-select"
          size="5"
        >
          {industries.map(industry => (
            <option key={industry.name} value={industry.name}>
              {industry.name}
            </option>
          ))}
        </select>
      </div>

      {selectedIndustries.length > 0 && (
        <div className="selected-filters">
          {selectedIndustries.map(industry => (
            <span key={industry} className="filter-badge">
              {industry}
              <button onClick={() => handleToggle(industry)}>×</button>
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

export default IndustryFilter
