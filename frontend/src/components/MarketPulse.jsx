import React from 'react'
import { Chart as ChartJS, ArcElement, Tooltip, Legend } from 'chart.js'
import { Pie } from 'react-chartjs-2'
import LoadingSpinner from './LoadingSpinner'
import EmptyState from './EmptyState'

ChartJS.register(ArcElement, Tooltip, Legend)

function MarketPulse({ data, loading }) {
  if (loading) {
    return <LoadingSpinner message="Loading market pulse..." />
  }

  if (!data || !data.most_discussed_stocks || data.most_discussed_stocks.length === 0) {
    return (
      <EmptyState
        icon="📊"
        title="No market data available"
        message="Fetch posts to see market pulse data"
      />
    )
  }

  const {
    most_discussed_stocks,
    most_positive_stocks,
    most_negative_stocks,
    sentiment_by_sector,
    overall_market_sentiment
  } = data

  // -----------------------------
  // Helpers for signed sentiment (-1 ~ 1)
  // -----------------------------
  const formatSigned = (v) => (v === null || v === undefined ? 'N/A' : Number(v).toFixed(2))

  const scoreClass = (v) => {
    if (v === null || v === undefined) return 'neutral'
    if (v > 0.05) return 'positive'
    if (v < -0.05) return 'negative'
    return 'neutral'
  }

  const sentimentTag = (v) => {
    if (v === null || v === undefined) return { text: 'N/A', cls: 'neutral' }
    if (v > 0.05) return { text: 'Bullish', cls: 'positive' }
    if (v < -0.05) return { text: 'Bearish', cls: 'negative' }
    return { text: 'Neutral', cls: 'neutral' }
  }

  // -----------------------------
  // Overall sentiment distribution (counts by label)
  // -----------------------------
  const overallDist = overall_market_sentiment?.distribution || {}
  const overallData = {
    labels: ['Positive', 'Neutral', 'Negative'],
    datasets: [
      {
        data: [overallDist.positive || 0, overallDist.neutral || 0, overallDist.negative || 0],
        backgroundColor: [
          'rgba(75, 192, 192, 0.8)',
          'rgba(54, 162, 235, 0.8)',
          'rgba(255, 99, 132, 0.8)',
        ],
        borderColor: [
          'rgba(75, 192, 192, 1)',
          'rgba(54, 162, 235, 1)',
          'rgba(255, 99, 132, 1)',
        ],
        borderWidth: 1,
      },
    ],
  }

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'bottom',
      },
    },
  }

  // Optional: sector data (you compute it; keep it for later if you add a chart)
  const sectorLabels = Object.keys(sentiment_by_sector || {})
  const sectorData = {
    labels: sectorLabels,
    datasets: [
      {
        label: 'Positive',
        data: sectorLabels.map(s => sentiment_by_sector[s]?.positive || 0),
        backgroundColor: 'rgba(75, 192, 192, 0.6)',
      },
      {
        label: 'Neutral',
        data: sectorLabels.map(s => sentiment_by_sector[s]?.neutral || 0),
        backgroundColor: 'rgba(54, 162, 235, 0.6)',
      },
      {
        label: 'Negative',
        data: sectorLabels.map(s => sentiment_by_sector[s]?.negative || 0),
        backgroundColor: 'rgba(255, 99, 132, 0.6)',
      },
    ],
  }

  // signed mean direction for overall
  const overallSigned = overall_market_sentiment?.average_score
  const overallTag = sentimentTag(overallSigned)

  return (
    <div className="market-pulse">
      <h2>📊 Market Pulse</h2>

      <div className="pulse-grid">
        {/* Overall Market Sentiment */}
        <div className="pulse-card overall-sentiment">
          <h3>Overall Market Sentiment</h3>



          <div className="chart-wrapper-small">
            <Pie data={overallData} options={chartOptions} />
          </div>
        </div>

        {/* Most Discussed */}
        <div className="pulse-card">
          <h3>🔥 Most Discussed</h3>
          <div className="stock-list">
            {most_discussed_stocks.slice(0, 5).map((stock, idx) => (
              <div key={stock.ticker} className="stock-item">
                <span className="rank">{idx + 1}</span>
                <span className="ticker">{stock.ticker}</span>
                <span className="count">{stock.post_count} posts</span>
                <span className={`score ${scoreClass(stock.avg_sentiment_score)}`}>
                  {formatSigned(stock.avg_sentiment_score)}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Most Positive */}
        <div className="pulse-card">
          <h3>📈 Most Positive</h3>
          <div className="stock-list">
            {most_positive_stocks.slice(0, 5).map((stock, idx) => (
              <div key={stock.ticker} className="stock-item">
                <span className="rank">{idx + 1}</span>
                <span className="ticker">{stock.ticker}</span>
                <span className="count">{stock.post_count} posts</span>
                <span className={`score ${scoreClass(stock.avg_sentiment)}`}>
                  {formatSigned(stock.avg_sentiment)}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Most Negative */}
        <div className="pulse-card">
          <h3>📉 Most Negative</h3>
          <div className="stock-list">
            {most_negative_stocks.slice(0, 5).map((stock, idx) => (
              <div key={stock.ticker} className="stock-item">
                <span className="rank">{idx + 1}</span>
                <span className="ticker">{stock.ticker}</span>
                <span className="count">{stock.post_count} posts</span>
                <span className={`score ${scoreClass(stock.avg_sentiment)}`}>
                  {formatSigned(stock.avg_sentiment)}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* 你之后如果要加 sector 图，可以在这里渲染 sectorData */}
      {/* <div className="pulse-card">
        <h3>Sector Sentiment</h3>
        <div className="chart-wrapper">
          <Bar data={sectorData} options={...} />
        </div>
      </div> */}
    </div>
  )
}

export default MarketPulse
