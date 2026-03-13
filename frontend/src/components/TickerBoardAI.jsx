import React, { useState, useEffect } from 'react'
import axios from 'axios'

const DEFAULT_TICKERS = ['NVDA', 'AAPL', 'MSFT', 'GOOG', 'AMZN', 'META', 'TSLA', 'AVGO', 'TXN', 'COHR', 'INTC', 'ASML', 'SNDK']

function TickerBoardAI({ apiBase }) {
  const [board, setBoard] = useState([])
  const [loading, setLoading] = useState(true)
  const [days, setDays] = useState(7)
  const [lastUpdated, setLastUpdated] = useState(null)

  const loadBoard = async (d = days) => {
    setLoading(true)
    try {
      const res = await axios.get(`${apiBase}/api/v1/ai-ticker-board?tickers=${DEFAULT_TICKERS.join(',')}&days=${d}`)
      if (res.data.success) {
        setBoard(res.data.data.board)
        setLastUpdated(new Date().toLocaleTimeString())
      }
    } catch (e) {
      console.error('Failed to load AI board', e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadBoard() }, [])

  const handleDaysChange = (d) => {
    setDays(d)
    loadBoard(d)
  }

  const getScoreColor = (score, label) => {
    if (label === 'no_data' || score == null) return '#94a3b8'
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
          <h2>🤖 AI Sentiment Leaderboard</h2>
          <div className="ticker-board-meta">
            {lastUpdated && <span className="ticker-board-updated">Updated {lastUpdated}</span>}
            <span className="ticker-sources-info">Scored by Gemini per post · stored in DB</span>
          </div>
        </div>
        <div className="ticker-board-controls">
          <div className="days-selector">
            {[7, 30].map(d => (
              <button key={d} className={`days-btn ${days === d ? 'active' : ''}`} onClick={() => handleDaysChange(d)}>{d}d</button>
            ))}
          </div>
          <button className="btn-refresh-board" onClick={() => loadBoard(days)} disabled={loading}>🔄</button>
        </div>
      </div>

      {loading && board.length === 0 ? (
        <div className="ticker-board-loading">Loading AI sentiment scores...</div>
      ) : (
        <div className="ticker-board-grid">
          {board.map((item, idx) => {
            const badge = getLabelBadge(item.label)
            const scoreColor = getScoreColor(item.score, item.label)
            const scoreWidth = item.score !== null ? `${Math.abs(item.score) * 100}%` : '0%'
            const hasData = item.ai_scored_posts > 0

            return (
              <div
                key={item.ticker}
                className={`ticker-card ${!hasData ? 'ticker-card-nodata' : ''}`}
                style={{ cursor: 'default' }}
              >
                <div className="ticker-card-top">
                  <div>
                    <div className="ticker-card-rank">#{idx + 1}</div>
                    <div className="ticker-card-symbol">{item.ticker}</div>
                  </div>
                  <span className="ticker-badge" style={{ background: badge.bg, color: badge.color }}>
                    {badge.text}
                  </span>
                </div>

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
                  <span className="ticker-posts">{item.ai_scored_posts}/{item.total_posts} AI scored</span>
                </div>

                {item.finbert_score !== null && (
                  <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 4, textAlign: 'right' }}>
                    FinBERT: {item.finbert_score > 0 ? '+' : ''}{item.finbert_score?.toFixed(3)}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

export default TickerBoardAI
