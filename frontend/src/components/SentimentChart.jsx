import React from 'react'
import { Chart as ChartJS, CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend } from 'chart.js'
import { Bar } from 'react-chartjs-2'
import EmptyState from './EmptyState'

ChartJS.register(CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend)

function SentimentChart({ trends, title = 'Sentiment Trends' }) {
  if (!trends || trends.length === 0) {
    return (
      <div className="card">
        <h2>{title}</h2>
        <EmptyState
          title="No trend data available"
          message="Adjust filters or fetch new posts to see trends"
        />
      </div>
    )
  }

  // Helper function to format date labels
  const formatDateLabel = (dateStr) => {
    // Check if it's a week format (e.g., "2026-w02")
    const weekMatch = dateStr.match(/^(\d{4})-w(\d{2})$/)
    if (weekMatch) {
      const year = parseInt(weekMatch[1])
      const week = parseInt(weekMatch[2])
      
      // Calculate the date range for the week
      // ISO week starts on Monday
      const jan4 = new Date(year, 0, 4)
      const monday = new Date(jan4)
      monday.setDate(jan4.getDate() - (jan4.getDay() || 7) + 1 + (week - 1) * 7)
      
      const sunday = new Date(monday)
      sunday.setDate(monday.getDate() + 6)
      
      // Validate dates
      if (isNaN(monday.getTime()) || isNaN(sunday.getTime())) {
        return dateStr
      }
      
      const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
      const startMonth = monthNames[monday.getMonth()]
      const endMonth = monthNames[sunday.getMonth()]
      
      if (monday.getMonth() === sunday.getMonth()) {
        return `${startMonth} ${monday.getDate()}-${sunday.getDate()}, ${year}`
      } else {
        return `${startMonth} ${monday.getDate()}-${endMonth} ${sunday.getDate()}, ${year}`
      }
    }
    
    // For daily format, convert to human-readable
    try {
      const date = new Date(dateStr)
      // Validate date
      if (isNaN(date.getTime())) {
        return dateStr
      }
      const monthNames = ['January', 'February', 'March', 'April', 'May', 'June', 
                          'July', 'August', 'September', 'October', 'November', 'December']
      return `${monthNames[date.getMonth()]} ${date.getDate()}, ${date.getFullYear()}`
    } catch {
      return dateStr
    }
  }

  const labels = trends.map(t => t.date).reverse()
  const positiveData = trends.map(t => t.positive || 0).reverse()
  const negativeData = trends.map(t => t.negative || 0).reverse()
  const neutralData = trends.map(t => t.neutral || 0).reverse()

  const data = {
    labels,
    datasets: [
      {
        label: 'Positive',
        data: positiveData,
        backgroundColor: 'rgba(75, 192, 192, 0.6)',
        borderColor: 'rgba(75, 192, 192, 1)',
        borderWidth: 1,
      },
      {
        label: 'Negative',
        data: negativeData,
        backgroundColor: 'rgba(255, 99, 132, 0.6)',
        borderColor: 'rgba(255, 99, 132, 1)',
        borderWidth: 1,
      },
      {
        label: 'Neutral',
        data: neutralData,
        backgroundColor: 'rgba(54, 162, 235, 0.6)',
        borderColor: 'rgba(54, 162, 235, 1)',
        borderWidth: 1,
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
        text: title,
      },
      tooltip: {
        callbacks: {
          title: (context) => {
            const index = context[0].dataIndex
            const dateStr = labels[index]
            return formatDateLabel(dateStr)
          },
          label: (context) => {
            return `${context.dataset.label}: ${context.parsed.y} posts`
          },
        },
      },
    },
    scales: {
      y: {
        beginAtZero: true,
        title: {
          display: true,
          text: 'Number of Posts',
        },
      },
    },
  }

  return (
    <div className="card">
      <h2>{title}</h2>
      <div className="chart-container">
        <Bar data={data} options={options} />
      </div>
    </div>
  )
}

export default SentimentChart
