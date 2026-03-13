import React, { useState, useRef, useEffect } from 'react'
import axios from 'axios'

const PERIODS = [
  { key: 'today',     label: '1天',  days: 1  },
  { key: 'yesterday', label: '2天',  days: 2  },
  { key: '3days',     label: '3天',  days: 3  },
  { key: '7days',     label: '7天',  days: 7  },
  { key: '30days',    label: '30天', days: 30 },
]

function AIAnalyst({ apiBase }) {
  const [activePeriod, setActivePeriod] = useState(null)
  const [analysis, setAnalysis] = useState('')
  const [analysisLoading, setAnalysisLoading] = useState(false)
  const [dbStats, setDbStats] = useState(null)

  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [chatLoading, setChatLoading] = useState(false)
  const [history, setHistory] = useState([])
  const messagesEndRef = useRef(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, chatLoading])

  const runAnalysis = async (periodKey) => {
    if (analysisLoading) return
    setActivePeriod(periodKey)
    setAnalysis('')
    setAnalysisLoading(true)

    try {
      const res = await axios.post(`${apiBase}/api/v1/agent/db-analysis`, {
        period: periodKey,
        question: '',
        history: [],
      })
      if (res.data.success) {
        setAnalysis(res.data.data.response)
        setDbStats(res.data.data.db_stats)
        setHistory(res.data.data.history)
      }
    } catch {
      setAnalysis('❌ 分析失败，请稍后重试。')
    } finally {
      setAnalysisLoading(false)
    }
  }

  const sendMessage = async () => {
    const text = input.trim()
    if (!text || chatLoading) return
    setInput('')
    setMessages(prev => [...prev, { role: 'user', content: text }])
    setChatLoading(true)

    try {
      const res = await axios.post(`${apiBase}/api/v1/agent/db-analysis`, {
        period: activePeriod || '7days',
        question: text,
        history,
      })
      if (res.data.success) {
        setMessages(prev => [...prev, { role: 'assistant', content: res.data.data.response }])
        setHistory(res.data.data.history)
      }
    } catch {
      setMessages(prev => [...prev, { role: 'assistant', content: '❌ 连接失败，请稍后重试。' }])
    } finally {
      setChatLoading(false)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  const renderText = (text) => {
    return text.split('\n').map((line, i) => {
      const parts = line.split(/\*\*(.*?)\*\*/g)
      const rendered = parts.map((part, j) =>
        j % 2 === 1 ? <strong key={j}>{part}</strong> : part
      )
      return <span key={i}>{rendered}<br /></span>
    })
  }

  return (
    <div className="ai-analyst">

      {/* ── Section 1: Period Analysis ── */}
      <div className="card ai-brief-card">
        <div className="ai-brief-header">
          <h2>📊 情感分析报告</h2>
          {dbStats && (
            <span style={{ fontSize: 12, color: '#94a3b8' }}>
              {dbStats.period} · {dbStats.total_posts} 条帖子
            </span>
          )}
        </div>

        {/* Period buttons */}
        <div style={{ display: 'flex', gap: 8, padding: '0 0 16px', flexWrap: 'wrap' }}>
          {PERIODS.map(p => (
            <button
              key={p.key}
              className={`days-btn ${activePeriod === p.key ? 'active' : ''}`}
              onClick={() => runAnalysis(p.key)}
              disabled={analysisLoading}
              style={{ fontSize: 13, padding: '6px 16px' }}
            >
              {analysisLoading && activePeriod === p.key ? '⏳' : p.label}
            </button>
          ))}
        </div>

        {/* Analysis result */}
        {!activePeriod && !analysisLoading && (
          <div style={{ color: '#94a3b8', fontSize: 14, padding: '20px 0', textAlign: 'center' }}>
            点击上方时间段按钮开始分析
          </div>
        )}

        {analysisLoading && (
          <div className="ai-brief-loading">
            <div className="ai-typing-dots"><span /><span /><span /></div>
            <p>正在从数据库提取数据并分析...</p>
          </div>
        )}

        {analysis && !analysisLoading && (
          <div className="ai-brief-content">
            {renderText(analysis)}
          </div>
        )}
      </div>

      {/* ── Section 2: Follow-up Chat ── */}
      <div className="card ai-chat-card">
        <div className="ai-chat-header">
          <h2>💬 追问</h2>
          {messages.length > 0 && (
            <button className="btn-clear-chat" onClick={() => { setMessages([]); setHistory([]) }}>
              清空
            </button>
          )}
        </div>

        <div className="ai-chat-messages" style={{ minHeight: 80 }}>
          {messages.length === 0 && (
            <div className="ai-chat-empty" style={{ padding: '16px 0' }}>
              <p>对上方报告有疑问？或者想问别的内容？直接输入。</p>
            </div>
          )}

          {messages.map((msg, i) => (
            <div key={i} className={`ai-message ai-message-${msg.role}`}>
              <div className="ai-message-avatar">{msg.role === 'user' ? '👤' : '🤖'}</div>
              <div className="ai-message-bubble">{renderText(msg.content)}</div>
            </div>
          ))}

          {chatLoading && (
            <div className="ai-message ai-message-assistant">
              <div className="ai-message-avatar">🤖</div>
              <div className="ai-message-bubble ai-message-loading">
                <div className="ai-typing-dots"><span /><span /><span /></div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <div className="ai-chat-input-row">
          <textarea
            className="ai-chat-input"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="输入问题… (Enter 发送)"
            rows={2}
            disabled={chatLoading}
          />
          <button
            className="ai-chat-send"
            onClick={sendMessage}
            disabled={!input.trim() || chatLoading}
          >
            {chatLoading ? '⏳' : '➤'}
          </button>
        </div>
      </div>

    </div>
  )
}

export default AIAnalyst
