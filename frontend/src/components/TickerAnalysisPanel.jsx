import React, { useState, useEffect } from 'react'
import axios from 'axios'
import {
  Chart as ChartJS,
  CategoryScale, LinearScale, PointElement, LineElement,
  Title, Tooltip, Legend, Filler
} from 'chart.js'
import { Line } from 'react-chartjs-2'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend, Filler)

function TickerAnalysisPanel({ ticker, apiBase, onClose, onViewDashboard }) {
  const [detail, setDetail] = useState(null)
  const [aiAnalysis, setAiAnalysis] = useState('')
  const [aiLoading, setAiLoading] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!ticker) return
    setDetail(null)
    setAiAnalysis('')
    loadDetail()
  }, [ticker])

  const loadDetail = async () => {
    setLoading(true)
    try {
      const res = await axios.get(`${apiBase}/api/v1/ticker-detail/${ticker}?days=7`)
      if (res.data.success) {
        setDetail(res.data.data)
        triggerAiAnalysis(res.data.data)
      }
    } catch (e) {
      console.error('Failed to load ticker detail', e)
    } finally {
      setLoading(false)
    }
  }

  const triggerAiAnalysis = async (data) => {
    setAiLoading(true)
    const { sentiment, price, company, sector, industry, recent_posts = [] } = data
    const p7d = price.price_7d_change_pct != null ? `${price.price_7d_change_pct > 0 ? '+' : ''}${price.price_7d_change_pct}%` : 'N/A'
    const p30d = price.price_30d_change_pct != null ? `${price.price_30d_change_pct > 0 ? '+' : ''}${price.price_30d_change_pct}%` : 'N/A'
    const cap = price.market_cap ? (price.market_cap >= 1e12 ? `$${(price.market_cap/1e12).toFixed(2)}T` : `$${(price.market_cap/1e9).toFixed(1)}B`) : 'N/A'
    const w52pos = price['52w_position_pct'] != null ? `${price['52w_position_pct']}% of 52-week range` : 'N/A'

    // Build post samples grouped by sentiment
    const posSamples = recent_posts.filter(p => p.sentiment === 'positive').slice(0, 5)
    const negSamples = recent_posts.filter(p => p.sentiment === 'negative').slice(0, 5)
    const formatPosts = (posts) => posts.map(p => `  • [${p.source}] ${p.content}`).join('\n') || '  (none)'

    const prompt = `You are analyzing ${ticker} — ${company} (${sector} / ${industry}).

=== SOCIAL MEDIA SENTIMENT (last 7 days) ===
Posts analyzed: ${sentiment.total_posts}
Positive: ${sentiment.positive_pct}% | Neutral: ${sentiment.neutral_pct}% | Negative: ${sentiment.negative_pct}%
Sentiment score: ${sentiment.score ?? 'N/A'} → ${sentiment.label.toUpperCase()}

Sample POSITIVE posts from Reddit/StockTwits/Yahoo News:
${formatPosts(posSamples)}

Sample NEGATIVE posts from Reddit/StockTwits/Yahoo News:
${formatPosts(negSamples)}

=== MARKET DATA (yfinance — same window) ===
Current price: $${price.current_price ?? 'N/A'} (today: ${price.change_today_pct > 0 ? '+' : ''}${price.change_today_pct}%)
7-day change: ${p7d} | 30-day change: ${p30d} | Trend: ${price.trend ?? 'N/A'}
52-week range: $${price['52w_low'] ?? 'N/A'} – $${price['52w_high'] ?? 'N/A'} (at ${w52pos})
Market cap: ${cap} | P/E: ${price.pe_ratio ? price.pe_ratio.toFixed(1) + 'x' : 'N/A'}

=== WHAT TO WRITE ===
Write a cohesive analysis (3-4 sentences) that:
1. Identifies the KEY TOPICS and EVENTS driving the sentiment (based on the actual post content above)
2. Explains whether the price action confirms or contradicts the sentiment
3. Notes any divergence or alignment as a market signal

Then end with:
📊 Decision Brief: ${ticker}
• Sentiment Driver: [What specific topics/events are driving positive or negative sentiment]
• Sentiment Signal: [Bullish/Bearish/Neutral] (score: ${sentiment.score}, ${sentiment.total_posts} posts)
• Price (7-day): $${price.current_price ?? 'N/A'} | ${p7d}
• Alignment: ✅ Aligned / ⚠️ Diverging — [one-line reason]
• Key Insight: [one sentence]
⚠️ Social media sentiment + public market data only — not financial advice.`

    try {
      const res = await axios.post(`${apiBase}/api/v1/agent/chat`, {
        message: prompt,
        history: []
      })
      if (res.data.success) {
        setAiAnalysis(res.data.data.response)
      }
    } catch (e) {
      setAiAnalysis('Unable to generate AI analysis.')
    } finally {
      setAiLoading(false)
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
              <span className={`tap-change ${price.change_today_pct >= 0 ? 'positive' : 'negative'}`}>
                {price.change_today_pct >= 0 ? '+' : ''}{price.change_today_pct}%
              </span>
            </>
          )}
        </div>
        <div className="tap-header-actions">
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
          <h3>📊 Sentiment Analysis <span className="tap-days">Last 7 days</span></h3>
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
              <span className="tap-market-label">7-day Trend</span>
              <span className="tap-market-value" style={{ color: trendColor, fontSize: 18, fontWeight: 700 }}>
                {trendIcon} {price.trend || 'N/A'}
              </span>
            </div>
            <div className="tap-market-item">
              <span className="tap-market-label">7-day Change</span>
              <span className="tap-market-value" style={{ color: price.price_7d_change_pct >= 0 ? '#16a34a' : '#dc2626' }}>
                {price.price_7d_change_pct !== undefined ? `${price.price_7d_change_pct >= 0 ? '+' : ''}${price.price_7d_change_pct}%` : 'N/A'}
              </span>
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
            <h3>📈 Sentiment Score vs. Price — Last 7 Days</h3>
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
        <h3>🤖 AI Analysis</h3>
        {aiLoading ? (
          <div className="tap-ai-loading">
            <div className="ai-typing-dots"><span/><span/><span/></div>
            <span>Analyzing sentiment + market data...</span>
          </div>
        ) : (
          <div className="tap-ai-content">
            {aiAnalysis ? renderText(aiAnalysis) : 'No analysis available.'}
          </div>
        )}
        <button className="tap-refresh-ai" onClick={() => detail && triggerAiAnalysis(detail)} disabled={aiLoading}>
          {aiLoading ? 'Analyzing...' : '🔄 Refresh Analysis'}
        </button>
      </div>

      {/* Recent Posts */}
      {detail.recent_posts?.length > 0 && (
        <div className="tap-posts-section">
          <h3>📰 Recent Posts <span className="tap-days">({detail.recent_posts.length} posts from DB)</span></h3>
          <div className="tap-posts-list">
            {detail.recent_posts.map((post, i) => {
              const sentColor = post.sentiment === 'positive' ? '#16a34a' : post.sentiment === 'negative' ? '#dc2626' : '#94a3b8'
              const sentIcon = post.sentiment === 'positive' ? '📈' : post.sentiment === 'negative' ? '📉' : '➡️'
              const sourceLabel = post.source.replace('yahoo_finance_news', 'Yahoo Finance').replace('google_news', 'Google News').replace('stocktwits', 'StockTwits')
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
      )}
    </div>
  )
}

export default TickerAnalysisPanel
