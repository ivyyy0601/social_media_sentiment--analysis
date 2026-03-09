import React from 'react'
import EmptyState from './EmptyState'
import Tooltip from './Tooltip'

function Dashboard({ stats, onFetchPosts }) {
  if (!stats || !stats.by_sentiment) {
    return (
      <div className="dashboard">
        <div className="card">
          <h2>
            Statistics
            <Tooltip text="Overall sentiment distribution of all analyzed posts. Positive indicates optimistic financial sentiment, Negative indicates pessimistic sentiment, and Neutral represents factual or balanced content." />
          </h2>
          <EmptyState
            icon="📊"
            title="No data available yet"
            message="Click 'Fetch New Posts' to get started!"
            actionButton={
              onFetchPosts && (
                <button onClick={onFetchPosts} className="btn-primary">
                  Fetch New Posts
                </button>
              )
            }
          />
        </div>
      </div>
    )
  }

  const { total, by_sentiment } = stats

  return (
    <div className="dashboard">
      <div className="card">
        <h2>
          Sentiment Overview
          <Tooltip text="Overall sentiment distribution of all analyzed posts. Sentiment scores are calculated using FinBERT, a specialized AI model for financial text analysis." />
        </h2>
        <div className="stats-grid">
          <div className="stat-item positive">
            <div className="stat-icon">📈</div>
            <div className="label">Positive</div>
            <div className="value">{by_sentiment.positive?.count || 0}</div>
            <div className="percentage">{by_sentiment.positive?.percentage || 0}%</div>
          </div>
          <div className="stat-item negative">
            <div className="stat-icon">📉</div>
            <div className="label">Negative</div>
            <div className="value">{by_sentiment.negative?.count || 0}</div>
            <div className="percentage">{by_sentiment.negative?.percentage || 0}%</div>
          </div>
          <div className="stat-item neutral">
            <div className="stat-icon">➖</div>
            <div className="label">Neutral</div>
            <div className="value">{by_sentiment.neutral?.count || 0}</div>
            <div className="percentage">{by_sentiment.neutral?.percentage || 0}%</div>
          </div>
        </div>
        <div className="total-posts">
          <strong>Total Posts Analyzed:</strong> {total}
        </div>
      </div>
    </div>
  )
}

export default Dashboard
