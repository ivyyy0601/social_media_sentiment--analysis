import React, { useState, useEffect } from 'react'
import axios from 'axios'
import {
  Chart as ChartJS, CategoryScale, LinearScale, PointElement, LineElement,
  BarElement, Title, Tooltip, Legend, Filler
} from 'chart.js'
import { Line, Bar } from 'react-chartjs-2'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, BarElement, Title, Tooltip, Legend, Filler)

const DEFAULT_TICKERS = ['NVDA', 'AAPL', 'MSFT', 'GOOG', 'AMZN', 'META', 'TSLA', 'AVGO', 'TXN', 'INTC', 'ASML', 'COHR', 'SNDK']

const METHOD_INFO = {
  a: { name: 'Method A — Count', desc: '(pos_count - neg_count) / total  |  丢失置信度信息', color: '#94a3b8' },
  b: { name: 'Method B — Avg Signed ★', desc: 'avg(positive_prob - negative_prob)  |  推荐：保留置信度', color: '#3b82f6' },
  c: { name: 'Method C — High Confidence', desc: 'avg(signed_score) 只用置信度 > 70% 的帖子', color: '#8b5cf6' },
  d: { name: 'Method D — Z-Score', desc: '(score - 全ticker均值) / std  |  相对排名', color: '#f59e0b' },
}

const LABEL_STYLE = {
  bullish: { bg: '#dcfce7', color: '#16a34a', text: 'Bullish 📈' },
  bearish: { bg: '#fee2e2', color: '#dc2626', text: 'Bearish 📉' },
  neutral: { bg: '#f1f5f9', color: '#64748b', text: 'Neutral ➡️' },
}

function Badge({ label }) {
  const s = LABEL_STYLE[label] || LABEL_STYLE.neutral
  return <span style={{ background: s.bg, color: s.color, padding: '2px 8px', borderRadius: 12, fontSize: 11, fontWeight: 600 }}>{s.text}</span>
}

function ScoreCell({ value, method }) {
  if (value == null) return <td>—</td>
  const color = value > 0.05 ? '#16a34a' : value < -0.03 ? '#dc2626' : '#64748b'
  return <td style={{ color, fontWeight: 600, fontFamily: 'monospace' }}>{value > 0 ? '+' : ''}{value.toFixed(4)}</td>
}

