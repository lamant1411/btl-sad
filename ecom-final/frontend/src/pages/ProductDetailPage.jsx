import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { productAPI, cartAPI, aiAPI } from '../services/api'
import { useAuthStore, useCartStore } from '../store'
import RecommendCarousel from '../components/RecommendCarousel'
import toast from 'react-hot-toast'

const CATEGORY_EMOJI = {
  book: '📚', phone: '📱', laptop: '💻', tablet: '📟',
  fashion: '👗', appliance: '🏠', cosmetics: '💄',
  food: '🍎', toy: '🧸', sport: '⚽'
}

function formatPrice(p) {
  return new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(p)
}

export default function ProductDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { user, isLoggedIn } = useAuthStore()
  const { setCart } = useCartStore()

  const [product, setProduct] = useState(null)
  const [loading, setLoading] = useState(true)
  const [quantity, setQuantity] = useState(1)

  useEffect(() => {
    setLoading(true)
    productAPI.detail(id)
      .then(res => {
        setProduct(res.data)
        // Ghi nhận sự kiện 'view' vào Knowledge Graph
        if (user?.id && res.data?.id) {
          aiAPI.trackEvent({ user_id: user.id, product_id: res.data.id, action: 'view' }).catch(() => {})
        }
      })
      .catch(err => {
        toast.error('Không tìm thấy sản phẩm')
        navigate('/')
      })
      .finally(() => setLoading(false))
  }, [id, navigate])

  const handleAddToCart = async (prod = product, qty = quantity) => {
    if (!isLoggedIn) {
      toast.error('Vui lòng đăng nhập để mua hàng')
      navigate('/login')
      return
    }
    if (prod.stock < qty) {
      toast.error('Không đủ hàng trong kho')
      return
    }
    try {
      const res = await cartAPI.addItem(user.id, { product_id: prod.id, quantity: qty })
      setCart(res.data)
      toast.success(`Đã thêm "${prod.name}" vào giỏ hàng`)
      // Ghi nhận sự kiện 'add_to_cart' vào Knowledge Graph
      aiAPI.trackEvent({ user_id: user.id, product_id: prod.id, action: 'add_to_cart' }).catch(() => {})
    } catch (e) {
      toast.error(e.response?.data?.error || 'Lỗi khi thêm vào giỏ')
    }
  }

  if (loading) {
    return (
      <main className="page">
        <div className="container" style={{ display: 'flex', gap: 40, marginTop: 40 }}>
          <div className="skeleton" style={{ flex: 1, height: 400, borderRadius: 16 }} />
          <div style={{ flex: 1 }}>
            <div className="skeleton" style={{ height: 40, width: '80%', marginBottom: 20 }} />
            <div className="skeleton" style={{ height: 30, width: '40%', marginBottom: 40 }} />
            <div className="skeleton" style={{ height: 100, width: '100%', marginBottom: 20 }} />
          </div>
        </div>
      </main>
    )
  }

  if (!product) return null

  const emoji = CATEGORY_EMOJI[product.category?.slug] || '🛍️'

  return (
    <main className="page fade-in">
      <div className="container" style={{ marginTop: 40 }}>
        {/* Breadcrumb */}
        <div style={{ marginBottom: 24, fontSize: 14, color: 'var(--text-muted)' }}>
          <span style={{ cursor: 'pointer' }} onClick={() => navigate('/')}>Trang chủ</span>
          {' > '}
          <span style={{ cursor: 'pointer' }}>{product.category?.name || 'Sản phẩm'}</span>
          {' > '}
          <span style={{ color: 'var(--text)', fontWeight: 600 }}>{product.name}</span>
        </div>

        <div style={{ display: 'flex', gap: 60, alignItems: 'flex-start', flexWrap: 'wrap' }}>
          {/* Hình ảnh (Emoji mockup) */}
          <div className="card" style={{ flex: '1 1 400px', display: 'flex', alignItems: 'center', justifyContent: 'center', height: 450, fontSize: 150, background: 'linear-gradient(135deg, var(--bg-card), var(--border))' }}>
            {emoji}
          </div>

          {/* Chi tiết sản phẩm */}
          <div style={{ flex: '1 1 400px' }}>
            <h1 style={{ fontSize: 36, fontWeight: 800, marginBottom: 16 }}>{product.name}</h1>
            <div style={{ fontSize: 28, fontWeight: 700, color: 'var(--primary)', marginBottom: 24 }}>
              {formatPrice(product.price)}
            </div>

            <p style={{ fontSize: 16, lineHeight: 1.6, color: 'var(--text-muted)', marginBottom: 32 }}>
              {product.description || 'Mô tả sản phẩm đang cập nhật.'}
            </p>

            <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 32 }}>
              <span style={{ fontSize: 14, fontWeight: 600 }}>Trạng thái:</span>
              {product.stock > 0 ? (
                <span className="badge badge-success">Còn {product.stock} SP</span>
              ) : (
                <span className="badge badge-danger">Hết hàng</span>
              )}
            </div>

            {/* Thêm vào giỏ hàng */}
            <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
              <div style={{ display: 'flex', border: '1px solid var(--border)', borderRadius: 8, overflow: 'hidden' }}>
                <button 
                  style={{ padding: '12px 16px', background: 'transparent', border: 'none', cursor: 'pointer', fontSize: 18 }}
                  onClick={() => setQuantity(Math.max(1, quantity - 1))}
                  disabled={product.stock === 0}
                >
                  -
                </button>
                <input 
                  type="number" 
                  value={quantity} 
                  onChange={(e) => setQuantity(Math.max(1, Math.min(product.stock, Number(e.target.value))))}
                  style={{ width: 50, textAlign: 'center', border: 'none', background: 'transparent', fontWeight: 600, fontSize: 16, outline: 'none' }}
                  disabled={product.stock === 0}
                />
                <button 
                  style={{ padding: '12px 16px', background: 'transparent', border: 'none', cursor: 'pointer', fontSize: 18 }}
                  onClick={() => setQuantity(Math.min(product.stock, quantity + 1))}
                  disabled={product.stock === 0}
                >
                  +
                </button>
              </div>

              <button 
                className="btn btn-primary"
                style={{ flex: 1, padding: 16, fontSize: 16, justifyContent: 'center' }}
                onClick={() => handleAddToCart(product, quantity)}
                disabled={product.stock === 0}
              >
                🛒 Thêm vào giỏ
              </button>
            </div>
          </div>
        </div>

        {/* Khối gợi ý */}
        <div style={{ marginTop: 80 }}>
          <RecommendCarousel 
            userId={user?.id}
            title="Thường mua cùng" 
            subtitle="Các sản phẩm được gợi ý cho bạn"
            onAddToCart={(prod) => handleAddToCart(prod, 1)}
          />
        </div>
      </div>
    </main>
  )
}
