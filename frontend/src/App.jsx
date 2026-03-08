
import React, { useState, useEffect } from 'react'
import axios from 'axios'
import Dashboard from './components/Dashboard'
import PostsList from './components/PostsList'
import SentimentChart from './components/SentimentChart'
import MarketPulse from './components/MarketPulse'
import StockComparisonChart from './components/StockComparisonChart'
import IndustryHeatmap from './components/IndustryHeatmap'
import VolumeSentimentChart from './components/VolumeSentimentChart'
import TickerFilter from './components/TickerFilter'
import IndustryFilter from './components/IndustryFilter'
import SectorFilter from './components/SectorFilter'
import DateRangeFilter from './components/DateRangeFilter'
import LoadingSpinner from './components/LoadingSpinner'
import ErrorMessage from './components/ErrorMessage'
import ExportMenu from './components/ExportMenu'
import WatchlistPanel from './components/WatchlistPanel'
import FetchControls from './components/FetchControls'

function App() {
  const [posts, setPosts] = useState([])
  const [stats, setStats] = useState(null)
  const [trends, setTrends] = useState([])
  const [marketPulse, setMarketPulse] = useState(null)
  const [industryHeatmap, setIndustryHeatmap] = useState([])
  const [volumeSentiment, setVolumeSentiment] = useState([])
  const [comparisonData, setComparisonData] = useState([])

  const [loading, setLoading] = useState(false)
  const [marketPulseLoading, setMarketPulseLoading] = useState(false)
  const [error, setError] = useState(null)

  // Filter options
  const [tickers, setTickers] = useState([])
  const [industries, setIndustries] = useState([])
  const [sectors, setSectors] = useState([])

  // Selected filters
  const [selectedTickers, setSelectedTickers] = useState([])
  const [selectedIndustries, setSelectedIndustries] = useState([])
  const [selectedSectors, setSelectedSectors] = useState([])
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [granularity, setGranularity] = useState('day')
  const [sentiment, setSentiment] = useState('')

  // View state
  const [activeView, setActiveView] = useState('overview')

  // Use relative URLs in production, localhost in development
  // Empty string means use relative URLs (same domain)
  const API_BASE = import.meta.env.VITE_API_BASE === '' ? '' : (import.meta.env.VITE_API_BASE || 'http://localhost:5000')

  useEffect(() => {
    loadFilterOptions()
    loadData()
  }, [])

  // Reload data when filters change
  useEffect(() => {
    loadData()
  }, [selectedTickers, selectedIndustries, selectedSectors, startDate, endDate, sentiment])

  const loadFilterOptions = async () => {
    try {
      const [tickersRes, industriesRes, sectorsRes] = await Promise.all([
        axios.get(`${API_BASE}/api/v1/tickers`),
        axios.get(`${API_BASE}/api/v1/industries`),
        axios.get(`${API_BASE}/api/v1/sectors`)
      ])

      if (tickersRes.data.success) {
        setTickers(tickersRes.data.data.tickers || [])
      }
      if (industriesRes.data.success) {
        setIndustries(industriesRes.data.data.industries || [])
      }
      if (sectorsRes.data.success) {
        setSectors(sectorsRes.data.data.sectors || [])
      }
    } catch (err) {
      console.error('Error loading filter options:', err)
    }
  }

  const buildFilterParams = () => {
    const params = new URLSearchParams()

    if (selectedTickers.length === 1) {
      params.append('ticker', selectedTickers[0])
    }
    if (selectedIndustries.length === 1) {
      params.append('industry', selectedIndustries[0])
    }
    if (selectedSectors.length === 1) {
      params.append('sector', selectedSectors[0])
    }
    if (startDate) {
      params.append('start_date', startDate)
    }
    if (endDate) {
      params.append('end_date', endDate)
    }
    if (sentiment) {
      params.append('sentiment', sentiment)
    }
    params.append('granularity', granularity)

    return params.toString()
  }

  const loadData = async () => {
    try {
      const filterParams = buildFilterParams()

      const [postsRes, statsRes, trendsRes] = await Promise.all([
        axios.get(`${API_BASE}/api/v1/posts?limit=20&${filterParams}`),
        axios.get(`${API_BASE}/api/v1/stats?${filterParams}`),
        axios.get(`${API_BASE}/api/v1/trends?days=7&${filterParams}`)
      ])

      if (postsRes.data.success) {
        setPosts(postsRes.data.data || [])
      }
      if (statsRes.data.success) {
        setStats(statsRes.data.data)
      }
      if (trendsRes.data.success) {
        setTrends(trendsRes.data.data.trends || [])
      }

      // Load market pulse
      loadMarketPulse()

      // Load additional analytics if filters allow
      loadAdditionalAnalytics()

    } catch (err) {
      console.error('Error loading data:', err)
    }
  }

  const loadMarketPulse = async () => {
    try {
      setMarketPulseLoading(true)
      const params = new URLSearchParams()
      if (startDate) params.append('start_date', startDate)
      if (endDate) params.append('end_date', endDate)

      const response = await axios.get(`${API_BASE}/api/v1/market-pulse?${params}`)
      if (response.data.success) {
        setMarketPulse(response.data.data)
      }
    } catch (err) {
      console.error('Error loading market pulse:', err)
    } finally {
      setMarketPulseLoading(false)
    }
  }

  const loadAdditionalAnalytics = async () => {
    try {
      const params = new URLSearchParams()
      if (startDate) params.append('start_date', startDate)
      if (endDate) params.append('end_date', endDate)

      // Load industry heatmap
      const heatmapRes = await axios.get(`${API_BASE}/api/v1/industry-heatmap?${params}`)
      if (heatmapRes.data.success) {
        setIndustryHeatmap(heatmapRes.data.data.heatmap || [])
      }

      // Load volume-sentiment correlation
      const volumeParams = new URLSearchParams(params)
      if (selectedTickers.length === 1) {
        volumeParams.append('ticker', selectedTickers[0])
      }
      const volumeRes = await axios.get(`${API_BASE}/api/v1/volume-sentiment-correlation?days=14&${volumeParams}`)
      if (volumeRes.data.success) {
        setVolumeSentiment(volumeRes.data.data.correlation || [])
      }

      // Load comparison data if multiple tickers selected
      if (selectedTickers.length > 1) {
        const compParams = new URLSearchParams(params)
        compParams.append('tickers', selectedTickers.join(','))
        const compRes = await axios.get(`${API_BASE}/api/v1/sentiment-comparison?${compParams}`)
        if (compRes.data.success) {
          setComparisonData(compRes.data.data.comparison || [])
        }
      } else {
        setComparisonData([])
      }

    } catch (err) {
      console.error('Error loading additional analytics:', err)
    }
  }

  const fetchNewPosts = async (params = {}) => {
    setLoading(true)
    setError(null)

    try {
      const { limit = 100, start_date, end_date } = params
      const queryParams = new URLSearchParams()
      queryParams.append('max_results', limit)
      if (start_date) queryParams.append('start_date', start_date)
      if (end_date) queryParams.append('end_date', end_date)
      
      const response = await axios.get(`${API_BASE}/api/v1/fetch-posts?${queryParams}`)
      if (response.data.success) {
        await loadData()
        await loadFilterOptions()
      } else {
        setError(response.data.error?.message || 'Failed to fetch posts')
      }
    } catch (err) {
      setError(err.response?.data?.error?.message || err.message || 'Failed to fetch posts')
    } finally {
      setLoading(false)
    }
  }

  const handleClearAllFilters = () => {
    setSelectedTickers([])
    setSelectedIndustries([])
    setSelectedSectors([])
    setStartDate('')
    setEndDate('')
    setSentiment('')
  }

  const hasActiveFilters = selectedTickers.length > 0 ||
                          selectedIndustries.length > 0 ||
                          selectedSectors.length > 0 ||
                          startDate ||
                          endDate ||
                          sentiment

  return (
    <div className="app">
      <header className="header">
        <h1>📈 Finance Sentiment Analysis Dashboard</h1>
        <p>Real-time sentiment analysis of finance-related Reddit posts using FinBERT</p>
      </header>

      <div className="controls">
        <div style={{ display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
          <FetchControls onFetch={fetchNewPosts} loading={loading} />
          <button onClick={loadData} disabled={loading} className="btn-secondary">
            Refresh Data
          </button>
          <WatchlistPanel 
            API_BASE={API_BASE}
            onSelectTickers={(tickers) => setSelectedTickers(tickers)}
          />
          <ExportMenu 
            filters={{
              ticker: selectedTickers,
              industry: selectedIndustries,
              sector: selectedSectors,
              startDate,
              endDate,
              sentiment,
              granularity
            }}
            API_BASE={API_BASE}
          />
          {hasActiveFilters && (
            <button onClick={handleClearAllFilters} className="btn-clear">
              Clear All Filters
            </button>
          )}
        </div>
      </div>

      <ErrorMessage error={error} onRetry={fetchNewPosts} />

      {loading && <LoadingSpinner message="Fetching and analyzing posts..." />}

      {/* Filters Section */}
      <div className="filters-section">
        <h3>Filters</h3>
        <div className="filters-grid">
          <TickerFilter
            tickers={tickers}
            selectedTickers={selectedTickers}
            onChange={setSelectedTickers}
          />
          <IndustryFilter
            industries={industries}
            selectedIndustries={selectedIndustries}
            onChange={setSelectedIndustries}
          />
          <SectorFilter
            sectors={sectors}
            selectedSectors={selectedSectors}
            onChange={setSelectedSectors}
          />
          <DateRangeFilter
            startDate={startDate}
            endDate={endDate}
            onStartDateChange={setStartDate}
            onEndDateChange={setEndDate}
            granularity={granularity}
            onGranularityChange={setGranularity}
          />
          <div className="filter-group">
            <label>Filter by Sentiment</label>
            <select
              value={sentiment}
              onChange={(e) => setSentiment(e.target.value)}
              className="filter-select"
            >
              <option value="">All</option>
              <option value="positive">Positive</option>
              <option value="neutral">Neutral</option>
              <option value="negative">Negative</option>
            </select>
          </div>
        </div>
      </div>

      {/* View Tabs */}
      <div className="view-tabs">
        <button
          className={`tab ${activeView === 'overview' ? 'active' : ''}`}
          onClick={() => setActiveView('overview')}
        >
          Overview
        </button>
        <button
          className={`tab ${activeView === 'analytics' ? 'active' : ''}`}
          onClick={() => setActiveView('analytics')}
        >
          Advanced Analytics
        </button>
        <button
          className={`tab ${activeView === 'posts' ? 'active' : ''}`}
          onClick={() => setActiveView('posts')}
        >
          Posts
        </button>
      </div>

      {/* Content based on active view */}
      {activeView === 'overview' && (
        <>
          <MarketPulse data={marketPulse} loading={marketPulseLoading} />
          <Dashboard stats={stats} onFetchPosts={fetchNewPosts} />
          <SentimentChart trends={trends} title="Sentiment Trends Over Time" />
        </>
      )}

      {activeView === 'analytics' && (
        <>
          {selectedTickers.length > 1 && (
            <StockComparisonChart data={comparisonData} />
          )}
          <IndustryHeatmap data={industryHeatmap} />
          <VolumeSentimentChart data={volumeSentiment} />
        </>
      )}

      {activeView === 'posts' && (
        <PostsList posts={posts} onFetchPosts={fetchNewPosts} />
      )}
    </div>
  )
}

export default App
