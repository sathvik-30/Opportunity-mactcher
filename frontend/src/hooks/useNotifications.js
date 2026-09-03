/**
 * hooks/useNotifications.js — Phase 6
 * ───────────────────────────────────────────────────────────────
 * NEW. Connects the notification bell (currently a hardcoded inline
 * component inside TopNavbar.jsx) to the real backend notification
 * endpoints. Reuses the same JWT-in-localStorage pattern useSaved.js
 * already established — no new auth mechanism.
 */
import { useState, useEffect, useCallback } from "react"
import axios from "axios"

const API = import.meta.env.VITE_API_URL || "http://localhost:8000"

function authHeaders() {
  const token = localStorage.getItem("token")
  return token ? { Authorization: `Bearer ${token}` } : null
}

export function useNotifications() {
  const [notifications, setNotifications] = useState([])
  const [unreadCount, setUnreadCount] = useState(0)
  const [loading, setLoading] = useState(true)

  const fetchNotifications = useCallback(async () => {
    const headers = authHeaders()
    if (!headers) {
      setNotifications([])
      setUnreadCount(0)
      setLoading(false)
      return
    }
    try {
      const res = await axios.get(`${API}/notifications`, { headers })
      setNotifications(res.data.notifications || [])
      setUnreadCount(res.data.unread_count || 0)
    } catch {
      // Non-fatal — bell just shows whatever it last had (or empty).
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchNotifications()
  }, [fetchNotifications])

  const markAsRead = useCallback(async (id) => {
    const headers = authHeaders()
    if (!headers) return
    // Optimistic update
    setNotifications(prev => prev.map(n => n.id === id ? { ...n, is_read: true } : n))
    setUnreadCount(prev => Math.max(0, prev - 1))
    try {
      await axios.patch(`${API}/notifications/${id}/read`, {}, { headers })
    } catch {
      fetchNotifications() // resync on failure rather than leaving stale optimistic state
    }
  }, [fetchNotifications])

  const markAllAsRead = useCallback(async () => {
    const headers = authHeaders()
    if (!headers) return
    const prevNotifications = notifications
    const prevUnread = unreadCount
    setNotifications(prev => prev.map(n => ({ ...n, is_read: true })))
    setUnreadCount(0)
    try {
      await axios.patch(`${API}/notifications/read-all`, {}, { headers })
    } catch {
      setNotifications(prevNotifications)
      setUnreadCount(prevUnread)
    }
  }, [notifications, unreadCount])

  const deleteNotification = useCallback(async (id) => {
    const headers = authHeaders()
    if (!headers) return
    const prev = notifications
    const wasUnread = prev.find(n => n.id === id && !n.is_read)
    setNotifications(prev.filter(n => n.id !== id))
    if (wasUnread) setUnreadCount(c => Math.max(0, c - 1))
    try {
      await axios.delete(`${API}/notifications/${id}`, { headers })
    } catch {
      setNotifications(prev) // restore on failure
      if (wasUnread) setUnreadCount(c => c + 1)
    }
  }, [notifications])

  return {
    notifications,
    unreadCount,
    loading,
    refresh: fetchNotifications,
    markAsRead,
    markAllAsRead,
    deleteNotification,
  }
}
