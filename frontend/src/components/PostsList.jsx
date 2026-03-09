import React from 'react'
import EmptyState from './EmptyState'

function PostsList({ posts, onFetchPosts }) {
  if (!posts || posts.length === 0) {
    return (
      <div className="posts-list">
        <h2>Recent Posts</h2>
        <EmptyState
          icon="📝"
          title="No posts available"
          message="Fetch some posts to see them analyzed here!"
          actionButton={
            onFetchPosts && (
              <button onClick={onFetchPosts} className="btn-primary">
                Fetch New Posts
              </button>
            )
          }
        />
      </div>
    )
  }

  const formatDate = (dateStr) => {
    try {
      return new Date(dateStr).toLocaleString()
    } catch {
      return dateStr
    }
  }

  const getSentimentClass = (label) => {
    return label ? label.toLowerCase() : 'neutral'
  }

  const handlePostClick = (url) => {
    if (url) {
      window.open(url, '_blank', 'noopener,noreferrer')
    }
  }

  return (
    <div className="posts-list">
      <h2>Recent Posts ({posts.length})</h2>
      {posts.map((post) => (
        <div 
          key={post.id} 
          className={`post ${post.url ? 'clickable' : ''}`}
          onClick={() => handlePostClick(post.url)}
          role={post.url ? 'button' : undefined}
          tabIndex={post.url ? 0 : undefined}
        >
          {post.title && (
            <div className="post-title">{post.title}</div>
          )}
          <div className="post-text">{post.text}</div>
          
          <div className="post-meta">
            <div className="meta-row">
              {post.subreddit && (
                <span className="meta-item subreddit">
                  r/{post.subreddit}
                </span>
              )}
              {post.author && (
                <span className="meta-item author">
                  u/{post.author}
                </span>
              )}
              <span className="meta-item timestamp">
                {formatDate(post.created_at)}
                {post.timezone && post.timezone !== 'UTC' && (
                  <span className="timezone"> ({post.timezone})</span>
                )}
              </span>
            </div>
            
            <div className="meta-row">
              <span className={`sentiment-badge ${getSentimentClass(post.sentiment?.label)}`}>
                {post.sentiment?.label?.toUpperCase() || 'NEUTRAL'}
                {post.sentiment?.score && (
                  <span className="confidence"> ({(post.sentiment.score * 100).toFixed(1)}%)</span>
                )}
              </span>
              
              {post.url && (
                <span className="external-link-icon" title="Click to view on Reddit">
                  🔗
                </span>
              )}
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

export default PostsList
