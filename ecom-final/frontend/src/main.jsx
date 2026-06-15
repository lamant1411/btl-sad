import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import './index.css'

import Navbar        from './components/Navbar'
import ChatWidget    from './components/ChatWidget'
import HomePage      from './pages/HomePage'
import { LoginPage, RegisterPage } from './pages/AuthPages'
import CartPage      from './pages/CartPage'
import OrdersPage    from './pages/OrdersPage'
import ProductDetailPage from './pages/ProductDetailPage'
import OrderDetailPage   from './pages/OrderDetailPage'

function App() {
  return (
    <BrowserRouter>
      <Navbar />
      <Routes>
        <Route path="/"         element={<HomePage />}    />
        <Route path="/login"    element={<LoginPage />}   />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/cart"     element={<CartPage />}    />
        <Route path="/orders"   element={<OrdersPage />}  />
        <Route path="/orders/:id" element={<OrderDetailPage />} />
        <Route path="/product/:id" element={<ProductDetailPage />} />
      </Routes>
      {/* AI Chatbot Widget — Global, hiển thị trên mọi trang */}
      <ChatWidget />
      {/* Toast Notifications */}
      <Toaster
        position="top-right"
        toastOptions={{
          style: {
            background: 'var(--bg-card)',
            color:      'var(--text)',
            border:     '1px solid var(--border)',
            fontFamily: 'Inter, sans-serif',
          },
          duration: 3000,
        }}
      />
    </BrowserRouter>
  )
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
)
