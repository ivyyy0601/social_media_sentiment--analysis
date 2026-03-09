import React from 'react'
import EmptyState from './EmptyState'

function IndustryHeatmap({ data }) {
  if (!data || data.length === 0) {
    return (
      <div className="card">
        <h2>Industry Sentiment Heatmap</h2>
        <EmptyState
          title="No industry data"
          message="Fetch posts to see industry sentiment breakdown"
        />
      </div>
    )
  }

  const getSentimentColor = (sentiments) => {
    if (!sentiments || !sentiments.positive && !sentiments.negative && !sentiments.neutral) {
      return '#eee'
    }

    const total = (sentiments.positive?.count || 0) + (sentiments.neutral?.count || 0) + (sentiments.negative?.count || 0)
    if (total === 0) return '#eee'

    const positiveRatio = (sentiments.positive?.count || 0) / total
    const negativeRatio = (sentiments.negative?.count || 0) / total

    // Calculate color based on sentiment ratio
    if (positiveRatio > 0.6) return '#4ade80' // Green
    if (positiveRatio > 0.4) return '#86efac' // Light green
    if (negativeRatio > 0.6) return '#f87171' // Red
    if (negativeRatio > 0.4) return '#fca5a5' // Light red
    return '#60a5fa' // Blue (neutral)
  }

  const getSentimentLabel = (sentiments) => {
    if (!sentiments) return 'No data'
    
    const positive = sentiments.positive?.count || 0
    const neutral = sentiments.neutral?.count || 0
    const negative = sentiments.negative?.count || 0
    const total = positive + neutral + negative

    if (total === 0) return 'No posts'

    const posPercent = ((positive / total) * 100).toFixed(0)
    const neuPercent = ((neutral / total) * 100).toFixed(0)
    const negPercent = ((negative / total) * 100).toFixed(0)

    return `${posPercent}% Pos / ${neuPercent}% Neu / ${negPercent}% Neg`
  }

  return (
    <div className="card">
      <h2>Industry Sentiment Heatmap</h2>
      <div className="heatmap-grid">
        {data.map(item => (
          <div
            key={item.industry}
            className="heatmap-cell"
            style={{ backgroundColor: getSentimentColor(item.sentiments) }}
            title={`${item.industry}: ${getSentimentLabel(item.sentiments)}`}
          >
            <div className="heatmap-label">{item.industry}</div>
            <div className="heatmap-value">{item.total} posts</div>
            <div className="heatmap-sentiment">{getSentimentLabel(item.sentiments)}</div>
          </div>
        ))}
      </div>
      <div className="heatmap-legend">
        <span className="legend-item">
          <span className="legend-color" style={{ backgroundColor: '#f87171' }}></span>
          Very Negative
        </span>
        <span className="legend-item">
          <span className="legend-color" style={{ backgroundColor: '#fca5a5' }}></span>
          Negative
        </span>
        <span className="legend-item">
          <span className="legend-color" style={{ backgroundColor: '#60a5fa' }}></span>
          Neutral
        </span>
        <span className="legend-item">
          <span className="legend-color" style={{ backgroundColor: '#86efac' }}></span>
          Positive
        </span>
        <span className="legend-item">
          <span className="legend-color" style={{ backgroundColor: '#4ade80' }}></span>
          Very Positive
        </span>
      </div>
    </div>
  )
}

export default IndustryHeatmap
