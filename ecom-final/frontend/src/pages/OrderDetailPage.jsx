import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { orderAPI } from '../services/api'
import { useAuthStore } from '../store'
import toast from 'react-hot-toast'

function formatPrice(p) {
  return new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(p)
}

const STATUS_COLORS = {
  PENDING:   'var(--warning)',
  PAID:      'var(--success)',
  FAILED:    'var(--danger)',
  SHIPPING:  'var(--primary)',
  DELIVERED: 'var(--success)'
}

const STATUS_LABELS = {
  PENDING:   'Chờ thanh toán',
  PAID:      'Đã thanh toán',
  FAILED:    'Thất bại',
  SHIPPING:  'Đang giao hàng',
  DELIVERED: 'Đã giao thành công'
}

export default function OrderDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { isLoggedIn } = useAuthStore()

  const [order, setOrder] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!isLoggedIn) {
      navigate('/login')
      return
    }
    setLoading(true)
    orderAPI.detail(id)
      .then(res => setOrder(res.data))
      .catch(err => {
        toast.error('Không tìm thấy đơn hàng')
        navigate('/orders')
      })
      .finally(() => setLoading(false))
  }, [id, isLoggedIn, navigate])

  if (loading) {
    return (
      <main className="page">
        <div className="container" style={{ marginTop: 40 }}>
          <div className="skeleton" style={{ height: 40, width: 300, marginBottom: 20 }} />
          <div className="skeleton" style={{ height: 200, borderRadius: 16, marginBottom: 24 }} />
          <div className="skeleton" style={{ height: 300, borderRadius: 16 }} />
        </div>
      </main>
    )
  }

  if (!order) return null

  return (
    <main className="page fade-in">
      <div className="container" style={{ marginTop: 40 }}>
        {/* Breadcrumb */}
        <div style={{ marginBottom: 24, fontSize: 14, color: 'var(--text-muted)' }}>
          <span style={{ cursor: 'pointer' }} onClick={() => navigate('/orders')}>Danh sách đơn hàng</span>
          {' > '}
          <span style={{ color: 'var(--text)', fontWeight: 600 }}>Chi tiết đơn #{order.id}</span>
        </div>

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
          <h1 style={{ fontSize: 28, fontWeight: 800 }}>Đơn hàng #{order.id}</h1>
          <span 
            className="badge" 
            style={{ 
              backgroundColor: STATUS_COLORS[order.status] + '20', 
              color: STATUS_COLORS[order.status],
              fontSize: 14,
              padding: '6px 12px'
            }}
          >
            {STATUS_LABELS[order.status] || order.status}
          </span>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: 24, alignItems: 'start' }}>
          {/* Cột trái: Danh sách sản phẩm */}
          <div className="card" style={{ padding: 0 }}>
            <div style={{ padding: '20px 24px', borderBottom: '1px solid var(--border)', fontWeight: 700 }}>
              Sản phẩm ({order.items?.length || 0})
            </div>
            {order.items?.map(item => (
              <div key={item.id} className="cart-item" style={{ borderBottom: '1px solid var(--border)', borderRadius: 0, border: 'none', borderBottom: '1px solid var(--border)' }}>
                <div className="cart-item-emoji" style={{ width: 60, height: 60, fontSize: 30 }}>🛍️</div>
                <div className="cart-item-info">
                  <div className="cart-item-name">Sản phẩm #{item.product_id}</div>
                  <div className="cart-item-price">{formatPrice(item.unit_price)}</div>
                </div>
                <div className="cart-qty" style={{ textAlign: 'right' }}>
                  <div style={{ fontSize: 14, color: 'var(--text-muted)', marginBottom: 4 }}>Số lượng: {item.quantity}</div>
                  <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--primary)' }}>
                    {formatPrice(item.quantity * item.unit_price)}
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Cột phải: Thông tin & Tóm tắt */}
          <div>
            <div className="card" style={{ marginBottom: 24 }}>
              <h3 style={{ marginBottom: 16, fontWeight: 700, fontSize: 16 }}>Thông tin đơn hàng</h3>
              <div style={{ fontSize: 14, color: 'var(--text-muted)', lineHeight: 1.8 }}>
                <div><strong>Ngày đặt:</strong> {new Date(order.created_at).toLocaleString('vi-VN')}</div>
                <div><strong>Khách hàng ID:</strong> {order.customer_id}</div>
                <div><strong>Phương thức TT:</strong> {order.payment_method}</div>
              </div>
            </div>

            <div className="cart-summary">
              <h3 style={{ marginBottom: 20, fontWeight: 700, fontSize: 16 }}>Tổng cộng</h3>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12, color: 'var(--text-muted)', fontSize: 14 }}>
                <span>Tạm tính</span>
                <span>{formatPrice(order.total_price)}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12, color: 'var(--text-muted)', fontSize: 14 }}>
                <span>Phí vận chuyển</span>
                <span style={{ color: 'var(--success)' }}>Miễn phí</span>
              </div>
              <hr style={{ borderColor: 'var(--border)', margin: '16px 0' }} />
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 20, fontWeight: 800 }}>
                <span>Thành tiền</span>
                <span style={{ color: 'var(--primary)' }}>{formatPrice(order.total_price)}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>
  )
}
