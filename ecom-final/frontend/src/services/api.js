import axios from 'axios'

// Tất cả API calls đi qua Nginx Gateway (port 80)
const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' }
})

// Request interceptor — tự động thêm JWT token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// Response interceptor — xử lý lỗi chung
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

// ── Auth ────────────────────────────────────────────────────
export const authAPI = {
  register: (data)  => api.post('/users/auth/register/', data),
  login:    (data)  => api.post('/users/auth/login/',    data),
  logout:   (data)  => api.post('/users/auth/logout/',   data),
  profile:  ()      => api.get('/users/me/'),
}

// ── Products ─────────────────────────────────────────────────
export const productAPI = {
  list:       (params) => api.get('/products/', { params }),
  detail:     (id)     => api.get(`/products/${id}/`),
  categories: ()       => api.get('/products/categories/'),
}

// ── Cart ──────────────────────────────────────────────────────
export const cartAPI = {
  get:        (customerId)           => api.get(`/carts/${customerId}/`),
  addItem:    (customerId, data)     => api.post(`/carts/${customerId}/items/`, data),
  updateItem: (customerId, productId, quantity) => api.put(`/carts/${customerId}/items/${productId}/`, { quantity }),
  removeItem: (customerId, productId) => api.delete(`/carts/${customerId}/items/${productId}/`),
  clear:      (customerId)           => api.delete(`/carts/${customerId}/`),
}

// ── Orders ────────────────────────────────────────────────────
export const orderAPI = {
  list:   (customerId) => api.get('/orders/', { params: { customer_id: customerId } }),
  create: (data)       => api.post('/orders/create/', data),
  detail: (id)         => api.get(`/orders/${id}/`),
}

// ── AI ────────────────────────────────────────────────────────
export const aiAPI = {
  recommend:   (userId, topK = 10) => api.get(`/ai/v1/recommend/${userId}`, { params: { top_k: topK } }),
  chat:        (data)              => api.post('/ai/v1/chat',        data),
  health:      ()                  => api.get('/ai/v1/health'),
  // Knowledge Graph endpoints
  trackEvent:  (data)              => api.post('/ai/v1/interaction', data),   // {user_id, product_id, action}
  graphInsight:(userId)            => api.get(`/ai/v1/graph/user/${userId}`),
  rebuildIndex:()                  => api.get('/ai/v1/rebuild-index'),
}

// ── Shipping ──────────────────────────────────────────────────
export const shippingAPI = {
  track: (orderId) => api.get(`/shipping/${orderId}/`),
}

export default api
