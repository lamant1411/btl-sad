import { useState, useEffect } from 'react'
import { aiAPI, productAPI } from '../services/api'

const CATEGORY_EMOJI = {
  book: '📚', phone: '📱', laptop: '💻', tablet: '📟',
  fashion: '👗', appliance: '🏠', cosmetics: '💄',
  food: '🍎', toy: '🧸', sport: '⚽'
}

function formatPrice(p) {
  return new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(p)
}

function RecommendCard({ productId, onAddToCart }) {
  const [product, setProduct] = useState(null)

  useEffect(() => {
    productAPI.detail(productId)
      .then(r => setProduct(r.data))
      .catch(() => {})
  }, [productId])

  if (!product) {
    return (
      <div className="carousel-item">
        <div className="skeleton" style={{ height: 260, borderRadius: 12 }} />
      </div>
    )
  }

  const emoji = CATEGORY_EMOJI[product.category?.slug] || '🛍️'

  return (
    <div className="carousel-item">
      <div className="product-card">
        <div className="product-card-img">{emoji}</div>
        <div className="product-card-body">
          <div className="product-card-name">{product.name}</div>
          <div className="product-card-price">{formatPrice(product.price)}</div>
          <div className="product-card-stock">
            {product.stock > 0 ? `Còn ${product.stock} SP` : '⚠️ Hết hàng'}
          </div>
          <button
            id={`rec-add-${product.id}`}
            className="btn btn-primary"
            style={{ width: '100%', justifyContent: 'center' }}
            onClick={() => onAddToCart(product)}
            disabled={product.stock === 0}
          >
            🛒 Thêm vào giỏ
          </button>
        </div>
      </div>
    </div>
  )
}

/**
 * RecommendCarousel — hiển thị tại 3 vị trí chiến lược:
 * - "Gợi ý dành riêng cho bạn" (Homepage)
 * - "Thường mua cùng" (Product Detail)
 * - "Đừng quên mua kèm" (Cart)
 */
export default function RecommendCarousel({ userId, title, subtitle, onAddToCart }) {
  const [recommendations, setRecommendations] = useState([])
  const [loading, setLoading]                  = useState(true)

  useEffect(() => {
    if (!userId) {
      setLoading(false)
      return
    }
    aiAPI.recommend(userId, 8)
      .then(r => setRecommendations(r.data.data || []))
      .catch(() => setRecommendations([]))
      .finally(() => setLoading(false))
  }, [userId])

  if (loading) {
    return (
      <div style={{ marginBottom: 48 }}>
        <div className="section-title">
          <span className="ai-badge">🤖 AI</span>
          <h2>{title}</h2>
        </div>
        <div className="carousel">
          {[1,2,3,4].map(i => (
            <div key={i} className="carousel-item">
              <div className="skeleton" style={{ height: 260, borderRadius: 12 }} />
            </div>
          ))}
        </div>
      </div>
    )
  }

  if (!recommendations.length) return null

  return (
    <div style={{ marginBottom: 48 }} className="fade-in">
      <div className="section-title">
        <span className="ai-badge">🤖 AI</span>
        <div>
          <h2>{title}</h2>
          {subtitle && <p style={{ color: 'var(--text-muted)', fontSize: 13, marginTop: 2 }}>{subtitle}</p>}
        </div>
      </div>
      <div className="carousel" id={`carousel-${title.replace(/\s+/g, '-').toLowerCase()}`}>
        {recommendations.map((rec) => (
          <RecommendCard
            key={rec.product_id}
            productId={rec.product_id}
            onAddToCart={onAddToCart}
          />
        ))}
      </div>
    </div>
  )
}
