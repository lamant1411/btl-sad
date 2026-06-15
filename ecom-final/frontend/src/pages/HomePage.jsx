import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { productAPI, cartAPI } from '../services/api'
import { useAuthStore, useCartStore } from '../store'
import RecommendCarousel from '../components/RecommendCarousel'
import toast from 'react-hot-toast'

const CATEGORY_EMOJI = {
  book: '📚', phone: '📱', laptop: '💻', tablet: '📟',
  fashion: '👗', appliance: '🏠', cosmetics: '💄',
  food: '🍎', toy: '🧸', sport: '⚽'
}

function formatPrice(p) {
  return new Intl.NumberFormat('vi-VN', { style:'currency', currency:'VND' }).format(p)
}

export default function HomePage() {
  const [products,   setProducts]   = useState([])
  const [categories, setCategories] = useState([])
  const [loading,    setLoading]    = useState(true)
  const [search,     setSearch]     = useState('')
  const [activeCategory, setActiveCategory] = useState('')
  const { user, isLoggedIn }        = useAuthStore()
  const { setCart }                 = useCartStore()
  const navigate                    = useNavigate()

  useEffect(() => {
    Promise.all([
      productAPI.list({ page_size: 20 }),
      productAPI.categories()
    ]).then(([pRes, cRes]) => {
      setProducts(pRes.data.results || [])
      setCategories(cRes.data || [])
    }).finally(() => setLoading(false))
  }, [])

  const handleFilter = async (cat) => {
    setActiveCategory(cat)
    setLoading(true)
    try {
      const res = await productAPI.list({ category: cat || undefined, page_size: 20 })
      setProducts(res.data.results || [])
    } finally {
      setLoading(false)
    }
  }

  const handleSearch = async (e) => {
    e.preventDefault()
    setLoading(true)
    try {
      const res = await productAPI.list({ search, page_size: 20 })
      setProducts(res.data.results || [])
    } finally {
      setLoading(false)
    }
  }

  const handleAddToCart = async (product) => {
    if (!isLoggedIn) { toast.error('Vui lòng đăng nhập để mua hàng'); return }
    try {
      const res = await cartAPI.addItem(user.id, { product_id: product.id, quantity: 1 })
      setCart(res.data)
      toast.success(`✅ Đã thêm "${product.name}" vào giỏ!`)
    } catch (e) {
      toast.error(e.response?.data?.error || 'Không thể thêm vào giỏ hàng')
    }
  }

  return (
    <main className="page">
      <div className="container">

        {/* Hero Section */}
        <section className="hero fade-in">
          <h1>Mua sắm thông minh<br />cùng <span style={{background:'var(--grad-primary)',WebkitBackgroundClip:'text',WebkitTextFillColor:'transparent'}}>AI</span></h1>
          <p>Hệ thống gợi ý sản phẩm cá nhân hóa và trợ lý tư vấn AI 24/7 — mang đến trải nghiệm mua sắm hoàn toàn mới.</p>
          <div className="hero-cta">
            <form onSubmit={handleSearch} style={{ display:'flex', gap:12 }}>
              <input
                id="search-input"
                className="input"
                type="text"
                placeholder="🔍 Tìm kiếm sản phẩm..."
                value={search}
                onChange={e => setSearch(e.target.value)}
                style={{ width: 320 }}
              />
              <button id="search-btn" type="submit" className="btn btn-primary">Tìm</button>
            </form>
          </div>
        </section>

        {/* AI Recommendation — "Gợi ý dành riêng cho bạn" */}
        {isLoggedIn && (
          <RecommendCarousel
            userId={user?.id}
            title="Gợi ý dành riêng cho bạn"
            subtitle="Dựa trên hành vi mua sắm của bạn · LSTM AI"
            onAddToCart={handleAddToCart}
          />
        )}

        {/* Category Filter */}
        <div style={{ display:'flex', gap:8, flexWrap:'wrap', marginBottom:28 }}>
          <button
            id="filter-all"
            className={`btn ${!activeCategory ? 'btn-primary' : 'btn-ghost'}`}
            onClick={() => handleFilter('')}
          >
            Tất cả
          </button>
          {categories.map(cat => (
            <button
              key={cat.slug}
              id={`filter-${cat.slug}`}
              className={`btn ${activeCategory === cat.slug ? 'btn-primary' : 'btn-ghost'}`}
              onClick={() => handleFilter(cat.slug)}
            >
              {cat.icon} {cat.name}
            </button>
          ))}
        </div>

        {/* Product Grid */}
        {loading ? (
          <div className="product-grid">
            {[1,2,3,4,5,6].map(i => (
              <div key={i} className="skeleton" style={{ height: 300, borderRadius: 12 }} />
            ))}
          </div>
        ) : (
          <div className="product-grid fade-in">
            {products.map(product => (
              <div key={product.id} className="product-card">
                <div className="product-card-img" style={{ cursor: 'pointer' }} onClick={() => navigate(`/product/${product.id}`)}>
                  {CATEGORY_EMOJI[product.category_slug] || '🛍️'}
                </div>
                <div className="product-card-body">
                  <div className="badge badge-primary" style={{ marginBottom:8 }}>
                    {product.category_name}
                  </div>
                  <div className="product-card-name" style={{ cursor: 'pointer' }} onClick={() => navigate(`/product/${product.id}`)}>
                    {product.name}
                  </div>
                  <div className="product-card-price">{formatPrice(product.price)}</div>
                  <div className="product-card-stock">
                    {product.stock > 0 ? `Còn ${product.stock} sản phẩm` : '⚠️ Hết hàng'}
                  </div>
                  <button
                    id={`add-to-cart-${product.id}`}
                    className="btn btn-primary"
                    style={{ width:'100%', justifyContent:'center' }}
                    onClick={() => handleAddToCart(product)}
                    disabled={product.stock === 0}
                  >
                    🛒 Thêm vào giỏ
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </main>
  )
}
