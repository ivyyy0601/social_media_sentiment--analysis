import React from 'react'
import { Chart as ChartJS, CategoryScale, LinearScale, PointElement, LineElement, BarElement, Title, Tooltip, Legend } from 'chart.js'
import { Chart } from 'react-chartjs-2'
import EmptyState from './EmptyState'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, BarElement, Title, Tooltip, Legend)

function VolumeSentimentChart({ data }) {
  if (!data || data.length === 0) {
    return (
      <div className="card">
        <h2>Volume & Sentiment Correlation</h2>
        <EmptyState
          title="No correlation data"
          message="Adjust date range to view volume and sentiment trends"
        />
      </div>
    )
  }

  const labels = data.map(d => d.date).reverse()
  const volumes = data.map(d => d.volume).reverse()
  const sentiments = data.map(d => d.avg_sentiment).reverse()

  const chartData = {
    labels,
    datasets: [
      {
        type: 'bar',
        label: 'Post Volume',
        data: volumes,
        backgroundColor: 'rgba(54, 162, 235, 0.5)',
        borderColor: 'rgba(54, 162, 235, 1)',
        borderWidth: 1,
        yAxisID: 'y',
      },
      {
        type: 'line',
        label: 'Average Sentiment',
        data: sentiments,
        borderColor: 'rgba(255, 99, 132, 1)',
        backgroundColor: 'rgba(255, 99, 132, 0.1)',
        borderWidth: 2,
        yAxisID: 'y1',
        tension: 0.1,
      },
    ],
  }

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: {
      mode: 'index',
      intersect: false,
    },
    plugins: {
      legend: {
        position: 'top',
      },
      title: {
        display: true,
        text: 'Post Volume vs Sentiment Over Time',
      },
      tooltip: {
        callbacks: {
          label: (context) => {
            if (context.datasetIndex === 0) {
              return `Volume: ${context.parsed.y} posts`
            } else {
              return `Avg Sentiment: ${context.parsed.y.toFixed(2)}`
            }
          },
        },
      },
    },
    scales: {
      y: {
        type: 'linear',
        display: true,
        position: 'left',
        beginAtZero: true,
        title: {
          display: true,
          text: 'Post Volume',
        },
      },
      y1: {
        type: 'linear',
        display: true,
        position: 'right',
        min: -1,
        max: 1,
        title: {
          display: true,
          text: 'Average Sentiment',
        },
        grid: {
          drawOnChartArea: false,
        },
      },
    },
  }

  return (
    <div className="card">
      <h2>Volume & Sentiment Correlation</h2>
      <div className="chart-container">
        <Chart type="bar" data={chartData} options={options} />
      </div>
    </div>
  )
}

export default VolumeSentimentChart
