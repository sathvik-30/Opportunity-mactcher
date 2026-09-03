/**
 * hooks/useSaved.js — Phase 5
 * ───────────────────────────────────────────────────────────────
 * CHANGED: saved opportunities now live in the backend database
 * (SavedOpportunityTable) instead of browser localStorage.
 *
 * External interface is UNCHANGED on purpose — { saved, toggle, isSaved }
 * — so Dashboard.jsx and SavedView.jsx need zero modifications.
 * `loading` is a new, optional field; existing callers that ignore it
 * are unaffected.
 *
 * Auth: reuses the JWT already stored by Login.jsx/Register.jsx under
 * localStorage "token" — no new auth mechanism introduced.
 *
 * Migration: any opportunities saved locally before Phase 5 (under the
 * old "om_saved" key) are uploaded to the backend once, using only the
 * real opportunity `id` each item already carries — never fabricated.
 * A one-time flag prevents re-uploading on every login.
 */
import { useState, useEffect, useCallback, useRef } from "react"
import axios from "axios"

const API = import.meta.env.VITE_API_URL || "http://localhost:8000"
const LEGACY_KEY = "om_saved"
const MIGRATION_FLAG_KEY = "om_saved_migrated_v1"

function authHeaders() {
  const token = localStorage.getItem("token")
  return token ? { Authorization: `Bearer ${token}` } : null
}

export function useSaved() {
  const [saved, setSaved] = useState([])
  const [loading, setLoading] = useState(true)
  const migrating = useRef(false)

  const fetchSaved = useCallback(async () => {
    const headers = authHeaders()
    if (!headers) {
      setSaved([])
      setLoading(false)
      return []
    }
    try {
      const res = await axios.get(`${API}/saved`, { headers })
      const list = res.data.saved || []
      setSaved(list)
      return list
    } catch {
      // Not fatal — Saved tab just shows empty until the next successful fetch.
      setSaved([])
      return []
    } finally {
      setLoading(false)
    }
  }, [])

  // On mount: load from DB, then migrate any leftover localStorage saves once.
  useEffect(() => {
    (async () => {
      const dbSaved = await fetchSaved()
      const headers = authHeaders()
      if (!headers || migrating.current) return
      if (localStorage.getItem(MIGRATION_FLAG_KEY)) return

      let legacy = []
      try {
        legacy = JSON.parse(localStorage.getItem(LEGACY_KEY) || "[]")
      } catch {
        legacy = []
      }

      if (!legacy.length) {
        localStorage.setItem(MIGRATION_FLAG_KEY, "true")
        return
      }

      migrating.current = true
      const existingIds = new Set(dbSaved.map(s => s.id))
      const toMigrate = legacy.filter(item => item?.id && !existingIds.has(item.id))

      for (const item of toMigrate) {
        try {
          await axios.post(`${API}/saved`, { opportunity_id: item.id }, { headers })
        } catch {
          // Item may no longer exist on the backend (expired/removed listing) —
          // skip it silently rather than inventing data or blocking migration.
        }
      }

      if (toMigrate.length) await fetchSaved()
      localStorage.setItem(MIGRATION_FLAG_KEY, "true")
      localStorage.removeItem(LEGACY_KEY)
      migrating.current = false
    })()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const isSaved = useCallback(
    (id) => saved.some(s => s.id === id),
    [saved]
  )

  const toggle = useCallback(async (opp) => {
    const headers = authHeaders()
    if (!headers) return

    const alreadySaved = saved.some(s => s.id === opp.id)

    if (alreadySaved) {
      const prev = saved
      setSaved(prev.filter(s => s.id !== opp.id))
      try {
        await axios.delete(`${API}/saved/${opp.id}`, { headers })
      } catch {
        setSaved(prev) // restore UI state — the delete never actually happened
        alert("Could not remove saved opportunity. Please try again.")
      }
    } else {
      const prev = saved
      const optimistic = { ...opp, savedAt: new Date().toISOString() }
      setSaved([optimistic, ...prev])
      try {
        await axios.post(`${API}/saved`, { opportunity_id: opp.id }, { headers })
      } catch (err) {
        if (err.response?.status === 409) {
          // Already saved server-side (e.g. saved from another device) —
          // keep the optimistic UI state, just quietly resync.
          fetchSaved()
        } else {
          setSaved(prev) // restore — the save never actually happened
          if (err.response?.status === 401) {
            alert("Your session has expired. Please log in again.")
          } else {
            alert("Could not save opportunity. Please try again.")
          }
        }
      }
    }
  }, [saved, fetchSaved])

  return { saved, toggle, isSaved, loading }
}
