import React, { useState } from 'react'
import axios from 'axios'

function ExportMenu({ filters, API_BASE }) {
  const [isOpen, setIsOpen] = useState(false)
  const [exporting, setExporting] = useState(false)

  const buildFilterParams = () => {
    const params = new URLSearchParams()
    
    if (filters.ticker && filters.ticker.length === 1) {
      params.append('ticker', filters.ticker[0])
    }
    if (filters.industry && filters.industry.length === 1) {
      params.append('industry', filters.industry[0])
    }
    if (filters.sector && filters.sector.length === 1) {
      params.append('sector', filters.sector[0])
    }
    if (filters.startDate) {
      params.append('start_date', filters.startDate)
    }
    if (filters.endDate) {
      params.append('end_date', filters.endDate)
    }
    if (filters.sentiment) {
      params.append('sentiment', filters.sentiment)
    }
    if (filters.granularity) {
      params.append('granularity', filters.granularity)
    }
    
    return params.toString()
  }

  const handleExport = async (type, format) => {
    setExporting(true)
    try {
      const params = buildFilterParams()
      const url = `${API_BASE}/api/v1/export/${type}?format=${format}&${params}`
      
      // Download file
      const link = document.createElement('a')
      link.href = url
      link.download = `${type}_export.${format}`
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      
      setIsOpen(false)
    } catch (err) {
      console.error('Export error:', err)
      alert('Failed to export data')
    } finally {
      setExporting(false)
    }
  }

  return (
    <div className="export-menu" style={{ position: 'relative' }}>
      <button 
        onClick={() => setIsOpen(!isOpen)} 
        className="btn-secondary"
        disabled={exporting}
      >
        {exporting ? 'Exporting...' : 'Export Data ▾'}
      </button>
      
      {isOpen && (
        <div 
          className="export-dropdown" 
          style={{
            position: 'absolute',
            top: '100%',
            right: 0,
            marginTop: '5px',
            backgroundColor: 'white',
            border: '1px solid #ddd',
            borderRadius: '4px',
            boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
            zIndex: 1000,
            minWidth: '200px'
          }}
        >
          <div style={{ padding: '10px', borderBottom: '1px solid #eee' }}>
            <strong>Export Posts</strong>
            <div style={{ marginTop: '5px' }}>
              <button 
                onClick={() => handleExport('posts', 'csv')}
                style={{ display: 'block', width: '100%', marginBottom: '5px', padding: '5px', cursor: 'pointer' }}
              >
                📄 CSV
              </button>
              <button 
                onClick={() => handleExport('posts', 'json')}
                style={{ display: 'block', width: '100%', padding: '5px', cursor: 'pointer' }}
              >
                📋 JSON
              </button>
            </div>
          </div>
          
          <div style={{ padding: '10px' }}>
            <strong>Export Sentiment Trends</strong>
            <div style={{ marginTop: '5px' }}>
              <button 
                onClick={() => handleExport('sentiment-trends', 'csv')}
                style={{ display: 'block', width: '100%', marginBottom: '5px', padding: '5px', cursor: 'pointer' }}
              >
                📄 CSV
              </button>
              <button 
                onClick={() => handleExport('sentiment-trends', 'json')}
                style={{ display: 'block', width: '100%', padding: '5px', cursor: 'pointer' }}
              >
                📋 JSON
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default ExportMenu
