import React from 'react'
import { Chart as ChartJS, CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend } from 'chart.js'
import { Line } from 'react-chartjs-2'
import EmptyState from './EmptyState'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend)

function SentimentByStockChart({ data, selectedTickers }) {
  if (!data || data.length === 0) {
    return (
      <div className="card">
        <h2>Sentiment by Stock Over Time</h2>
        <EmptyState
          title="No data available"
          message="Select tickers and adjust date range to view trends"
        />
      </div>
    )
  }

  // Transform data for multi-line chart
  const datasets = selectedTickers.map((ticker, idx) => {
    const tickerData = data.filter(d => d.ticker === ticker)
    const colors = [
      'rgb(75, 192, 192)',
      'rgb(255, 99, 132)',
      'rgb(54, 162, 235)',
      'rgb(255, 206, 86)',
      'rgb(153, 102, 255)',
    ]
    const color = colors[idx % colors.length]

    return {
      label: ticker,
      data: tickerData.map(d => d.avg_sentiment),
      borderColor: color,
      backgroundColor: color.replace('rgb', 'rgba').replace(')', ', 0.1)'),
      tension: 0.1,
    }
  })

  const labels = data.length > 0 ? data.map(d => d.date) : []

  const chartData = {
    labels,
    datasets,
  }

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'top',
      },
      title: {
        display: true,
        text: 'Sentiment Trends by Stock',
      },
      tooltip: {
        callbacks: {
          label: (context) => {
            return `${context.dataset.label}: ${context.parsed.y.toFixed(2)}`
          },
        },
      },
    },
    scales: {
      y: {
        beginAtZero: true,
        title: {
          display: true,
          text: 'Average Sentiment Score',
        },
      },
    },
  }

  return (
    <div className="card">
      <h2>Sentiment by Stock Over Time</h2>
      <div className="chart-container">
        <Line data={chartData} options={options} />
      </div>
    </div>
  )
}

export default SentimentByStockChart
