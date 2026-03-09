import React, { useState, useRef, useEffect } from 'react'

function TickerFilter({ tickers, selectedTickers, onChange }) {
  const [searchTerm, setSearchTerm] = useState('')
  const [showDropdown, setShowDropdown] = useState(false)
  const dropdownRef = useRef(null)

  // Filter tickers based on search term
  const filteredTickers = tickers.filter(ticker =>
    ticker.symbol.toLowerCase().includes(searchTerm.toLowerCase()) ||
    (ticker.company_name && ticker.company_name.toLowerCase().includes(searchTerm.toLowerCase()))
  )

  // Handle click outside to close dropdown
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setShowDropdown(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const handleToggleTicker = (symbol) => {
    const newSelected = selectedTickers.includes(symbol)
      ? selectedTickers.filter(t => t !== symbol)
      : [...selectedTickers, symbol]
    onChange(newSelected)
  }

  const handleClearAll = () => {
    onChange([])
  }

  return (
    <div className="filter-group ticker-filter" ref={dropdownRef}>
      <label>Filter by Stock</label>
      <div className="filter-input-wrapper">
        <input
          type="text"
          placeholder="Search tickers..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          onFocus={() => setShowDropdown(true)}
          className="filter-input"
        />
        {selectedTickers.length > 0 && (
          <button onClick={handleClearAll} className="clear-filter">
            Clear ({selectedTickers.length})
          </button>
        )}
      </div>

      {showDropdown && (
        <div className="filter-dropdown">
          {filteredTickers.length === 0 ? (
            <div className="dropdown-empty">No tickers found</div>
          ) : (
            <div className="dropdown-list">
              {filteredTickers.map(ticker => (
                <div
                  key={ticker.symbol}
                  className={`dropdown-item ${selectedTickers.includes(ticker.symbol) ? 'selected' : ''}`}
                  onClick={() => handleToggleTicker(ticker.symbol)}
                >
                  <input
                    type="checkbox"
                    checked={selectedTickers.includes(ticker.symbol)}
                    readOnly
                  />
                  <span className="ticker-symbol">{ticker.symbol}</span>
                  {ticker.company_name && (
                    <span className="ticker-company">{ticker.company_name}</span>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {selectedTickers.length > 0 && (
        <div className="selected-filters">
          {selectedTickers.map(symbol => (
            <span key={symbol} className="filter-badge">
              {symbol}
              <button onClick={() => handleToggleTicker(symbol)}>×</button>
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

export default TickerFilter
