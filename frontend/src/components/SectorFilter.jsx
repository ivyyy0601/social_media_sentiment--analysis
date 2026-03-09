import React from 'react'

function SectorFilter({ sectors, selectedSectors, onChange }) {
  const handleToggle = (sector) => {
    const newSelected = selectedSectors.includes(sector)
      ? selectedSectors.filter(s => s !== sector)
      : [...selectedSectors, sector]
    onChange(newSelected)
  }

  const handleClearAll = () => {
    onChange([])
  }

  return (
    <div className="filter-group sector-filter">
      <label>
        Filter by Sector
        {selectedSectors.length > 0 && (
          <button onClick={handleClearAll} className="clear-filter-inline">
            Clear ({selectedSectors.length})
          </button>
        )}
      </label>
      
      <div className="filter-select-wrapper">
        <select
          multiple
          value={selectedSectors}
          onChange={(e) => {
            const selected = Array.from(e.target.selectedOptions, option => option.value)
            onChange(selected)
          }}
          className="filter-select"
          size="5"
        >
          {sectors.map(sector => (
            <option key={sector.name} value={sector.name}>
              {sector.name}
            </option>
          ))}
        </select>
      </div>

      {selectedSectors.length > 0 && (
        <div className="selected-filters">
          {selectedSectors.map(sector => (
            <span key={sector} className="filter-badge">
              {sector}
              <button onClick={() => handleToggle(sector)}>×</button>
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

export default SectorFilter
