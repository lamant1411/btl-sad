import { create } from 'zustand'

// ── Auth Store ─────────────────────────────────────────────────
export const useAuthStore = create((set) => ({
  user:        JSON.parse(localStorage.getItem('user') || 'null'),
  accessToken: localStorage.getItem('access_token') || null,
  isLoggedIn:  !!localStorage.getItem('access_token'),

  login: (user, accessToken, refreshToken) => {
    localStorage.setItem('access_token',  accessToken)
    localStorage.setItem('refresh_token', refreshToken)
    localStorage.setItem('user',          JSON.stringify(user))
    localStorage.setItem('user_id',       user.id)
    set({ user, accessToken, isLoggedIn: true })
  },

  logout: () => {
    localStorage.clear()
    set({ user: null, accessToken: null, isLoggedIn: false })
  },
}))

// ── Cart Store ─────────────────────────────────────────────────
export const useCartStore = create((set, get) => ({
  items:      [],
  totalItems: 0,
  totalPrice: 0,

  setCart: (cart) => {
    const items      = cart?.items || []
    const totalItems = items.reduce((s, i) => s + i.quantity, 0)
    const totalPrice = items.reduce((s, i) => s + i.quantity * parseFloat(i.unit_price || 0), 0)
    set({ items, totalItems, totalPrice })
  },

  clear: () => set({ items: [], totalItems: 0, totalPrice: 0 }),
}))

// ── UI Store ───────────────────────────────────────────────────
export const useUIStore = create((set) => ({
  chatOpen: false,
  toggleChat: () => set((s) => ({ chatOpen: !s.chatOpen })),
  closeChat:  () => set({ chatOpen: false }),
}))
