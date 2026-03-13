import React, { useState, useEffect } from 'react'
import axios from 'axios'
import {
  Chart as ChartJS,
  CategoryScale, LinearScale, PointElement, LineElement,
  Title, Tooltip, Legend, Filler
} from 'chart.js'
import { Line } from 'react-chartjs-2'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend, Filler)

const SOURCE_LABELS = {
  reddit:        'Reddit',
  yahoo_finance: 'Yahoo Finance',
  google_news:   'Google News',
  nasdaq_news:   'Nasdaq',
  seeking_alpha: 'Seeking Alpha',
  cnbc_news:     'CNBC',
  sec_edgar:     'SEC EDGAR',
  motley_fool:   'Motley Fool',
  hackernews:    'Hacker News',
}

const DAYS_TO_PERIOD = { 1: 'today', 2: 'yesterday', 3: '3days', 7: '7days', 30: '30days' }

const PANEL_PERIODS = [
  { d: 1,  label: '1天'  },
  { d: 2,  label: '2天'  },
  { d: 3,  label: '3天'  },
  { d: 7,  label: '7天'  },
  { d: 30, label: '30天' },
]

function TickerAnalysisPanel({ ticker, days: defaultDays = 7, apiBase, onClose, onViewDashboard }) {
  const [days, setDays] = useState(defaultDays)
  const [detail, setDetail] = useState(null)
  const [loading, setLoading] = useState(true)
  const [sourceFilter, setSourceFilter] = useState('all')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')

  // AI state
  const [aiAnalysis, setAiAnalysis] = useState('')
  const [aiLoading, setAiLoading] = useState(false)
  const [aiHistory, setAiHistory] = useState([])
  const [chatMessages, setChatMessages] = useState([])
  const [chatInput, setChatInput] = useState('')
  const [chatLoading, setChatLoading] = useState(false)

  useEffect(() => {
    if (!ticker) return
    setDetail(null)
    setAiAnalysis('')
    setChatMessages([])
    loadDetail()
  }, [ticker, days])

  const handleDaysChange = (d) => {
    setDays(d)
    setAiAnalysis('')
    setChatMessages([])
  }

  const loadDetail = async () => {
    setLoading(true)
    try {
      const [detailRes] = await Promise.all([
        axios.get(`${apiBase}/api/v1/ticker-detail/${ticker}?days=${days}`)
      ])
      if (detailRes.data.success) {
        setDetail(detailRes.data.data)
      }
    } catch (e) {
      console.error('Failed to load ticker detail', e)
    } finally {
      setLoading(false)
    }
  }

  const runAiPeriod = async () => {
    if (aiLoading) return
    const period = DAYS_TO_PERIOD[days] || '7days'
    setAiAnalysis('')
    setAiHistory([])
    setChatMessages([])
    setAiLoading(true)
    try {
      const res = await axios.post(`${apiBase}/api/v1/agent/db-analysis`, {
        period, ticker, question: '', history: []
      })
      if (res.data.success) {
        setAiAnalysis(res.data.data.response)
        setAiHistory(res.data.data.history)
      }
    } catch {
      setAiAnalysis('❌ 分析失败，请稍后重试。')
    } finally {
      setAiLoading(false)
    }
  }

  const sendAiChat = async () => {
    const text = chatInput.trim()
    if (!text || chatLoading) return
    setChatInput('')
    setChatMessages(prev => [...prev, { role: 'user', content: text }])
    setChatLoading(true)
    try {
      const res = await axios.post(`${apiBase}/api/v1/agent/db-analysis`, {
        period: DAYS_TO_PERIOD[days] || '7days', ticker, question: text, history: aiHistory
      })
      if (res.data.success) {
        setChatMessages(prev => [...prev, { role: 'assistant', content: res.data.data.response }])
        setAiHistory(res.data.data.history)
      }
    } catch {
      setChatMessages(prev => [...prev, { role: 'assistant', content: '❌ 连接失败。' }])
    } finally {
      setChatLoading(false)
    }
  }

  const formatMarketCap = (cap) => {
    if (!cap) return 'N/A'
    if (cap >= 1e12) return `$${(cap / 1e12).toFixed(2)}T`
    if (cap >= 1e9) return `$${(cap / 1e9).toFixed(1)}B`
    return `$${(cap / 1e6).toFixed(0)}M`
  }

  const renderText = (text) => {
    return text.split('\n').map((line, i) => {
      const parts = line.split(/\*\*(.*?)\*\*/g)
      const rendered = parts.map((part, j) =>
        j % 2 === 1 ? <strong key={j}>{part}</strong> : part
      )
      return <span key={i}>{rendered}<br /></span>
    })
  }

  if (loading) {
    return (
      <div className="ticker-analysis-panel" id="ticker-analysis-anchor">
        <div className="tap-loading">Loading {ticker} analysis...</div>
      </div>
    )
  }

  if (!detail) return null

  const { sentiment, price } = detail
  const sentimentColor = sentiment.label === 'bullish' ? '#16a34a' : sentiment.label === 'bearish' ? '#dc2626' : '#94a3b8'
  const trendIcon = price.trend === 'uptrend' ? '↑' : price.trend === 'downtrend' ? '↓' : '→'
  const trendColor = price.trend === 'uptrend' ? '#16a34a' : price.trend === 'downtrend' ? '#dc2626' : '#94a3b8'

  return (
    <div className="ticker-analysis-panel" id="ticker-analysis-anchor">
      {/* Header */}
      <div className="tap-header">
        <div className="tap-title">
          <span className="tap-ticker">{ticker}</span>
          <span className="tap-company">{detail.company}</span>
          <span className="tap-sector">{detail.sector} · {detail.industry}</span>
        </div>
        <div className="tap-price-header">
          {price.current_price && (
            <>
              <span className="tap-price">${price.current_price?.toFixed(2)}</span>
              {(() => {
                const pct = days === 1 ? price.change_today_pct : price.price_7d_change_pct
                const label = PANEL_PERIODS.find(p => p.d === days)?.label || `${days}天`
                return pct != null ? (
                  <span className={`tap-change ${pct >= 0 ? 'positive' : 'negative'}`} title={`${label}涨跌幅`}>
                    {pct >= 0 ? '+' : ''}{pct}%
                  </span>
                ) : null
              })()}
            </>
          )}
        </div>
        <div className="tap-header-actions">
          <div className="days-selector" style={{ display: 'flex', gap: 4 }}>
            {PANEL_PERIODS.map(p => (
              <button
                key={p.d}
                className={`days-btn ${days === p.d ? 'active' : ''}`}
                onClick={() => handleDaysChange(p.d)}
                style={{ fontSize: 12, padding: '4px 10px' }}
              >
                {p.label}
              </button>
            ))}
          </div>
          {onViewDashboard && (
            <button className="tap-dashboard-btn" onClick={() => onViewDashboard(ticker)}>
              View in Dashboard →
            </button>
          )}
          <button className="tap-close" onClick={onClose}>✕</button>
        </div>
      </div>

      <div className="tap-body">
        {/* Sentiment Panel */}
        <div className="tap-section">
          <h3>📊 Sentiment Analysis <span className="tap-days">{PANEL_PERIODS.find(p => p.d === days)?.label || `${days}天`}</span></h3>
          <div className="tap-sentiment-score" style={{ color: sentimentColor }}>
            {sentiment.label === 'bullish' ? '📈 Bullish' : sentiment.label === 'bearish' ? '📉 Bearish' : sentiment.label === 'neutral' ? '➡️ Neutral' : 'No Data'}
            <span className="tap-score-num">{sentiment.score !== null ? (sentiment.score > 0 ? '+' : '') + sentiment.score : 'N/A'}</span>
          </div>

          <div className="tap-bars">
            {[
              { label: 'Positive', value: sentiment.positive, pct: sentiment.positive_pct, color: '#16a34a' },
              { label: 'Neutral', value: sentiment.neutral, pct: sentiment.neutral_pct, color: '#94a3b8' },
              { label: 'Negative', value: sentiment.negative, pct: sentiment.negative_pct, color: '#dc2626' },
            ].map(row => (
              <div key={row.label} className="tap-bar-row">
                <span className="tap-bar-label">{row.label}</span>
                <div className="tap-bar-bg">
                  <div className="tap-bar-fill" style={{ width: `${row.pct}%`, background: row.color }} />
                </div>
                <span className="tap-bar-pct">{row.pct}%</span>
                <span className="tap-bar-count">({row.value})</span>
              </div>
            ))}
          </div>
          <div className="tap-total">{sentiment.total_posts} posts analyzed</div>
        </div>

        {/* Market Data Panel */}
        <div className="tap-section">
          <h3>📈 Market Data <span className="tap-days">via yfinance</span></h3>

          <div className="tap-market-grid">
            <div className="tap-market-item">
              <span className="tap-market-label">{PANEL_PERIODS.find(p => p.d === days)?.label || `${days}天`} Trend</span>
              <span className="tap-market-value" style={{ color: trendColor, fontSize: 18, fontWeight: 700 }}>
                {trendIcon} {price.trend || 'N/A'}
              </span>
            </div>
            <div className="tap-market-item">
              <span className="tap-market-label">{PANEL_PERIODS.find(p => p.d === days)?.label || `${days}天`} Change</span>
              {(() => {
                const pct = days === 1 ? price.change_today_pct : price.price_7d_change_pct
                return (
                  <span className="tap-market-value" style={{ color: pct >= 0 ? '#16a34a' : '#dc2626' }}>
                    {pct != null ? `${pct >= 0 ? '+' : ''}${pct}%` : 'N/A'}
                  </span>
                )
              })()}
            </div>
            <div className="tap-market-item">
              <span className="tap-market-label">Market Cap</span>
              <span className="tap-market-value">{formatMarketCap(price.market_cap)}</span>
            </div>
            <div className="tap-market-item">
              <span className="tap-market-label">P/E Ratio</span>
              <span className="tap-market-value">{price.pe_ratio ? price.pe_ratio.toFixed(1) + 'x' : 'N/A'}</span>
            </div>
          </div>

          {/* 52-week range bar */}
          {price['52w_high'] && price['52w_low'] && (
            <div className="tap-52w">
              <div className="tap-52w-header">
                <span>52-week range</span>
                {price['52w_position_pct'] !== undefined && (
                  <span className="tap-52w-pos">at {price['52w_position_pct']}% of range</span>
                )}
              </div>
              <div className="tap-52w-bar-bg">
                <div
                  className="tap-52w-marker"
                  style={{ left: `${price['52w_position_pct'] || 0}%` }}
                />
              </div>
              <div className="tap-52w-labels">
                <span>${price['52w_low']?.toFixed(2)}</span>
                <span>${price['52w_high']?.toFixed(2)}</span>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Charts */}
      {(sentiment.daily?.length > 0 || price.price_7d?.length > 0) && (() => {
        const sentDates = (sentiment.daily || []).map(d => d.date)
        const priceDates = (price.price_7d || []).map(d => d.date)
        // Use price dates as x-axis (more reliable), fallback to sentiment dates
        const labels = priceDates.length > 0 ? priceDates : sentDates

        const lineOpts = {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false }, tooltip: { mode: 'index', intersect: false } },
          scales: {
            x: { grid: { display: false }, ticks: { maxTicksLimit: 7, font: { size: 11 } } },
            y: { grid: { color: '#f1f5f9' }, ticks: { font: { size: 11 } } }
          }
        }

        const sentScores = sentDates.map(d => {
          const row = sentiment.daily.find(r => r.date === d)
          return row?.score ?? null
        })

        const priceValues = priceDates.map(d => {
          const row = price.price_7d.find(r => r.date === d)
          return row?.close ?? null
        })

        return (
          <div className="tap-charts">
            <h3>📈 Sentiment Score vs. Price — Last {days} Days</h3>
            <div className="tap-charts-grid">
              {sentiment.daily?.length > 0 && (
                <div className="tap-chart-wrap">
                  <div className="tap-chart-label">Sentiment Score (net)</div>
                  <div className="tap-chart-inner">
                    <Line
                      data={{
                        labels: sentDates,
                        datasets: [{
                          data: sentScores,
                          borderColor: '#3b82f6',
                          backgroundColor: 'rgba(59,130,246,0.1)',
                          fill: true,
                          tension: 0.4,
                          pointRadius: 4,
                          pointBackgroundColor: sentScores.map(s =>
                            s === null ? '#94a3b8' : s > 0.1 ? '#16a34a' : s < -0.1 ? '#dc2626' : '#94a3b8'
                          ),
                        }]
                      }}
                      options={{
                        ...lineOpts,
                        scales: {
                          ...lineOpts.scales,
                          y: {
                            ...lineOpts.scales.y,
                            min: -1, max: 1,
                            ticks: { font: { size: 11 }, callback: v => v > 0 ? `+${v.toFixed(1)}` : v.toFixed(1) }
                          }
                        },
                        plugins: {
                          ...lineOpts.plugins,
                          annotation: undefined,
                          tooltip: {
                            callbacks: {
                              label: ctx => `Score: ${ctx.parsed.y > 0 ? '+' : ''}${ctx.parsed.y?.toFixed(3) ?? 'N/A'}`
                            }
                          }
                        }
                      }}
                    />
                  </div>
                </div>
              )}

              {price.price_7d?.length > 0 && (
                <div className="tap-chart-wrap">
                  <div className="tap-chart-label">Stock Price (USD)</div>
                  <div className="tap-chart-inner">
                    <Line
                      data={{
                        labels: priceDates,
                        datasets: [{
                          data: priceValues,
                          borderColor: '#f59e0b',
                          backgroundColor: 'rgba(245,158,11,0.1)',
                          fill: true,
                          tension: 0.4,
                          pointRadius: 4,
                          pointBackgroundColor: '#f59e0b',
                        }]
                      }}
                      options={{
                        ...lineOpts,
                        plugins: {
                          ...lineOpts.plugins,
                          tooltip: {
                            callbacks: {
                              label: ctx => `$${ctx.parsed.y?.toFixed(2) ?? 'N/A'}`
                            }
                          }
                        }
                      }}
                    />
                  </div>
                </div>
              )}
            </div>
          </div>
        )
      })()}

      {/* AI Analysis */}
      <div className="tap-ai-section">
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
          <h3 style={{ margin: 0 }}>🤖 AI Analysis</h3>
          <button
            className="tap-refresh-ai"
            onClick={runAiPeriod}
            disabled={aiLoading}
          >
            {aiLoading ? '⏳ 分析中...' : aiAnalysis ? '🔄 重新分析' : '▶ 开始分析'}
          </button>
          <span style={{ fontSize: 12, color: '#94a3b8' }}>
            当前时段：{days}天
          </span>
        </div>

        {/* Analysis result */}
        {!aiAnalysis && !aiLoading && (
          <div style={{ color: '#94a3b8', fontSize: 13, padding: '8px 0' }}>
            点击「开始分析」分析 {ticker} 过去 {days}天 的情感数据
          </div>
        )}
        {aiLoading && (
          <div className="tap-ai-loading">
            <div className="ai-typing-dots"><span/><span/><span/></div>
            <span>分析中...</span>
          </div>
        )}
        {aiAnalysis && !aiLoading && (
          <div className="tap-ai-content">{renderText(aiAnalysis)}</div>
        )}

        {/* Chat follow-up */}
        {(aiAnalysis || chatMessages.length > 0) && (
          <div style={{ marginTop: 16, borderTop: '1px solid #f1f5f9', paddingTop: 12 }}>
            <div style={{ fontSize: 13, fontWeight: 600, color: '#475569', marginBottom: 8 }}>💬 追问</div>
            {chatMessages.map((m, i) => (
              <div key={i} className={`ai-message ai-message-${m.role}`} style={{ marginBottom: 8 }}>
                <div className="ai-message-avatar">{m.role === 'user' ? '👤' : '🤖'}</div>
                <div className="ai-message-bubble">{renderText(m.content)}</div>
              </div>
            ))}
            {chatLoading && (
              <div className="ai-message ai-message-assistant">
                <div className="ai-message-avatar">🤖</div>
                <div className="ai-message-bubble"><div className="ai-typing-dots"><span/><span/><span/></div></div>
              </div>
            )}
            <div className="ai-chat-input-row" style={{ marginTop: 8 }}>
              <textarea
                className="ai-chat-input"
                value={chatInput}
                onChange={e => setChatInput(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendAiChat() } }}
                placeholder="追问..."
                rows={2}
                disabled={chatLoading}
              />
              <button className="ai-chat-send" onClick={sendAiChat} disabled={!chatInput.trim() || chatLoading}>
                {chatLoading ? '⏳' : '➤'}
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Recent Posts */}
      {detail.recent_posts?.length > 0 && (() => {
        const allPosts = detail.recent_posts
        const sources = ['all', ...Array.from(new Set(allPosts.map(p => p.source).filter(Boolean)))]

        let filtered = sourceFilter === 'all' ? allPosts : allPosts.filter(p => p.source === sourceFilter)
        if (dateFrom) filtered = filtered.filter(p => p.date && p.date >= dateFrom)
        if (dateTo)   filtered = filtered.filter(p => p.date && p.date <= dateTo)

        return (
          <div className="tap-posts-section">
            <div className="tap-posts-header">
              <h3>📰 Recent Posts <span className="tap-days">({filtered.length} / {allPosts.length})</span></h3>

              {/* Date range pickers */}
              <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap', marginBottom: 6 }}>
                <span style={{ fontSize: 12, color: '#64748b' }}>日期：</span>
                <input
                  type="date"
                  value={dateFrom}
                  onChange={e => setDateFrom(e.target.value)}
                  style={{ fontSize: 12, padding: '3px 6px', borderRadius: 6, border: '1px solid #e2e8f0' }}
                />
                <span style={{ fontSize: 12, color: '#94a3b8' }}>至</span>
                <input
                  type="date"
                  value={dateTo}
                  onChange={e => setDateTo(e.target.value)}
                  style={{ fontSize: 12, padding: '3px 6px', borderRadius: 6, border: '1px solid #e2e8f0' }}
                />
                {(dateFrom || dateTo) && (
                  <button
                    onClick={() => { setDateFrom(''); setDateTo('') }}
                    style={{ fontSize: 11, color: '#94a3b8', background: 'none', border: 'none', cursor: 'pointer' }}
                  >
                    ✕ 清除
                  </button>
                )}
              </div>

              {/* Source filters */}
              <div className="tap-source-filters">
                {sources.map(src => (
                  <button
                    key={src}
                    className={`tap-source-btn ${sourceFilter === src ? 'active' : ''}`}
                    onClick={() => setSourceFilter(src)}
                  >
                    {src === 'all' ? 'All Sources' : (SOURCE_LABELS[src] || src)}
                  </button>
                ))}
              </div>
            </div>
            <div className="tap-posts-list">
              {filtered.map((post, i) => {
                const sentColor = post.sentiment === 'positive' ? '#16a34a' : post.sentiment === 'negative' ? '#dc2626' : '#94a3b8'
                const sentIcon = post.sentiment === 'positive' ? '📈' : post.sentiment === 'negative' ? '📉' : '➡️'
                const sourceLabel = SOURCE_LABELS[post.source] || post.source
                return (
                  <div key={i} className="tap-post-item">
                    <div className="tap-post-left">
                      <span className="tap-post-icon">{sentIcon}</span>
                    </div>
                    <div className="tap-post-body">
                      {post.url ? (
                        <a className="tap-post-title" href={post.url} target="_blank" rel="noreferrer">
                          {post.content}
                        </a>
                      ) : (
                        <span className="tap-post-title">{post.content}</span>
                      )}
                      <div className="tap-post-meta">
                        <span className="tap-post-source">{sourceLabel}</span>
                        <span className="tap-post-date">{post.date}</span>
                        <span className="tap-post-sentiment" style={{ color: sentColor }}>
                          {post.sentiment}
                        </span>
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        )
      })()}
    </div>
  )
}

export default TickerAnalysisPanel
