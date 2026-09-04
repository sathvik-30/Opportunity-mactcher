/**
 * pages/AdminDashboard.jsx — Phase 8
 * ───────────────────────────────────────────────────────────────
 * NEW. Reuses the existing design language (colors, radii, shadows
 * via the same CSS custom properties used throughout the app) —
 * no new chart library added (none existed before this phase), so
 * "charts" here are simple styled bar rows, matching how the rest
 * of the app already builds visuals with plain divs (see TopNavbar,
 * OpportunityCard). This keeps the bundle small and the visual
 * language consistent rather than introducing Recharts/Chart.js
 * for a handful of bars.
 *
 * Backend enforcement is the real security boundary — every call
 * here hits an /admin/* route protected by require_admin server-side.
 * This component only decides whether to RENDER the page; it never
 * grants access on its own.
 */
import { useState, useEffect, useCallback } from "react"
import axios from "axios"

const API = import.meta.env.VITE_API_URL || "http://localhost:8000"

function authHeaders() {
  const token = localStorage.getItem("token")
  return token ? { Authorization: `Bearer ${token}` } : null
}

function Card({ label, value, sub }) {
  return (
    <div style={{ background:"white", border:"1px solid var(--gray-200)", borderRadius:"var(--radius-lg)",
      padding:"18px 20px", minWidth:0 }}>
      <div style={{ fontSize:12, color:"var(--gray-500)", fontWeight:600, textTransform:"uppercase",
        letterSpacing:"0.04em", marginBottom:6 }}>{label}</div>
      <div style={{ fontSize:26, fontWeight:700, color:"var(--gray-900)" }}>{value}</div>
      {sub && <div style={{ fontSize:12, color:"var(--gray-400)", marginTop:4 }}>{sub}</div>}
    </div>
  )
}

function SectionTitle({ children }) {
  return <h3 style={{ fontSize:15, fontWeight:700, color:"var(--gray-800)", margin:"28px 0 12px 0" }}>{children}</h3>
}

function BarRow({ label, value, max, color = "var(--blue)" }) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0
  return (
    <div style={{ marginBottom:10 }}>
      <div style={{ display:"flex", justifyContent:"space-between", fontSize:12, color:"var(--gray-600)", marginBottom:3 }}>
        <span>{label}</span><span style={{ fontWeight:600 }}>{value}</span>
      </div>
      <div style={{ height:8, background:"var(--gray-100)", borderRadius:4, overflow:"hidden" }}>
        <div style={{ height:"100%", width:`${pct}%`, background:color, borderRadius:4, transition:"width 0.3s ease" }} />
      </div>
    </div>
  )
}

function StatusBadge({ status }) {
  const colors = {
    Healthy: { bg:"#dcfce7", fg:"#16a34a" },
    Warning: { bg:"#fef3c7", fg:"#d97706" },
    Failed:  { bg:"#fee2e2", fg:"#dc2626" },
    success: { bg:"#dcfce7", fg:"#16a34a" },
    failed:  { bg:"#fee2e2", fg:"#dc2626" },
    running: { bg:"#dbeafe", fg:"#2563eb" },
  }
  const c = colors[status] || { bg:"var(--gray-100)", fg:"var(--gray-600)" }
  return (
    <span style={{ background:c.bg, color:c.fg, fontSize:11, fontWeight:700, padding:"3px 9px",
      borderRadius:12, textTransform:"capitalize" }}>{status}</span>
  )
}

