import React, { useState } from 'react'
import axios from 'axios'

const DEFAULT_TICKERS = ['NVDA', 'AAPL', 'MSFT', 'GOOG', 'AMZN', 'META', 'TSLA', 'AVGO', 'TXN', 'COHR', 'INTC', 'ASML', 'SNDK']

function TickerBoardGemini({ apiBase }) {
  const [board, setBoard] = useState([])
  const [loading, setLoading] = useState(false)
  const [days, setDays] = useState(7)
  const [ran, setRan] = useState(false)

  const runAnalysis = async () => {
    setLoading(true)
    setBoard([])
    try {
      const res = await axios.get(`${apiBase}/api/v1/gemini-board?tickers=${DEFAULT_TICKERS.join(',')}&days=${days}`)
      if (res.data.success) {
        setBoard(res.data.data.board)
        setRan(true)
      }
    } catch (e) {
      console.error('Gemini board failed', e)
    } finally {
      setLoading(false)
    }
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

  const diffColor = (gemini, finbert) => {
    if (gemini == null || finbert == null) return '#94a3b8'
    const diff = gemini - finbert
    if (diff > 0.1) return '#16a34a'
    if (diff < -0.1) return '#dc2626'
    return '#94a3b8'
  }

  return (
    <div className="ticker-board card">
      <div className="ticker-board-header">
        <div>
          <h2>🤖 Gemini Sentiment Leaderboard</h2>
          <p style={{ color: '#64748b', fontSize: 13, margin: '4px 0 0' }}>
            Gemini 直接阅读帖子原文判断情感，不经过 FinBERT 分类
          </p>
        </div>
        <div className="ticker-board-controls">
          <div className="days-selector">
            {[7, 30].map(d => (
              <button
                key={d}
                className={`days-btn ${days === d ? 'active' : ''}`}
                onClick={() => setDays(d)}
              >{d}d</button>
            ))}
          </div>
          <button className="btn-fetch-all" onClick={runAnalysis} disabled={loading}>
            {loading ? '⏳ Analyzing...' : '▶ Run Gemini Analysis'}
          </button>
        </div>
      </div>

      {!ran && !loading && (
        <div style={{ textAlign: 'center', padding: '60px 0', color: '#94a3b8', fontSize: 14 }}>
          点击 ▶ Run Gemini Analysis 开始分析<br />
          <span style={{ fontSize: 12, marginTop: 8, display: 'block' }}>
            每次调用 Gemini API 分析 {DEFAULT_TICKERS.length} 个 ticker，约需 20-40 秒
          </span>
        </div>
      )}

      {loading && (
        <div style={{ textAlign: 'center', padding: '60px 0', color: '#3b82f6', fontSize: 14 }}>
          <div style={{ fontSize: 28, marginBottom: 12 }}>🤖</div>
          Gemini 正在阅读帖子并分析情感...
        </div>
      )}

      {ran && !loading && board.length > 0 && (
        <>
          <div style={{ overflowX: 'auto' }}>
            <table className="lab-table" style={{ marginTop: 16 }}>
              <thead>
                <tr>
                  <th>#</th>
                  <th>Ticker</th>
                  <th>Gemini Score</th>
                  <th>FinBERT Score</th>
                  <th>差值</th>
                  <th>Label</th>
                  <th>Posts</th>
                  <th>Gemini 理由</th>
                </tr>
              </thead>
              <tbody>
                {board.map((item, idx) => {
                  const badge = getLabelBadge(item.label)
                  const scoreColor = getScoreColor(item.score, item.label)
                  const diff = item.score != null && item.finbert_score != null
                    ? round(item.score - item.finbert_score, 3)
                    : null

                  return (
                    <tr key={item.ticker}>
                      <td style={{ color: '#94a3b8', fontWeight: 600 }}>#{idx + 1}</td>
                      <td><strong>{item.ticker}</strong></td>
                      <td style={{ color: scoreColor, fontWeight: 700, fontFamily: 'monospace', fontSize: 15 }}>
                        {item.score != null ? (item.score > 0 ? '+' : '') + item.score.toFixed(3) : 'N/A'}
                      </td>
                      <td style={{ fontFamily: 'monospace', color: '#64748b' }}>
                        {item.finbert_score != null ? (item.finbert_score > 0 ? '+' : '') + item.finbert_score.toFixed(3) : 'N/A'}
                      </td>
                      <td style={{ fontFamily: 'monospace', color: diffColor(item.score, item.finbert_score), fontWeight: 600 }}>
                        {diff != null ? (diff > 0 ? '+' : '') + diff.toFixed(3) : '—'}
                      </td>
                      <td>
                        <span style={{ background: badge.bg, color: badge.color, padding: '2px 10px', borderRadius: 12, fontSize: 12, fontWeight: 600 }}>
                          {badge.text}
                        </span>
                      </td>
                      <td style={{ color: '#94a3b8' }}>{item.total_posts}</td>
                      <td style={{ fontSize: 12, color: '#475569', maxWidth: 260 }}>{item.reason}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          <div className="lab-insight" style={{ marginTop: 20 }}>
            <strong>💡 如何看差值：</strong> 绿色 = Gemini 比 FinBERT 更看多（Gemini 读懂了 FinBERT 忽略的乐观语气）；
            红色 = Gemini 更看空。差值大说明两种方法判断分歧，值得重点关注。
          </div>
        </>
      )}
    </div>
  )
}

function round(val, dec) {
  return Math.round(val * 10 ** dec) / 10 ** dec
}

export default TickerBoardGemini
