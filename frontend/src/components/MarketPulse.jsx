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

  // Prepare sector sentiment chart data
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

  // Overall sentiment distribution
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

  return (
    <div className="market-pulse">
      <h2>📊 Market Pulse</h2>
      
      <div className="pulse-grid">
        {/* Overall Market Sentiment */}
        <div className="pulse-card overall-sentiment">
          <h3>Overall Market Sentiment</h3>
          <div className="sentiment-score-large">
            {overall_market_sentiment?.average_score !== undefined 
              ? overall_market_sentiment.average_score.toFixed(2) 
              : 'N/A'}
          </div>
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
                <span className={`score ${stock.avg_sentiment_score != null && stock.avg_sentiment_score >= 0 ? 'positive' : 'negative'}`}>
                  {stock.avg_sentiment_score != null ? stock.avg_sentiment_score.toFixed(2) : 'N/A'}
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
                <span className="score positive">{stock.avg_sentiment.toFixed(2)}</span>
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
                <span className="score negative">{stock.avg_sentiment.toFixed(2)}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

export default MarketPulse