function timeAgo(iso) {
  if (!iso) return "—"
  const diffMs = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diffMs / 60000)
  if (mins < 1) return "just now"
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.floor(hrs / 24)}d ago`
}

export default function AdminDashboard() {
  const [stats, setStats] = useState(null)
  const [scrapers, setScrapers] = useState(null)
  const [users, setUsers] = useState(null)
  const [notifStats, setNotifStats] = useState(null)
  const [emailStats, setEmailStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [userPage, setUserPage] = useState(1)
  const [triggering, setTriggering] = useState(false)
  const [lastRefreshed, setLastRefreshed] = useState(null)

  const fetchAll = useCallback(async (page = userPage) => {
    const headers = authHeaders()
    if (!headers) { setError("Not authenticated"); setLoading(false); return }
    try {
      const [s, sc, u, n, e] = await Promise.all([
        axios.get(`${API}/admin/stats`, { headers }),
        axios.get(`${API}/admin/scrapers?limit=15`, { headers }),
        axios.get(`${API}/admin/users?page=${page}&limit=10`, { headers }),
        axios.get(`${API}/admin/notifications`, { headers }),
        axios.get(`${API}/admin/emails?limit=10`, { headers }),
      ])
      setStats(s.data); setScrapers(sc.data); setUsers(u.data)
      setNotifStats(n.data); setEmailStats(e.data)
      setError(null)
      setLastRefreshed(new Date().toISOString())
    } catch (err) {
      if (err.response?.status === 403) setError("Access denied — admin privileges required.")
      else if (err.response?.status === 401) setError("Session expired — please log in again.")
      else setError("Could not load admin dashboard. Please try again.")
    } finally {
      setLoading(false)
    }
  }, [userPage])

  useEffect(() => {
    (async () => { await fetchAll(userPage) })()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userPage])

  // Auto-refresh every 45s (per Phase 8 "30-60s" guidance) — not aggressive polling.
  useEffect(() => {
    const id = setInterval(() => fetchAll(userPage), 45000)
    return () => clearInterval(id)
  }, [fetchAll, userPage])

  const runScraper = async () => {
    const headers = authHeaders()
    if (!headers) return
    setTriggering(true)
    try {
      await axios.post(`${API}/admin/trigger-scraper`, {}, { headers })
      await fetchAll(userPage)
    } catch {
      alert("Could not trigger scraper. Check the scraper logs for details.")
    } finally {
      setTriggering(false)
    }
  }

  if (loading) {
    return <div style={{ padding:40, textAlign:"center", color:"var(--gray-400)" }}>Loading admin dashboard…</div>
  }

  if (error) {
    return (
      <div style={{ padding:40, textAlign:"center" }}>
        <div style={{ fontSize:32, marginBottom:8 }}>🔒</div>
        <p style={{ color:"var(--gray-600)", fontSize:14 }}>{error}</p>
      </div>
    )
  }

  const typeCounts = stats?.opportunities?.by_type || {}
  const maxType = Math.max(1, ...Object.values(typeCounts))
  const sourceEntries = scrapers?.health?.map(h => [h.source, h.runs_sampled]) || []
  const maxSource = Math.max(1, ...sourceEntries.map(([, v]) => v))

  return (
    <div style={{ padding:"4px 4px 40px 4px" }}>
      <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", flexWrap:"wrap", gap:12, marginBottom:8 }}>
        <div>
          <h2 style={{ fontSize:20, fontWeight:700, color:"var(--gray-900)", margin:0 }}>System Overview</h2>
          {lastRefreshed && (
            <p style={{ fontSize:12, color:"var(--gray-400)", margin:"2px 0 0 0" }}>
              Last refreshed {timeAgo(lastRefreshed)} · auto-refreshes every 45s
            </p>
          )}
        </div>
        <div style={{ display:"flex", gap:8 }}>
          <button onClick={() => fetchAll(userPage)} style={{
            padding:"8px 16px", borderRadius:"var(--radius)", border:"1px solid var(--gray-200)",
            background:"white", fontSize:13, fontWeight:600, cursor:"pointer", color:"var(--gray-700)"
          }}>Refresh</button>
          <button onClick={runScraper} disabled={triggering} style={{
            padding:"8px 16px", borderRadius:"var(--radius)", border:"none",
            background:"var(--blue)", color:"white", fontSize:13, fontWeight:600,
            cursor: triggering ? "wait" : "pointer", opacity: triggering ? 0.7 : 1
          }}>{triggering ? "Running…" : "Run Scraper"}</button>
        </div>
      </div>

      {/* Overview cards */}
      <div style={{ display:"grid", gridTemplateColumns:"repeat(auto-fit, minmax(160px, 1fr))", gap:14, marginTop:16 }}>
        <Card label="Total Users" value={stats?.users?.total ?? 0} sub={`${stats?.users?.active_engaged ?? 0} engaged`} />
        <Card label="Active Opportunities" value={stats?.opportunities?.active ?? 0}
          sub={`${stats?.opportunities?.total ?? 0} total`} />
        <Card label="Notifications" value={stats?.notifications?.total ?? 0}
          sub={`${stats?.notifications?.unread ?? 0} unread`} />
        <Card label="Emails Sent" value={stats?.emails?.sent ?? 0}
          sub={`${stats?.emails?.failed ?? 0} failed`} />
      </div>

      {/* Opportunity overview */}
      <SectionTitle>Opportunity Overview</SectionTitle>
      <div style={{ display:"grid", gridTemplateColumns:"repeat(auto-fit, minmax(260px, 1fr))", gap:16 }}>
        <div style={{ background:"white", border:"1px solid var(--gray-200)", borderRadius:"var(--radius-lg)", padding:18 }}>
          <div style={{ fontSize:13, fontWeight:700, color:"var(--gray-700)", marginBottom:12 }}>By Type</div>
          {Object.entries(typeCounts).map(([type, count]) => (
            <BarRow key={type} label={type.charAt(0).toUpperCase()+type.slice(1)} value={count} max={maxType} />
          ))}
        </div>
        <div style={{ background:"white", border:"1px solid var(--gray-200)", borderRadius:"var(--radius-lg)", padding:18 }}>
          <div style={{ fontSize:13, fontWeight:700, color:"var(--gray-700)", marginBottom:12 }}>Scraper Runs by Source (sampled)</div>
          {sourceEntries.length === 0 && <p style={{ fontSize:13, color:"var(--gray-400)" }}>No scraper runs recorded yet.</p>}
          {sourceEntries.map(([src, count]) => (
            <BarRow key={src} label={src} value={count} max={maxSource} color="#6D28D9" />
          ))}
        </div>
      </div>

      {/* Scraper health */}
      <SectionTitle>Scraper Health</SectionTitle>
      <div style={{ background:"white", border:"1px solid var(--gray-200)", borderRadius:"var(--radius-lg)", overflow:"auto" }}>
        <table style={{ width:"100%", borderCollapse:"collapse", fontSize:13, minWidth:600 }}>
          <thead>
            <tr style={{ borderBottom:"1px solid var(--gray-100)", textAlign:"left" }}>
              {["Source","Status","Last Run","Success Rate","Last Failure"].map(h => (
                <th key={h} style={{ padding:"10px 14px", color:"var(--gray-500)", fontWeight:600, fontSize:11,
                  textTransform:"uppercase" }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {(scrapers?.health || []).map(h => (
              <tr key={h.source} style={{ borderBottom:"1px solid var(--gray-50)" }}>
                <td style={{ padding:"10px 14px", fontWeight:600, color:"var(--gray-800)" }}>{h.source}</td>
                <td style={{ padding:"10px 14px" }}><StatusBadge status={h.status} /></td>
                <td style={{ padding:"10px 14px", color:"var(--gray-600)" }}>{timeAgo(h.last_run_at)}</td>
                <td style={{ padding:"10px 14px", color:"var(--gray-600)" }}>{h.success_rate_pct}%</td>
                <td style={{ padding:"10px 14px", color:"var(--gray-500)", fontSize:12 }}>
                  {h.last_failure_reason ? h.last_failure_reason.slice(0, 60) : "—"}
                </td>
              </tr>
            ))}
            {(!scrapers?.health || scrapers.health.length === 0) && (
              <tr><td colSpan={5} style={{ padding:16, textAlign:"center", color:"var(--gray-400)" }}>No scraper data yet.</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Recent activity */}
      <SectionTitle>Recent Activity</SectionTitle>
      <div style={{ display:"grid", gridTemplateColumns:"repeat(auto-fit, minmax(260px, 1fr))", gap:16 }}>
        <div style={{ background:"white", border:"1px solid var(--gray-200)", borderRadius:"var(--radius-lg)", padding:16 }}>
          <div style={{ fontSize:13, fontWeight:700, color:"var(--gray-700)", marginBottom:10 }}>Recent Scraper Runs</div>
          {(scrapers?.logs || []).slice(0, 6).map(l => (
            <div key={l.id} style={{ display:"flex", justifyContent:"space-between", alignItems:"center",
              padding:"6px 0", borderBottom:"1px solid var(--gray-50)", fontSize:12 }}>
              <span style={{ color:"var(--gray-700)" }}>{l.source}</span>
              <span style={{ display:"flex", gap:8, alignItems:"center" }}>
                <span style={{ color:"var(--gray-400)" }}>{timeAgo(l.started_at)}</span>
                <StatusBadge status={l.status} />
              </span>
            </div>
          ))}
          {(!scrapers?.logs || scrapers.logs.length === 0) && <p style={{ fontSize:12, color:"var(--gray-400)" }}>No runs yet.</p>}
        </div>

        <div style={{ background:"white", border:"1px solid var(--gray-200)", borderRadius:"var(--radius-lg)", padding:16 }}>
          <div style={{ fontSize:13, fontWeight:700, color:"var(--gray-700)", marginBottom:10 }}>Recent Users</div>
          {(users?.users || []).slice(0, 6).map(u => (
            <div key={u.id} style={{ display:"flex", justifyContent:"space-between", alignItems:"center",
              padding:"6px 0", borderBottom:"1px solid var(--gray-50)", fontSize:12 }}>
              <span style={{ color:"var(--gray-700)" }}>{u.name}</span>
              <span style={{ color:"var(--gray-400)" }}>{timeAgo(u.created_at)}</span>
            </div>
          ))}
          {(!users?.users || users.users.length === 0) && <p style={{ fontSize:12, color:"var(--gray-400)" }}>No users yet.</p>}
        </div>

        <div style={{ background:"white", border:"1px solid var(--gray-200)", borderRadius:"var(--radius-lg)", padding:16 }}>
          <div style={{ fontSize:13, fontWeight:700, color:"var(--gray-700)", marginBottom:10 }}>Top Matched Opportunities</div>
          {(notifStats?.top_matched_opportunities || []).map(t => (
            <div key={t.opportunity_id} style={{ display:"flex", justifyContent:"space-between", alignItems:"center",
              padding:"6px 0", borderBottom:"1px solid var(--gray-50)", fontSize:12 }}>
              <span style={{ color:"var(--gray-700)", overflow:"hidden", textOverflow:"ellipsis",
                whiteSpace:"nowrap", maxWidth:160 }}>{t.title}</span>
              <span style={{ color:"var(--blue)", fontWeight:600 }}>{t.notification_count}×</span>
            </div>
          ))}
          {(!notifStats?.top_matched_opportunities || notifStats.top_matched_opportunities.length === 0) && (
            <p style={{ fontSize:12, color:"var(--gray-400)" }}>No matches recorded yet.</p>
          )}
        </div>
      </div>

      {/* Email health */}
      <SectionTitle>Email Health</SectionTitle>
      <div style={{ display:"grid", gridTemplateColumns:"repeat(auto-fit, minmax(140px, 1fr))", gap:14 }}>
        <Card label="Sent" value={emailStats?.sent ?? 0} />
        <Card label="Failed" value={emailStats?.failed ?? 0} />
        <Card label="Pending" value={emailStats?.pending ?? 0} />
        <Card label="Success Rate" value={emailStats?.success_rate_pct != null ? `${emailStats.success_rate_pct}%` : "—"} />
      </div>
      {emailStats?.recent_failed?.items?.length > 0 && (
        <div style={{ background:"white", border:"1px solid var(--gray-200)", borderRadius:"var(--radius-lg)",
          padding:16, marginTop:14, overflow:"auto" }}>
          <div style={{ fontSize:13, fontWeight:700, color:"var(--gray-700)", marginBottom:10 }}>Recent Failed Emails</div>
          {emailStats.recent_failed.items.map(f => (
            <div key={f.id} style={{ padding:"6px 0", borderBottom:"1px solid var(--gray-50)", fontSize:12 }}>
              <div style={{ display:"flex", justifyContent:"space-between" }}>
                <span style={{ color:"var(--gray-700)" }}>{f.recipient_email}</span>
                <span style={{ color:"var(--gray-400)" }}>{timeAgo(f.created_at)}</span>
              </div>
              <div style={{ color:"var(--gray-500)", fontSize:11, marginTop:2 }}>{f.error_message}</div>
            </div>
          ))}
        </div>
      )}

      {/* Users table with pagination */}
      <SectionTitle>Users</SectionTitle>
      <div style={{ background:"white", border:"1px solid var(--gray-200)", borderRadius:"var(--radius-lg)", overflow:"auto" }}>
        <table style={{ width:"100%", borderCollapse:"collapse", fontSize:13, minWidth:600 }}>
          <thead>
            <tr style={{ borderBottom:"1px solid var(--gray-100)", textAlign:"left" }}>
              {["Name","Email","Branch/Year","Saved","Notifications","Joined"].map(h => (
                <th key={h} style={{ padding:"10px 14px", color:"var(--gray-500)", fontWeight:600, fontSize:11,
                  textTransform:"uppercase" }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {(users?.users || []).map(u => (
              <tr key={u.id} style={{ borderBottom:"1px solid var(--gray-50)" }}>
                <td style={{ padding:"10px 14px", fontWeight:600, color:"var(--gray-800)" }}>
                  {u.name}{u.is_admin && <span style={{ marginLeft:6, fontSize:10, background:"var(--blue-light)",
                    color:"var(--blue)", padding:"1px 6px", borderRadius:8 }}>admin</span>}
                </td>
                <td style={{ padding:"10px 14px", color:"var(--gray-600)" }}>{u.email}</td>
                <td style={{ padding:"10px 14px", color:"var(--gray-600)" }}>{u.branch} · Y{u.year}</td>
                <td style={{ padding:"10px 14px", color:"var(--gray-600)" }}>{u.saved_count}</td>
                <td style={{ padding:"10px 14px", color:"var(--gray-600)" }}>{u.notification_count}</td>
                <td style={{ padding:"10px 14px", color:"var(--gray-400)" }}>{timeAgo(u.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {users && users.total_pages > 1 && (
        <div style={{ display:"flex", gap:8, justifyContent:"center", marginTop:12 }}>
          <button onClick={() => setUserPage(p => Math.max(1, p-1))} disabled={userPage<=1}
            style={{ padding:"6px 14px", borderRadius:"var(--radius)", border:"1px solid var(--gray-200)",
              background:"white", fontSize:13, cursor: userPage<=1 ? "default":"pointer", opacity: userPage<=1?0.5:1 }}>
            Previous
          </button>
          <span style={{ fontSize:13, color:"var(--gray-500)", alignSelf:"center" }}>
            Page {users.page} of {users.total_pages}
          </span>
          <button onClick={() => setUserPage(p => p+1)} disabled={userPage>=users.total_pages}
            style={{ padding:"6px 14px", borderRadius:"var(--radius)", border:"1px solid var(--gray-200)",
              background:"white", fontSize:13, cursor: userPage>=users.total_pages ? "default":"pointer",
              opacity: userPage>=users.total_pages?0.5:1 }}>
            Next
          </button>
        </div>
      )}
    </div>
  )
}
