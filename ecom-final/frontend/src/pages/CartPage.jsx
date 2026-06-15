import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { cartAPI, orderAPI, aiAPI } from '../services/api'
import { useAuthStore, useCartStore } from '../store'
import RecommendCarousel from '../components/RecommendCarousel'
import toast from 'react-hot-toast'

function formatPrice(p) {
  return new Intl.NumberFormat('vi-VN', { style:'currency', currency:'VND' }).format(p)
}

const CATEGORY_EMOJI = {
  book:'📚', phone:'📱', laptop:'💻', tablet:'📟',
  fashion:'👗', appliance:'🏠', cosmetics:'💄', food:'🍎', toy:'🧸', sport:'⚽'
}

export default function CartPage() {
  const { user, isLoggedIn }         = useAuthStore()
  const { items, totalPrice, setCart, clear } = useCartStore()
  const [loading, setLoading]        = useState(false)
  const [checkoutLoading, setCheckoutLoading] = useState(false)
  const navigate                     = useNavigate()

  useEffect(() => {
    if (!isLoggedIn) { navigate('/login'); return }
    cartAPI.get(user.id)
      .then(r => setCart(r.data))
      .catch(() => {})
  }, [isLoggedIn])

  const handleRemove = async (productId) => {
    try {
      const res = await cartAPI.removeItem(user.id, productId)
      setCart(res.data)
      toast.success('Đã xóa sản phẩm khỏi giỏ')
    } catch { toast.error('Không thể xóa sản phẩm') }
  }

  const handleAddToCart = async (product) => {
    try {
      const res = await cartAPI.addItem(user.id, { product_id: product.id, quantity: 1 })
      setCart(res.data)
      toast.success(`Đã thêm "${product.name}"`)
    } catch (e) { toast.error(e.response?.data?.error || 'Lỗi') }
  }

  const handleUpdateQuantity = async (productId, currentQuantity, delta) => {
    const newQuantity = currentQuantity + delta
    if (newQuantity < 1) {
      handleRemove(productId)
      return
    }
    try {
      const res = await cartAPI.updateItem(user.id, productId, newQuantity)
      setCart(res.data)
      toast.success('Cập nhật số lượng thành công')
    } catch (e) {
      toast.error(e.response?.data?.error || 'Lỗi cập nhật số lượng')
    }
  }

  const handleCheckout = async () => {
    if (!items.length) { toast.error('Giỏ hàng trống'); return }
    setCheckoutLoading(true)
    try {
      const payload = {
        customer_id:    user.id,
        payment_method: 'COD',
        items: items.map(i => ({
          product_id: i.product_id,
          quantity:   i.quantity,
          unit_price: i.unit_price,
        }))
      }
      const res = await orderAPI.create(payload)
      // Ghi nhận sự kiện 'purchase' vào Knowledge Graph cho từng sản phẩm
      items.forEach(i => {
        aiAPI.trackEvent({ user_id: user.id, product_id: i.product_id, action: 'purchase' }).catch(() => {})
      })
      clear()
      toast.success(`🎉 Đặt hàng thành công! Mã đơn: #${res.data.id}`)
      navigate('/orders')
    } catch (e) {
      toast.error(e.response?.data?.error || 'Lỗi khi đặt hàng')
    } finally {
      setCheckoutLoading(false)
    }
  }

  return (
    <main className="page">
      <div className="container">
        <h1 style={{ fontSize:28, fontWeight:800, marginBottom:32 }}>🛒 Giỏ hàng của bạn</h1>

        {!items.length ? (
          <div className="card" style={{ textAlign:'center', padding:64 }}>
            <div style={{ fontSize:80, marginBottom:16 }}>🛒</div>
            <h2 style={{ marginBottom:8 }}>Giỏ hàng trống</h2>
            <p style={{ color:'var(--text-muted)', marginBottom:24 }}>Hãy thêm sản phẩm vào giỏ hàng của bạn</p>
            <button className="btn btn-primary" onClick={() => navigate('/')}>🛍️ Tiếp tục mua sắm</button>
          </div>
        ) : (
          <div style={{ display:'grid', gridTemplateColumns:'1fr 340px', gap:24, alignItems:'start' }}>
            {/* Cart Items */}
            <div className="card" style={{ padding:0 }}>
              {items.map(item => (
                <div key={item.product_id} className="cart-item">
                  <div className="cart-item-emoji" style={{ cursor: 'pointer' }} onClick={() => navigate(`/product/${item.product_id}`)}>
                    {CATEGORY_EMOJI[item.category_slug] || '🛍️'}
                  </div>
                  <div className="cart-item-info">
                    <div className="cart-item-name" style={{ cursor: 'pointer' }} onClick={() => navigate(`/product/${item.product_id}`)}>Sản phẩm #{item.product_id}</div>
                    <div className="cart-item-price">{formatPrice(item.unit_price)}</div>
                  </div>
                  <div className="cart-qty" style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                    <div style={{ display: 'flex', border: '1px solid var(--border)', borderRadius: 8, overflow: 'hidden' }}>
                      <button 
                        style={{ padding: '4px 10px', background: 'transparent', border: 'none', cursor: 'pointer', fontSize: 16 }}
                        onClick={() => handleUpdateQuantity(item.product_id, item.quantity, -1)}
                      >-</button>
                      <span style={{ width: 30, textAlign: 'center', fontWeight: 600, fontSize: 14, lineHeight: '30px' }}>{item.quantity}</span>
                      <button 
                        style={{ padding: '4px 10px', background: 'transparent', border: 'none', cursor: 'pointer', fontSize: 16 }}
                        onClick={() => handleUpdateQuantity(item.product_id, item.quantity, 1)}
                      >+</button>
                    </div>
                    <span style={{ fontSize:16, fontWeight:700, color:'var(--primary)', minWidth:100, textAlign:'right' }}>
                      {formatPrice(item.quantity * item.unit_price)}
                    </span>
                  </div>
                  <button
                    id={`remove-${item.product_id}`}
                    className="btn btn-danger"
                    style={{ padding:'6px 12px' }}
                    onClick={() => handleRemove(item.product_id)}
                  >
                    🗑️
                  </button>
                </div>
              ))}
            </div>

            {/* Summary */}
            <div className="cart-summary fade-in">
              <h3 style={{ marginBottom:20, fontWeight:700 }}>Tóm tắt đơn hàng</h3>
              <div style={{ display:'flex', justifyContent:'space-between', marginBottom:12, color:'var(--text-muted)', fontSize:14 }}>
                <span>Tạm tính ({items.length} SP)</span>
                <span>{formatPrice(totalPrice)}</span>
              </div>
              <div style={{ display:'flex', justifyContent:'space-between', marginBottom:12, color:'var(--text-muted)', fontSize:14 }}>
                <span>Phí vận chuyển</span>
                <span style={{ color:'var(--success)' }}>Miễn phí</span>
              </div>
              <hr style={{ borderColor:'var(--border)', margin:'16px 0' }} />
              <div style={{ display:'flex', justifyContent:'space-between', fontSize:20, fontWeight:800, marginBottom:24 }}>
                <span>Tổng cộng</span>
                <span style={{ color:'var(--primary)' }}>{formatPrice(totalPrice)}</span>
              </div>
              <button
                id="checkout-btn"
                className="btn btn-primary"
                style={{ width:'100%', justifyContent:'center', fontSize:16, padding:'14px' }}
                onClick={handleCheckout}
                disabled={checkoutLoading}
              >
                {checkoutLoading ? '⏳ Đang đặt hàng...' : '✅ Đặt hàng ngay'}
              </button>
            </div>
          </div>
        )}

        {/* AI Nudge Section — "Đừng quên mua kèm" */}
        {items.length > 0 && isLoggedIn && (
          <div style={{ marginTop:48 }}>
            <RecommendCarousel
              userId={user?.id}
              title="Đừng quên mua kèm"
              subtitle="AI gợi ý dựa trên giỏ hàng hiện tại"
              onAddToCart={handleAddToCart}
            />
          </div>
        )}
      </div>
    </main>
  )
}
