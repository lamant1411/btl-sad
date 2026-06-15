import { Link, useLocation } from 'react-router-dom'
import { useAuthStore, useCartStore } from '../store'

export default function Navbar() {
  const { isLoggedIn, user, logout } = useAuthStore()
  const { totalItems }               = useCartStore()
  const { pathname }                 = useLocation()

  const handleLogout = () => {
    logout()
    window.location.href = '/login'
  }

  return (
    <nav className="navbar">
      <div className="container navbar-inner">
        {/* Logo */}
        <Link to="/" id="navbar-logo" className="navbar-logo">
          🛍️ <span>EcomAI</span>
        </Link>

        {/* Navigation links */}
        <div className="navbar-nav">
          <Link to="/"         className={pathname === '/'         ? 'active' : ''} id="nav-home">Trang chủ</Link>
          <Link to="/products" className={pathname === '/products' ? 'active' : ''} id="nav-products">Sản phẩm</Link>
          {isLoggedIn && (
            <Link to="/orders" className={pathname === '/orders'   ? 'active' : ''} id="nav-orders">Đơn hàng</Link>
          )}
        </div>

        {/* Actions */}
        <div className="navbar-actions">
          {isLoggedIn ? (
            <>
              <Link to="/cart" id="nav-cart-btn">
                <button className="cart-btn" aria-label="Giỏ hàng">
                  🛒
                  {totalItems > 0 && (
                    <span className="cart-badge">{totalItems > 99 ? '99+' : totalItems}</span>
                  )}
                </button>
              </Link>
              <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>
                👤 {user?.full_name || user?.username}
              </span>
              <button id="nav-logout-btn" className="btn btn-ghost" style={{ padding: '8px 14px', fontSize: 13 }} onClick={handleLogout}>
                Đăng xuất
              </button>
            </>
          ) : (
            <>
              <Link to="/login"    id="nav-login-btn">    <button className="btn btn-ghost">Đăng nhập</button></Link>
              <Link to="/register" id="nav-register-btn"> <button className="btn btn-primary">Đăng ký</button></Link>
            </>
          )}
        </div>
      </div>
    </nav>
  )
}
