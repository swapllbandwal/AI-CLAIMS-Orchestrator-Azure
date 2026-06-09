import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8005'

const api = axios.create({ baseURL: API_BASE_URL })

export const claimsAPI = {
  health: async () => (await api.get('/api/health')).data,

  submitClaim: async (formData) => {
    const res = await api.post('/api/claims/submit', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return res.data
  },

  listClaims: async () => (await api.get('/api/claims')).data,

  getClaim: async (claimId) => (await api.get(`/api/claims/${claimId}`)).data,

  imageUrl: (claimId, filename) =>
    `${API_BASE_URL}/api/claims/${claimId}/image/${encodeURIComponent(filename)}`,

  submitReview: async (claimId, decision) => {
    const res = await api.post(`/api/claims/${claimId}/review`, decision)
    return res.data
  },
}

export default api
