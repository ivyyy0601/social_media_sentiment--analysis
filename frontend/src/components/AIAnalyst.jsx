import React, { useState, useEffect, useRef } from 'react'
import axios from 'axios'

function AIAnalyst({ apiBase }) {
  const [brief, setBrief] = useState(null)
  const [briefLoading, setBriefLoading] = useState(true)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [chatLoading, setChatLoading] = useState(false)
  const [history, setHistory] = useState([])
  const messagesEndRef = useRef(null)

  useEffect(() => {
    loadBrief()
  }, [])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, chatLoading])

  const loadBrief = async () => {
    try {
      setBriefLoading(true)
      const res = await axios.get(`${apiBase}/api/v1/agent/brief`)
      if (res.data.success) {
        setBrief(res.data.data.brief)
      }
    } catch {
      setBrief('Unable to load market brief. Please check your API configuration.')
    } finally {
      setBriefLoading(false)
    }
  }

  const sendMessage = async () => {
    const text = input.trim()
    if (!text || chatLoading) return

    setInput('')
    const userMsg = { role: 'user', content: text }
    setMessages(prev => [...prev, userMsg])
    setChatLoading(true)

    try {
      const res = await axios.post(`${apiBase}/api/v1/agent/chat`, {
        message: text,
        history
      })
      if (res.data.success) {
        const { response, history: newHistory } = res.data.data
        setMessages(prev => [...prev, { role: 'assistant', content: response }])
        setHistory(newHistory)
      }
    } catch {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: '❌ Error connecting to AI Agent. Please try again.'
      }])
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

  const clearChat = () => {
    setMessages([])
    setHistory([])
  }

  const renderText = (text) => {
    // Simple markdown-like rendering
    return text
      .split('\n')
      .map((line, i) => {
        // Bold: **text**
        const parts = line.split(/\*\*(.*?)\*\*/g)
        const rendered = parts.map((part, j) =>
          j % 2 === 1 ? <strong key={j}>{part}</strong> : part
        )
        return <span key={i}>{rendered}<br /></span>
      })
  }

  return (
    <div className="ai-analyst">
      {/* Market Brief */}
      <div className="card ai-brief-card">
        <div className="ai-brief-header">
          <h2>🤖 AI Market Brief</h2>
          <button
            className="btn-refresh-brief"
            onClick={loadBrief}
            disabled={briefLoading}
            title="Refresh brief"
          >
            {briefLoading ? '⏳' : '🔄'}
          </button>
        </div>

        {briefLoading ? (
          <div className="ai-brief-loading">
            <div className="ai-typing-dots">
              <span></span><span></span><span></span>
            </div>
            <p>Analyzing market sentiment...</p>
          </div>
        ) : (
          <div className="ai-brief-content">
            {renderText(brief || 'No brief available.')}
          </div>
        )}
      </div>

      {/* Chat */}
      <div className="card ai-chat-card">
        <div className="ai-chat-header">
          <h2>💬 Ask the Analyst</h2>
          {messages.length > 0 && (
            <button className="btn-clear-chat" onClick={clearChat}>
              Clear
            </button>
          )}
        </div>

        <div className="ai-chat-messages">
          {messages.length === 0 && (
            <div className="ai-chat-empty">
              <p>Ask me anything about market sentiment.</p>
              <div className="ai-suggestions">
                {['What stocks are trending?', 'Analyze NVDA', 'Which sector is most bullish?'].map(s => (
                  <button
                    key={s}
                    className="ai-suggestion-chip"
                    onClick={() => { setInput(s); }}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg, i) => (
            <div key={i} className={`ai-message ai-message-${msg.role}`}>
              <div className="ai-message-avatar">
                {msg.role === 'user' ? '👤' : '🤖'}
              </div>
              <div className="ai-message-bubble">
                {renderText(msg.content)}
              </div>
            </div>
          ))}

          {chatLoading && (
            <div className="ai-message ai-message-assistant">
              <div className="ai-message-avatar">🤖</div>
              <div className="ai-message-bubble ai-message-loading">
                <div className="ai-typing-dots">
                  <span></span><span></span><span></span>
                </div>
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
            placeholder="Ask about a stock or market trend... (Enter to send)"
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
