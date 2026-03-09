import React from 'react'
import { Chart as ChartJS, CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend } from 'chart.js'
import { Bar } from 'react-chartjs-2'
import EmptyState from './EmptyState'

ChartJS.register(CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend)

function StockComparisonChart({ data }) {
  if (!data || data.length === 0) {
    return (
      <div className="card">
        <h2>Stock Comparison</h2>
        <EmptyState
          title="No comparison data"
          message="Select multiple tickers to compare"
        />
      </div>
    )
  }

  const labels = data.map(d => d.ticker)
  const positiveData = data.map(d => d.sentiments?.positive || 0)
  const neutralData = data.map(d => d.sentiments?.neutral || 0)
  const negativeData = data.map(d => d.sentiments?.negative || 0)

  const chartData = {
    labels,
    datasets: [
      {
        label: 'Positive',
        data: positiveData,
        backgroundColor: 'rgba(75, 192, 192, 0.8)',
      },
      {
        label: 'Neutral',
        data: neutralData,
        backgroundColor: 'rgba(54, 162, 235, 0.8)',
      },
      {
        label: 'Negative',
        data: negativeData,
        backgroundColor: 'rgba(255, 99, 132, 0.8)',
      },
    ],
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
        text: 'Sentiment Distribution by Stock',
      },
      tooltip: {
        callbacks: {
          label: (context) => {
            return `${context.dataset.label}: ${context.parsed.y} posts`
          },
        },
      },
    },
    scales: {
      y: {
        stacked: true,
        beginAtZero: true,
        title: {
          display: true,
          text: 'Number of Posts',
        },
      },
      x: {
        stacked: true,
      },
    },
  }

  return (
    <div className="card">
      <h2>Stock Comparison</h2>
      <div className="chart-container">
        <Bar data={chartData} options={options} />
      </div>
    </div>
  )
}

export default StockComparisonChart
