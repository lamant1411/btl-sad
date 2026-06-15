import { useState, useEffect, useRef } from 'react'
import { useUIStore, useAuthStore, useCartStore } from '../store'
import { aiAPI, cartAPI } from '../services/api'

// Emoji map cho categories
const CATEGORY_EMOJI = {
  book: '📚', phone: '📱', laptop: '💻', tablet: '📟',
  fashion: '👗', appliance: '🏠', cosmetics: '💄',
  food: '🍎', toy: '🧸', sport: '⚽'
}

function formatPrice(price) {
  return new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(price)
}

// ── Mini Product Card (inline trong chat) ────────────────────────
function MiniProductCard({ product, onAddToCart }) {
  const emoji = CATEGORY_EMOJI[product.category_slug] || '🛍️'
  return (
    <div className="chat-product-card">
      <div className="chat-product-emoji">{emoji}</div>
      <div className="chat-product-info">
        <div className="chat-product-name">{product.name}</div>
        <div className="chat-product-price">{formatPrice(product.price)}</div>
      </div>
      <button
        id={`chat-add-to-cart-${product.id}`}
        className="btn chat-product-btn"
        onClick={() => onAddToCart(product)}
      >
        🛒
      </button>
    </div>
  )
}

// ── Chat Message ────────────────────────────────────────────────
function ChatMessage({ msg, onAddToCart }) {
  if (msg.loading) {
    return (
      <div className="chat-msg bot loading">
        <span className="dot" />
        <span className="dot" />
        <span className="dot" />
      </div>
    )
  }

  return (
    <div className={`chat-msg ${msg.role}`}>
      {msg.text}
      {/* Hiển thị Mini Product Cards nếu bot trả về sản phẩm */}
      {msg.role === 'bot' && msg.products?.length > 0 && (
        <div style={{ marginTop: '10px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {msg.products.slice(0, 3).map((p) => (
            <MiniProductCard key={p.id} product={p} onAddToCart={onAddToCart} />
          ))}
        </div>
      )}
    </div>
  )
}

// ── Main Chat Widget ─────────────────────────────────────────────
export default function ChatWidget() {
  const { chatOpen, toggleChat } = useUIStore()
  const { user, isLoggedIn }     = useAuthStore()
  const { items }                = useCartStore()

  const [messages, setMessages]  = useState([
    {
      role: 'bot',
      text: '👋 Xin chào! Tôi là AI Trợ lý mua sắm của EcomAI. Tôi có thể giúp bạn tìm sản phẩm, so sánh giá và tư vấn dựa trên sở thích của bạn!',
      id: 0
    }
  ])
  const [input, setInput]    = useState('')
  const [loading, setLoading] = useState(false)
  const messagesEndRef        = useRef(null)

  // Quick replies context-aware
  const quickReplies = [
    '📱 Tìm điện thoại giá tốt',
    '💻 Laptop cho sinh viên',
    '🎁 Gợi ý quà tặng',
    '🔥 Sản phẩm bán chạy',
  ]

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleAddToCart = async (product) => {
    if (!isLoggedIn || !user) return
    try {
      await cartAPI.addItem(user.id, { product_id: product.id, quantity: 1 })
    } catch (e) {
      console.error(e)
    }
  }

  const sendMessage = async (text) => {
    const query = text || input.trim()
    if (!query || loading) return

    setInput('')
    const userMsgId = Date.now()

    setMessages((prev) => [...prev, { role: 'user', text: query, id: userMsgId }])

    // Loading indicator
    const loadingId = userMsgId + 1
    setMessages((prev) => [...prev, { role: 'bot', loading: true, id: loadingId }])
    setLoading(true)

    try {
      const userId = isLoggedIn && user ? user.id : 0
      const { data } = await aiAPI.chat({ user_id: userId, query })

      setMessages((prev) => prev.filter((m) => m.id !== loadingId))
      setMessages((prev) => [
        ...prev,
        {
          role:     'bot',
          text:     data.reply,
          products: data.rag_products || [],
          id:       loadingId + 1,
        }
      ])
    } catch {
      setMessages((prev) => prev.filter((m) => m.id !== loadingId))
      setMessages((prev) => [
        ...prev,
        {
          role: 'bot',
          text: '😔 Xin lỗi, tôi đang gặp sự cố kỹ thuật. Vui lòng thử lại sau nhé!',
          id:   loadingId + 1,
        }
      ])
    } finally {
      setLoading(false)
    }
  }

  const handleKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  return (
    <>
      {/* Floating Action Button */}
      <button
        id="chat-fab-btn"
        className="chat-fab"
        onClick={toggleChat}
        aria-label="Mở chat AI"
        title="AI Trợ lý mua sắm"
      >
        {chatOpen ? '✕' : '🤖'}
      </button>

      {/* Chat Window */}
      {chatOpen && (
        <div className="chat-window" id="chat-window">
          {/* Header */}
          <div className="chat-header">
            <div>
              <h3>🤖 EcomAI Assistant</h3>
              <p>Trợ lý mua sắm thông minh · RAG + LSTM</p>
            </div>
            <button className="chat-close" onClick={toggleChat} id="chat-close-btn">✕</button>
          </div>

          {/* Messages */}
          <div className="chat-messages" id="chat-messages">
            {messages.map((msg) => (
              <ChatMessage key={msg.id} msg={msg} onAddToCart={handleAddToCart} />
            ))}
            <div ref={messagesEndRef} />
          </div>

          {/* Quick Replies */}
          <div className="quick-replies">
            {quickReplies.map((qr) => (
              <button
                key={qr}
                className="quick-reply-btn"
                onClick={() => sendMessage(qr)}
                disabled={loading}
                id={`qr-${qr.replace(/\s+/g, '-').toLowerCase()}`}
              >
                {qr}
              </button>
            ))}
          </div>

          {/* Input */}
          <div className="chat-input-area">
            <input
              id="chat-input"
              className="chat-input"
              type="text"
              placeholder="Nhập câu hỏi..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKey}
              disabled={loading}
            />
            <button
              id="chat-send-btn"
              className="chat-send"
              onClick={() => sendMessage()}
              disabled={loading || !input.trim()}
            >
              ➤
            </button>
          </div>
        </div>
      )}
    </>
  )
}
