import { useState } from "react"
import axios from "axios"

const API = import.meta.env.VITE_API_URL || "http://localhost:8000"

export default function Login({ onSuccess, onRegister }) {
  const [form, setForm] = useState({ email: "", password: "" })
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(false)

  const handleLogin = async () => {
    if (!form.email || !form.password) return setError("Please fill in all fields.")
    setLoading(true); setError("")
    try {
      const res = await axios.post(`${API}/login`, form)
      localStorage.setItem("token", res.data.token)
      onSuccess(res.data.user)
    } catch (e) {
      setError(e.response?.data?.detail || "Incorrect email or password.")
    }
    setLoading(false)
  }

  return (
    <div style={s.page}>
      <div style={s.left}>
        <div style={s.leftInner}>
          <div style={s.brand}>
            <div style={s.brandIcon}>OM</div>
            <span style={s.brandName}>OpportunityMatch</span>
          </div>
          <h1 style={s.tagline}>Find opportunities that match your skills and goals.</h1>
          <p style={s.taglineSub}>Internships, hackathons, scholarships — all in one place, ranked for you.</p>
        </div>
      </div>
      <div style={s.right}>
        <div style={s.formCard}>
          <h2 style={s.formTitle}>Sign in</h2>
          <p style={s.formSub}>Stay updated on your professional world</p>
          {error && <div style={s.error}>{error}</div>}
          <label style={s.label}>Email</label>
          <input style={s.input} type="email" placeholder="you@college.edu"
            value={form.email} onChange={e => setForm({...form, email: e.target.value})}
            onKeyDown={e => e.key === "Enter" && handleLogin()} />
          <label style={s.label}>Password</label>
          <input style={s.input} type="password" placeholder="••••••••"
            value={form.password} onChange={e => setForm({...form, password: e.target.value})}
            onKeyDown={e => e.key === "Enter" && handleLogin()} />
          <button style={{ ...s.btn, opacity: loading ? 0.7 : 1 }}
            onClick={handleLogin} disabled={loading}>
            {loading ? "Signing in..." : "Sign in"}
          </button>
          <div style={s.divider}><span style={s.dividerText}>or</span></div>
          <button style={s.btnOutline} onClick={onRegister}>
            Join OpportunityMatch
          </button>
        </div>
      </div>
    </div>
  )
}

const s = {
  page: { display: "flex", minHeight: "100vh" },
  left: { flex: 1, background: "#0A66C2", display: "flex", alignItems: "flex-end",
    padding: "3rem", minHeight: "100vh" },
  leftInner: { maxWidth: "380px" },
  brand: { display: "flex", alignItems: "center", gap: "10px", marginBottom: "3rem" },
  brandIcon: { width: "36px", height: "36px", background: "white", borderRadius: "8px",
    display: "flex", alignItems: "center", justifyContent: "center",
    fontSize: "12px", fontWeight: "700", color: "#0A66C2" },
  brandName: { color: "white", fontSize: "18px", fontWeight: "600" },
  tagline: { color: "white", fontSize: "32px", fontWeight: "300", lineHeight: "1.3", marginBottom: "1rem" },
  taglineSub: { color: "rgba(255,255,255,0.75)", fontSize: "15px", lineHeight: "1.6" },
  right: { width: "480px", display: "flex", alignItems: "center", justifyContent: "center",
    padding: "2rem", background: "#F3F2EF" },
  formCard: { width: "100%", maxWidth: "360px", background: "white", padding: "2rem",
    borderRadius: "8px", border: "1px solid #dce6f1" },
  formTitle: { fontSize: "24px", fontWeight: "600", marginBottom: "4px" },
  formSub: { fontSize: "14px", color: "#666", marginBottom: "1.5rem" },
  error: { background: "#FEE2E2", color: "#B91C1C", padding: "10px 12px",
    borderRadius: "6px", fontSize: "13px", marginBottom: "1rem" },
  label: { display: "block", fontSize: "13px", fontWeight: "500", color: "#444", marginBottom: "5px" },
  input: { width: "100%", padding: "10px 12px", border: "1px solid #ccc",
    borderRadius: "4px", fontSize: "14px", marginBottom: "1rem" },
  btn: { width: "100%", padding: "12px", background: "#0A66C2", color: "white",
    border: "none", borderRadius: "24px", fontSize: "15px", fontWeight: "600",
    cursor: "pointer", marginBottom: "1rem" },
  divider: { textAlign: "center", borderTop: "1px solid #e0e0e0",
    position: "relative", margin: "1rem 0" },
  dividerText: { background: "white", padding: "0 10px", fontSize: "13px",
    color: "#999", position: "relative", top: "-10px" },
  btnOutline: { width: "100%", padding: "11px", background: "white",
    color: "#0A66C2", border: "2px solid #0A66C2", borderRadius: "24px",
    fontSize: "15px", fontWeight: "600", cursor: "pointer" }
}
