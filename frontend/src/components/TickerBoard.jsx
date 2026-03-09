import React, { useState, useEffect, useCallback } from 'react'
import axios from 'axios'
import TickerAnalysisPanel from './TickerAnalysisPanel'

const DEFAULT_TICKERS = ['NVDA', 'AAPL', 'MSFT', 'GOOG', 'AMZN', 'META', 'TSLA', 'AVGO', 'TXN', 'COHR', 'INTC', 'ASML', 'SNDK']

function TickerBoard({ apiBase, onTickerSelect }) {
  const [board, setBoard] = useState([])
  const [loading, setLoading] = useState(true)
  const [days, setDays] = useState(30)
  const [selectedTicker, setSelectedTicker] = useState(null)
  const [fetchingTicker, setFetchingTicker] = useState(null)
  const [fetchingAll, setFetchingAll] = useState(false)
  const [lastUpdated, setLastUpdated] = useState(null)
  const [schedulerStatus, setSchedulerStatus] = useState(null)
  const [autoRunning, setAutoRunning] = useState(false)

  const loadBoard = useCallback(async (d = days) => {
    try {
      setLoading(true)
      const res = await axios.get(`${apiBase}/api/v1/ticker-board?tickers=${DEFAULT_TICKERS.join(',')}&days=${d}`)
      if (res.data.success) {
        setBoard(res.data.data.board)
        setLastUpdated(new Date().toLocaleTimeString())
      }
    } catch (e) {
      console.error('Failed to load ticker board', e)
    } finally {
      setLoading(false)
    }
  }, [apiBase, days])

  const loadSchedulerStatus = useCallback(async () => {
    try {
      const res = await axios.get(`${apiBase}/api/v1/scheduler/status`)
      if (res.data.success) setSchedulerStatus(res.data.data)
    } catch (e) {}
  }, [apiBase])

  const triggerAutoFetch = async () => {
    setAutoRunning(true)
    try {
      await axios.post(`${apiBase}/api/v1/scheduler/run-now`)
      // Poll board until data updates (max 60s)
      for (let i = 0; i < 12; i++) {
        await new Promise(r => setTimeout(r, 5000))
        await loadBoard(days)
        await loadSchedulerStatus()
      }
    } catch (e) {
      console.error('Auto-fetch failed', e)
    } finally {
      setAutoRunning(false)
    }
  }

  useEffect(() => {
    loadBoard()
    loadSchedulerStatus()
  }, [])

  const fetchTicker = async (ticker) => {
    setFetchingTicker(ticker)
    try {
      await axios.get(`${apiBase}/api/v1/fetch-posts?query=${ticker}&max_results=50`)
      await loadBoard()
    } catch (e) {
      console.error(`Failed to fetch ${ticker}`, e)
    } finally {
      setFetchingTicker(null)
    }
  }

  const fetchAll = async () => {
    setFetchingAll(true)
    for (const ticker of DEFAULT_TICKERS) {
      setFetchingTicker(ticker)
      try {
        await axios.get(`${apiBase}/api/v1/fetch-posts?query=${ticker}&max_results=30`)
      } catch (e) {
        console.error(`Failed to fetch ${ticker}`, e)
      }
    }
    setFetchingTicker(null)
    await loadBoard()
    setFetchingAll(false)
  }

  const handleDaysChange = (d) => {
    setDays(d)
    loadBoard(d)
  }

  const getScoreColor = (score, label) => {
    if (label === 'no_data') return '#94a3b8'
    if (score > 0.2) return '#16a34a'
    if (score > 0.05) return '#4ade80'
    if (score < -0.2) return '#dc2626'
    if (score < -0.05) return '#f87171'
    return '#94a3b8'
  }

  const getLabelBadge = (label) => {
    const map = {
      bullish: { text: 'Bullish', bg: '#dcfce7', color: '#16a34a' },
      bearish: { text: 'Bearish', bg: '#fee2e2', color: '#dc2626' },
      neutral: { text: 'Neutral', bg: '#f1f5f9', color: '#64748b' },
      no_data: { text: 'No Data', bg: '#f8fafc', color: '#94a3b8' },
    }
    return map[label] || map.no_data
  }

  return (
    <div className="ticker-board card">
      <div className="ticker-board-header">
        <div>
          <h2>📊 Sentiment Leaderboard</h2>
          <div className="ticker-board-meta">
            {lastUpdated && <span className="ticker-board-updated">Scores updated {lastUpdated}</span>}
            {schedulerStatus && (
              <span className="ticker-scheduler-info">
                {schedulerStatus.running ? '🟢 Auto-fetch ON' : '🔴 Auto-fetch OFF'}
                {schedulerStatus.last_fetch && ` · Last: ${new Date(schedulerStatus.last_fetch).toLocaleString()}`}
                {` · Every ${schedulerStatus.interval_hours}h`}
              </span>
            )}
            <span className="ticker-sources-info">📡 Reddit · StockTwits · Yahoo Finance News</span>
          </div>
        </div>
        <div className="ticker-board-controls">
          <div className="days-selector">
            {[7, 30, 90].map(d => (
              <button
                key={d}
                className={`days-btn ${days === d ? 'active' : ''}`}
                onClick={() => handleDaysChange(d)}
              >{d}d</button>
            ))}
          </div>
          <button
            className="btn-fetch-all"
            onClick={triggerAutoFetch}
            disabled={autoRunning || fetchingAll}
            title="Fetch latest posts from Reddit, StockTwits & Yahoo Finance for all tickers"
          >
            {autoRunning ? '⏳ Fetching...' : fetchingAll ? `⬇ ${fetchingTicker}...` : '⬇ Fetch All Sources'}
          </button>
          <button
            className="btn-fetch-all"
            style={{ background: '#334155' }}
            onClick={fetchAll}
            disabled={fetchingAll || autoRunning}
            title="Fetch ticker by ticker (Reddit only)"
          >
            {fetchingAll ? `${fetchingTicker}...` : '⬇ Reddit Only'}
          </button>
          <button className="btn-refresh-board" onClick={() => loadBoard()} disabled={loading}>
            🔄
          </button>
        </div>
      </div>

      {loading && board.length === 0 ? (
        <div className="ticker-board-loading">Loading sentiment data...</div>
      ) : (
        <div className="ticker-board-grid">
          {board.map((item, idx) => {
            const badge = getLabelBadge(item.label)
            const scoreColor = getScoreColor(item.score, item.label)
            const scoreWidth = item.score !== null
              ? `${Math.abs(item.score) * 100}%`
              : '0%'
            const isFetching = fetchingTicker === item.ticker
            const hasData = item.total_posts > 0

            const isSelected = selectedTicker === item.ticker

            return (
              <div
                key={item.ticker}
                className={`ticker-card ${!hasData ? 'ticker-card-nodata' : ''} ${isSelected ? 'ticker-card-selected' : ''}`}
                onClick={() => {
                  if (!hasData) return
                  setSelectedTicker(isSelected ? null : item.ticker)
                  if (!isSelected) setTimeout(() => {
                    document.getElementById('ticker-analysis-anchor')?.scrollIntoView({ behavior: 'smooth' })
                  }, 50)
                }}
                style={{ cursor: hasData ? 'pointer' : 'default' }}
              >
                <div className="ticker-card-top">
                  <div>
                    <div className="ticker-card-rank">#{idx + 1}</div>
                    <div className="ticker-card-symbol">{item.ticker}</div>
                    <div className="ticker-card-company">{item.company}</div>
                  </div>
                  <div className="ticker-card-right">
                    <span
                      className="ticker-badge"
                      style={{ background: badge.bg, color: badge.color }}
                    >
                      {badge.text}
                    </span>
                    <button
                      className="btn-fetch-ticker"
                      onClick={e => { e.stopPropagation(); fetchTicker(item.ticker) }}
                      disabled={isFetching || fetchingAll}
                      title={`Fetch latest posts for ${item.ticker}`}
                    >
                      {isFetching ? '⏳' : '⬇'}
                    </button>
                  </div>
                </div>

                {/* Score bar */}
                <div className="ticker-score-bar-bg">
                  <div
                    className="ticker-score-bar-fill"
                    style={{
                      width: scoreWidth,
                      background: scoreColor,
                      marginLeft: item.score !== null && item.score < 0 ? 'auto' : '0',
                    }}
                  />
                </div>

                <div className="ticker-card-stats">
                  <span className="ticker-score" style={{ color: scoreColor }}>
                    {item.score !== null ? (item.score > 0 ? '+' : '') + item.score.toFixed(3) : 'N/A'}
                  </span>
                  <span className="ticker-posts">{item.total_posts} posts</span>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {selectedTicker && (
        <TickerAnalysisPanel
          ticker={selectedTicker}
          apiBase={apiBase}
          onClose={() => setSelectedTicker(null)}
          onViewDashboard={onTickerSelect ? (t) => onTickerSelect(t) : null}
        />
      )}
    </div>
  )
}

export default TickerBoard
