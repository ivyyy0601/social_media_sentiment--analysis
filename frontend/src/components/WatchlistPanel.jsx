import React, { useState, useEffect } from 'react'
import axios from 'axios'

function WatchlistPanel({ API_BASE, onSelectTickers }) {
  const [watchlists, setWatchlists] = useState([])
  const [isOpen, setIsOpen] = useState(false)
  const [newWatchlistName, setNewWatchlistName] = useState('')
  const [addingTicker, setAddingTicker] = useState(null)
  const [newTicker, setNewTicker] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (isOpen) {
      loadWatchlists()
    }
  }, [isOpen])

  const loadWatchlists = async () => {
    setLoading(true)
    try {
      const response = await axios.get(`${API_BASE}/api/v1/watchlists`)
      if (response.data.success) {
        setWatchlists(response.data.data.watchlists || [])
      }
    } catch (err) {
      console.error('Error loading watchlists:', err)
    } finally {
      setLoading(false)
    }
  }

  const createWatchlist = async () => {
    if (!newWatchlistName.trim()) return
    
    try {
      const response = await axios.post(`${API_BASE}/api/v1/watchlists`, {
        name: newWatchlistName
      })
      if (response.data.success) {
        setNewWatchlistName('')
        loadWatchlists()
      }
    } catch (err) {
      console.error('Error creating watchlist:', err)
      alert('Failed to create watchlist')
    }
  }

  const deleteWatchlist = async (id) => {
    if (!confirm('Are you sure you want to delete this watchlist?')) return
    
    try {
      await axios.delete(`${API_BASE}/api/v1/watchlists/${id}`)
      loadWatchlists()
    } catch (err) {
      console.error('Error deleting watchlist:', err)
      alert('Failed to delete watchlist')
    }
  }

  const addTickerToWatchlist = async (watchlistId) => {
    if (!newTicker.trim()) return
    
    try {
      await axios.post(`${API_BASE}/api/v1/watchlists/${watchlistId}/tickers`, {
        ticker: newTicker.toUpperCase()
      })
      setNewTicker('')
      setAddingTicker(null)
      loadWatchlists()
    } catch (err) {
      console.error('Error adding ticker:', err)
      alert('Failed to add ticker')
    }
  }

  const removeTickerFromWatchlist = async (watchlistId, ticker) => {
    try {
      await axios.delete(`${API_BASE}/api/v1/watchlists/${watchlistId}/tickers/${ticker}`)
      loadWatchlists()
    } catch (err) {
      console.error('Error removing ticker:', err)
      alert('Failed to remove ticker')
    }
  }

  const applyWatchlist = (tickers) => {
    onSelectTickers(tickers)
    setIsOpen(false)
  }

  if (!isOpen) {
    return (
      <button onClick={() => setIsOpen(true)} className="btn-secondary">
        📋 Watchlists
      </button>
    )
  }

  return (
    <div 
      className="watchlist-panel"
      style={{
        position: 'fixed',
        top: 0,
        right: 0,
        width: '350px',
        height: '100vh',
        backgroundColor: 'white',
        boxShadow: '-2px 0 8px rgba(0,0,0,0.1)',
        zIndex: 1000,
        overflowY: 'auto',
        padding: '20px'
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '20px' }}>
        <h3>Watchlists</h3>
        <button onClick={() => setIsOpen(false)} style={{ cursor: 'pointer', fontSize: '20px' }}>×</button>
      </div>

      <div style={{ marginBottom: '20px' }}>
        <h4>Create New Watchlist</h4>
        <div style={{ display: 'flex', gap: '5px' }}>
          <input
            type="text"
            value={newWatchlistName}
            onChange={(e) => setNewWatchlistName(e.target.value)}
            placeholder="Watchlist name"
            style={{ flex: 1, padding: '5px' }}
            onKeyPress={(e) => e.key === 'Enter' && createWatchlist()}
          />
          <button onClick={createWatchlist} className="btn-primary">
            Create
          </button>
        </div>
      </div>

      {loading ? (
        <p>Loading...</p>
      ) : (
        <div>
          {watchlists.length === 0 ? (
            <p style={{ color: '#666', fontStyle: 'italic' }}>No watchlists yet. Create one above!</p>
          ) : (
            watchlists.map(wl => (
              <div 
                key={wl.id} 
                style={{ 
                  border: '1px solid #ddd', 
                  borderRadius: '4px', 
                  padding: '10px', 
                  marginBottom: '10px' 
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '10px' }}>
                  <strong>{wl.name}</strong>
                  <div>
                    <button 
                      onClick={() => applyWatchlist(wl.tickers)}
                      style={{ marginRight: '5px', fontSize: '12px', padding: '2px 8px', cursor: 'pointer' }}
                    >
                      Apply
                    </button>
                    <button 
                      onClick={() => deleteWatchlist(wl.id)}
                      style={{ fontSize: '12px', padding: '2px 8px', cursor: 'pointer', color: 'red' }}
                    >
                      Delete
                    </button>
                  </div>
                </div>
                
                <div style={{ fontSize: '14px' }}>
                  {wl.tickers && wl.tickers.length > 0 ? (
                    <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
                      {wl.tickers.map(ticker => (
                        <li 
                          key={ticker} 
                          style={{ 
                            display: 'flex', 
                            justifyContent: 'space-between', 
                            padding: '5px 0',
                            borderBottom: '1px solid #eee'
                          }}
                        >
                          <span>{ticker}</span>
                          <button 
                            onClick={() => removeTickerFromWatchlist(wl.id, ticker)}
                            style={{ fontSize: '12px', cursor: 'pointer', color: 'red', border: 'none', background: 'none' }}
                          >
                            ×
                          </button>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p style={{ fontSize: '12px', color: '#666', fontStyle: 'italic' }}>No tickers yet</p>
                  )}
                </div>

                {addingTicker === wl.id ? (
                  <div style={{ marginTop: '10px', display: 'flex', gap: '5px' }}>
                    <input
                      type="text"
                      value={newTicker}
                      onChange={(e) => setNewTicker(e.target.value)}
                      placeholder="Ticker symbol"
                      style={{ flex: 1, padding: '5px', fontSize: '12px' }}
                      onKeyPress={(e) => e.key === 'Enter' && addTickerToWatchlist(wl.id)}
                    />
                    <button 
                      onClick={() => addTickerToWatchlist(wl.id)}
                      style={{ fontSize: '12px', padding: '5px 10px', cursor: 'pointer' }}
                    >
                      Add
                    </button>
                    <button 
                      onClick={() => { setAddingTicker(null); setNewTicker('') }}
                      style={{ fontSize: '12px', padding: '5px 10px', cursor: 'pointer' }}
                    >
                      Cancel
                    </button>
                  </div>
                ) : (
                  <button 
                    onClick={() => setAddingTicker(wl.id)}
                    style={{ marginTop: '10px', fontSize: '12px', padding: '5px 10px', cursor: 'pointer' }}
                  >
                    + Add Ticker
                  </button>
                )}
              </div>
            ))
          )}
        </div>
      )}
    </div>
  )
}

export default WatchlistPanel