export default function SentimentLab({ apiBase }) {
  const [tab, setTab] = useState('comparison')
  const [days, setDays] = useState(7)
  const [compData, setCompData] = useState(null)
  const [compLoading, setCompLoading] = useState(false)
  const [btTicker, setBtTicker] = useState('NVDA')
  const [btDays, setBtDays] = useState(30)
  const [btData, setBtData] = useState(null)
  const [btLoading, setBtLoading] = useState(false)
  const [distData, setDistData] = useState(null)
  const [distLoading, setDistLoading] = useState(false)
  const [sortCol, setSortCol] = useState('method_b')
  const [sortDir, setSortDir] = useState(-1)

  useEffect(() => { loadComparison() }, [days])
  useEffect(() => { if (tab === 'distribution') loadDistribution() }, [tab, days])

  const loadComparison = async () => {
    setCompLoading(true)
    try {
      const res = await axios.get(`${apiBase}/api/v1/lab/method-comparison?days=${days}&tickers=${DEFAULT_TICKERS.join(',')}`)
      if (res.data.success) setCompData(res.data.data)
    } catch (e) { console.error(e) }
    finally { setCompLoading(false) }
  }

  const loadBacktest = async () => {
    setBtLoading(true)
    try {
      const res = await axios.get(`${apiBase}/api/v1/lab/backtest?ticker=${btTicker}&days=${btDays}`)
      if (res.data.success) setBtData(res.data.data)
    } catch (e) { console.error(e) }
    finally { setBtLoading(false) }
  }

  const loadDistribution = async () => {
    setDistLoading(true)
    try {
      const res = await axios.get(`${apiBase}/api/v1/lab/distribution?days=${days}`)
      if (res.data.success) setDistData(res.data.data)
    } catch (e) { console.error(e) }
    finally { setDistLoading(false) }
  }

  const sorted = compData?.rows ? [...compData.rows].sort((a, b) => sortDir * (a[sortCol] - b[sortCol])) : []

  const handleSort = (col) => {
    if (sortCol === col) setSortDir(d => -d)
    else { setSortCol(col); setSortDir(-1) }
  }

  const Th = ({ col, children }) => (
    <th onClick={() => handleSort(col)} style={{ cursor: 'pointer', userSelect: 'none', whiteSpace: 'nowrap' }}>
      {children} {sortCol === col ? (sortDir === -1 ? '↓' : '↑') : ''}
    </th>
  )

  return (
    <div className="sentiment-lab">
      <div className="lab-header card">
        <div>
          <h2>🔬 Sentiment Lab</h2>
          <p style={{ color: '#64748b', margin: 0, fontSize: 14 }}>分析 Sentiment Score 的计算方式、分布和回测表现</p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          {[7, 30].map(d => (
            <button key={d} className={`days-btn ${days === d ? 'active' : ''}`} onClick={() => setDays(d)}>{d}d</button>
          ))}
        </div>
      </div>

      {/* Tabs */}
      <div className="lab-tabs">
        {[
          { key: 'comparison', label: '📊 Method Comparison' },
          { key: 'backtest',   label: '📈 Backtest' },
          { key: 'distribution', label: '📉 Distribution' },
        ].map(t => (
          <button key={t.key} className={`lab-tab ${tab === t.key ? 'active' : ''}`} onClick={() => setTab(t.key)}>
            {t.label}
          </button>
        ))}
      </div>

      {/* ── Tab 1: Method Comparison ── */}
      {tab === 'comparison' && (
        <div className="card lab-section">
          <div style={{ marginBottom: 16 }}>
            <h3 style={{ margin: '0 0 8px' }}>4 种计算方式对比（最近 {days} 天）</h3>
            {Object.entries(METHOD_INFO).map(([k, m]) => (
              <div key={k} style={{ fontSize: 12, color: '#64748b', margin: '2px 0' }}>
                <span style={{ color: m.color, fontWeight: 700 }}>{m.name}</span>：{m.desc}
              </div>
            ))}
            {compData?.stats && (
              <div style={{ marginTop: 8, fontSize: 12, color: '#94a3b8' }}>
                全 ticker 均值: {compData.stats.mean > 0 ? '+' : ''}{compData.stats.mean} | 标准差: {compData.stats.std} | Z-Score 阈值: ±0.5σ
              </div>
            )}
          </div>

          {compLoading ? <div className="lab-loading">Loading...</div> : (
            <div style={{ overflowX: 'auto' }}>
              <table className="lab-table">
                <thead>
                  <tr>
                    <Th col="ticker">Ticker</Th>
                    <Th col="total_posts">Posts</Th>
                    <th>Pos / Neg / Neu</th>
                    <Th col="avg_confidence">Confidence</Th>
                    <Th col="method_a">Method A</Th>
                    <Th col="method_b">Method B ★</Th>
                    <Th col="method_c">Method C</Th>
                    <Th col="method_d">Method D (Z)</Th>
                    <th>Label (B)</th>
                  </tr>
                </thead>
                <tbody>
                  {sorted.map(r => (
                    <tr key={r.ticker}>
                      <td><strong>{r.ticker}</strong></td>
                      <td>{r.total_posts}</td>
                      <td style={{ fontSize: 12 }}>
                        <span style={{ color: '#16a34a' }}>+{r.pos}</span> /
                        <span style={{ color: '#dc2626' }}> -{r.neg}</span> /
                        <span style={{ color: '#94a3b8' }}> {r.neu}</span>
                      </td>
                      <td style={{ fontFamily: 'monospace' }}>{(r.avg_confidence * 100).toFixed(0)}%</td>
                      <ScoreCell value={r.method_a} />
                      <ScoreCell value={r.method_b} />
                      <ScoreCell value={r.method_c} />
                      <ScoreCell value={r.method_d} />
                      <td><Badge label={r.label_b} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <div className="lab-insight">
            <strong>💡 结论：</strong> Method B（推荐）保留了每条帖子的概率置信度，是最准确的聚合方式。
            Method D 的 Z-Score 显示相对排名，适合横向比较 ticker 而非衡量绝对情感强度。
          </div>
        </div>
      )}

      {/* ── Tab 2: Backtest ── */}
      {tab === 'backtest' && (
        <div className="card lab-section">
          <h3 style={{ margin: '0 0 16px' }}>📈 情感分数 vs 价格变化回测</h3>
          <div style={{ display: 'flex', gap: 12, marginBottom: 20, flexWrap: 'wrap', alignItems: 'center' }}>
            <select className="lab-select" value={btTicker} onChange={e => setBtTicker(e.target.value)}>
              {DEFAULT_TICKERS.map(t => <option key={t}>{t}</option>)}
            </select>
            {[7, 14, 30].map(d => (
              <button key={d} className={`days-btn ${btDays === d ? 'active' : ''}`} onClick={() => setBtDays(d)}>{d}d</button>
            ))}
            <button className="btn-fetch-all" onClick={loadBacktest} disabled={btLoading}>
              {btLoading ? '⏳ Loading...' : '▶ Run Backtest'}
            </button>
          </div>

          {btData && (
            <>
              {/* Correlation stats */}
              <div className="lab-stats-row">
                <div className="lab-stat-card">
                  <div className="lab-stat-label">Same-Day Correlation</div>
                  <div className="lab-stat-value" style={{ color: btData.correlation.same_day > 0 ? '#16a34a' : btData.correlation.same_day < 0 ? '#dc2626' : '#94a3b8' }}>
                    {btData.correlation.same_day != null ? btData.correlation.same_day.toFixed(4) : 'N/A'}
                  </div>
                  <div className="lab-stat-sub">情感与当天价格变化</div>
                </div>
                <div className="lab-stat-card">
                  <div className="lab-stat-label">1-Day Lag Correlation</div>
                  <div className="lab-stat-value" style={{ color: btData.correlation.lag_1_day > 0 ? '#16a34a' : btData.correlation.lag_1_day < 0 ? '#dc2626' : '#94a3b8' }}>
                    {btData.correlation.lag_1_day != null ? btData.correlation.lag_1_day.toFixed(4) : 'N/A'}
                  </div>
                  <div className="lab-stat-sub">情感领先价格 1 天</div>
                </div>
                <div className="lab-stat-card" style={{ background: '#dcfce7' }}>
                  <div className="lab-stat-label">情感看涨时，次日均涨</div>
                  <div className="lab-stat-value" style={{ color: '#16a34a' }}>
                    {btData.conditional_avg_next_day.when_bullish != null
                      ? `${btData.conditional_avg_next_day.when_bullish > 0 ? '+' : ''}${btData.conditional_avg_next_day.when_bullish}%`
                      : 'N/A'}
                  </div>
                  <div className="lab-stat-sub">{btData.conditional_avg_next_day.n_bullish_days} 天样本</div>
                </div>
                <div className="lab-stat-card" style={{ background: '#fee2e2' }}>
                  <div className="lab-stat-label">情感看跌时，次日均涨</div>
                  <div className="lab-stat-value" style={{ color: '#dc2626' }}>
                    {btData.conditional_avg_next_day.when_bearish != null
                      ? `${btData.conditional_avg_next_day.when_bearish > 0 ? '+' : ''}${btData.conditional_avg_next_day.when_bearish}%`
                      : 'N/A'}
                  </div>
                  <div className="lab-stat-sub">{btData.conditional_avg_next_day.n_bearish_days} 天样本</div>
                </div>
              </div>

              {/* Dual chart */}
              {btData.daily.length > 0 && (() => {
                const labels = btData.daily.map(d => d.date)
                const sentScores = btData.daily.map(d => d.sentiment)
                const priceChanges = btData.daily.map(d => d.price_change_pct)

                return (
                  <div style={{ marginTop: 24 }}>
                    <div style={{ fontSize: 13, color: '#64748b', marginBottom: 8 }}>
                      蓝色 = 每日情感分数（Method B） | 橙色 = 当日价格变化 %
                    </div>
                    <div style={{ height: 280 }}>
                      <Line
                        data={{
                          labels,
                          datasets: [
                            {
                              label: 'Sentiment Score (B)',
                              data: sentScores,
                              borderColor: '#3b82f6',
                              backgroundColor: 'rgba(59,130,246,0.1)',
                              fill: true, tension: 0.3, pointRadius: 4,
                              yAxisID: 'y',
                            },
                            {
                              label: 'Price Change %',
                              data: priceChanges,
                              borderColor: '#f59e0b',
                              backgroundColor: 'rgba(245,158,11,0.1)',
                              fill: false, tension: 0.3, pointRadius: 4,
                              yAxisID: 'y1',
                            }
                          ]
                        }}
                        options={{
                          responsive: true, maintainAspectRatio: false,
                          plugins: { legend: { position: 'top' } },
                          scales: {
                            y: { position: 'left', title: { display: true, text: 'Sentiment' }, grid: { color: '#f1f5f9' } },
                            y1: { position: 'right', title: { display: true, text: 'Price %' }, grid: { drawOnChartArea: false } },
                          }
                        }}
                      />
                    </div>
                  </div>
                )
              })()}

              <div className="lab-insight" style={{ marginTop: 16 }}>
                <strong>💡 解读：</strong>相关系数接近 0 说明情感与价格关联很弱——这很正常。
                情感分析最好作为辅助过滤条件，而非直接交易信号。
                关注"1-Day Lag"的方向性：如果为正说明情感领先价格，有参考价值。
              </div>
            </>
          )}

          {!btData && !btLoading && (
            <div style={{ color: '#94a3b8', textAlign: 'center', padding: 40 }}>
              选择 Ticker 和天数后点击 ▶ Run Backtest
            </div>
          )}
        </div>
      )}

      {/* ── Tab 3: Distribution ── */}
      {tab === 'distribution' && (
        <div className="card lab-section">
          <h3 style={{ margin: '0 0 16px' }}>📉 Signed Score 分布（最近 {days} 天）</h3>

          {distLoading ? <div className="lab-loading">Loading...</div> : distData && (
            <>
              <div className="lab-stats-row" style={{ marginBottom: 20 }}>
                <div className="lab-stat-card">
                  <div className="lab-stat-label">总帖子数</div>
                  <div className="lab-stat-value">{distData.total_posts}</div>
                </div>
                <div className="lab-stat-card">
                  <div className="lab-stat-label">整体均值</div>
                  <div className="lab-stat-value" style={{ color: distData.overall_avg > 0 ? '#16a34a' : '#dc2626' }}>
                    {distData.overall_avg > 0 ? '+' : ''}{distData.overall_avg}
                  </div>
                </div>
                <div className="lab-stat-card">
                  <div className="lab-stat-label">标准差</div>
                  <div className="lab-stat-value">{distData.overall_std}</div>
                </div>
              </div>

              {/* Histogram */}
              <div style={{ height: 240, marginBottom: 24 }}>
                <Bar
                  data={{
                    labels: distData.histogram.map(b => b.bucket),
                    datasets: [{
                      label: 'Posts',
                      data: distData.histogram.map(b => b.count),
                      backgroundColor: distData.histogram.map(b => {
                        const idx = distData.histogram.indexOf(b)
                        if (idx <= 3) return 'rgba(220,38,38,0.7)'
                        if (idx === 4 || idx === 5) return 'rgba(148,163,184,0.7)'
                        return 'rgba(22,163,74,0.7)'
                      }),
                      borderRadius: 4,
                    }]
                  }}
                  options={{
                    responsive: true, maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: { y: { grid: { color: '#f1f5f9' } } }
                  }}
                />
              </div>

              {/* By source */}
              <h4 style={{ margin: '0 0 12px', color: '#475569', fontSize: 13, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                按来源分析
              </h4>
              <div style={{ overflowX: 'auto' }}>
                <table className="lab-table">
                  <thead>
                    <tr>
                      <th>来源</th>
                      <th>帖子数</th>
                      <th>平均 Signed Score</th>
                      <th>倾向</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(distData.by_source)
                      .sort((a, b) => b[1].count - a[1].count)
                      .map(([src, s]) => (
                        <tr key={src}>
                          <td><strong>{src}</strong></td>
                          <td>{s.count}</td>
                          <td style={{ fontFamily: 'monospace', color: s.avg_signed > 0.05 ? '#16a34a' : s.avg_signed < -0.03 ? '#dc2626' : '#64748b', fontWeight: 600 }}>
                            {s.avg_signed > 0 ? '+' : ''}{s.avg_signed}
                          </td>
                          <td><Badge label={s.avg_signed > 0.05 ? 'bullish' : s.avg_signed < -0.03 ? 'bearish' : 'neutral'} /></td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>

              <div className="lab-insight" style={{ marginTop: 16 }}>
                <strong>💡 注意：</strong> 双峰分布（大量 ±0.8 附近的帖子）是 FinBERT 的特性——
                它判断非常肯定（正面/负面），不确定时才归为 neutral（接近 0）。
                这说明你的数据质量是正常的。
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}
