import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { orderAPI, shippingAPI } from '../services/api'
import { useAuthStore } from '../store'

function formatPrice(p) {
  return new Intl.NumberFormat('vi-VN', { style:'currency', currency:'VND' }).format(p)
}

export default function OrdersPage() {
  const { user, isLoggedIn } = useAuthStore()
  const navigate             = useNavigate()
  const [orders, setOrders]  = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!isLoggedIn) { navigate('/login'); return }
    orderAPI.list(user.id)
      .then(r => setOrders(r.data || []))
      .finally(() => setLoading(false))
  }, [])

  return (
    <main className="page">
      <div className="container">
        <h1 style={{ fontSize:28, fontWeight:800, marginBottom:32 }}>📦 Đơn hàng của tôi</h1>

        {loading ? (
          <div style={{ display:'flex', flexDirection:'column', gap:16 }}>
            {[1,2,3].map(i => <div key={i} className="skeleton" style={{ height:120, borderRadius:12 }} />)}
          </div>
        ) : orders.length === 0 ? (
          <div className="card" style={{ textAlign:'center', padding:64 }}>
            <div style={{ fontSize:80, marginBottom:16 }}>📦</div>
            <h2>Chưa có đơn hàng nào</h2>
            <button className="btn btn-primary" style={{ marginTop:24 }} onClick={() => navigate('/')}>🛍️ Mua sắm ngay</button>
          </div>
        ) : (
          <div style={{ display:'flex', flexDirection:'column', gap:16 }}>
            {orders.map(order => (
              <div 
                key={order.id} 
                className="card fade-in"
                style={{ cursor: 'pointer' }}
                onClick={() => navigate(`/orders/${order.id}`)}
              >
                <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:16 }}>
                  <div>
                    <h3 style={{ fontWeight:700, marginBottom:4 }}>Đơn hàng #{order.id}</h3>
                    <p style={{ color:'var(--text-muted)', fontSize:13 }}>
                      {new Date(order.created_at).toLocaleString('vi-VN')}
                    </p>
                  </div>
                  <span className={`badge status-${order.status}`}>{order.status}</span>
                </div>
                <div style={{ display:'flex', gap:8, flexWrap:'wrap', marginBottom:16 }}>
                  {order.items?.map(item => (
                    <span key={item.id} style={{ background:'var(--bg-glass)', border:'1px solid var(--border)', borderRadius:8, padding:'4px 12px', fontSize:13 }}>
                      SP #{item.product_id} × {item.quantity}
                    </span>
                  ))}
                </div>
                <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center' }}>
                  <span style={{ color:'var(--text-muted)', fontSize:14 }}>{order.items?.length} sản phẩm</span>
                  <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
                    <span style={{ fontSize:20, fontWeight:700, color:'var(--primary)' }}>{formatPrice(order.total_price)}</span>
                    <span style={{ color: 'var(--text-muted)' }}>Chi tiết ➔</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </main>
  )
}
