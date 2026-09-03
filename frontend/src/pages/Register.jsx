import { useState } from "react"
import axios from "axios"

const API = import.meta.env.VITE_API_URL || "http://localhost:8000"
const BRANCHES = ["CS", "IT", "ECE", "ME", "Civil", "Chemical"]

export default function Register({ onSuccess, onLogin }) {
  const [step, setStep] = useState(1)
  const [form, setForm] = useState({
    name: "", email: "", password: "",
    branch: "CS", year: 2, skills: "", cgpa: ""
  })
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(false)

  const next = () => {
    if (!form.name || !form.email || !form.password)
      return setError("Please fill in all fields.")
    setError(""); setStep(2)
  }

  const handleRegister = async () => {
    if (!form.skills) return setError("Please add at least one skill.")
    setLoading(true); setError("")
    try {
      const res = await axios.post(`${API}/register`, {
        ...form, year: parseInt(form.year), cgpa: parseFloat(form.cgpa) || null
      })
      localStorage.setItem("token", res.data.token)
      onSuccess(res.data.user)
    } catch (e) {
      const detail = e.response?.data?.detail
      // FastAPI/pydantic validation errors (422, e.g. invalid email format
      // or a too-short password) return `detail` as an array of error
      // objects, not a string — rendering that array directly as a React
      // child would throw. Other failures (e.g. "Email already
      // registered") already return a plain string.
      const message = Array.isArray(detail) ? detail.map(d => d.msg).join(" ") : detail
      setError(message || "Registration failed. Try again.")
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
          <h1 style={s.tagline}>Your next big opportunity is one match away.</h1>
          <div style={s.steps}>
            {["Basic info", "Academic profile"].map((label, i) => (
              <div key={i} style={s.stepRow}>
                <div style={{ ...s.stepDot, background: step > i ? "white" : "rgba(255,255,255,0.3)" }} />
                <span style={{ ...s.stepLabel, color: step > i ? "white" : "rgba(255,255,255,0.6)" }}>
                  {label}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
      <div style={s.right}>
        <div style={s.formCard}>
          <h2 style={s.formTitle}>Create account</h2>
          <p style={s.formSub}>Step {step} of 2 — {step === 1 ? "Basic information" : "Academic profile"}</p>
          <div style={s.progressBar}>
            <div style={{ ...s.progressFill, width: step === 1 ? "50%" : "100%" }} />
          </div>
          {error && <div style={s.error}>{error}</div>}

          {step === 1 ? (
            <>
              <label style={s.label}>Full name</label>
              <input style={s.input} placeholder="Aryan Sharma"
                value={form.name} onChange={e => setForm({...form, name: e.target.value})} />
              <label style={s.label}>Email</label>
              <input style={s.input} type="email" placeholder="you@college.edu"
                value={form.email} onChange={e => setForm({...form, email: e.target.value})} />
              <label style={s.label}>Password</label>
              <input style={s.input} type="password" placeholder="Min 6 characters"
                value={form.password} onChange={e => setForm({...form, password: e.target.value})} />
              <button style={s.btn} onClick={next}>Continue</button>
            </>
          ) : (
            <>
              <label style={s.label}>Branch</label>
              <select style={s.input} value={form.branch}
                onChange={e => setForm({...form, branch: e.target.value})}>
                {BRANCHES.map(b => <option key={b}>{b}</option>)}
              </select>
              <label style={s.label}>Year of study</label>
              <select style={s.input} value={form.year}
                onChange={e => setForm({...form, year: e.target.value})}>
                {[1,2,3,4].map(y =>
                  <option key={y} value={y}>{y === 1 ? "1st" : y === 2 ? "2nd" : y === 3 ? "3rd" : "4th"} Year</option>)}
              </select>
              <label style={s.label}>CGPA</label>
              <input style={s.input} placeholder="e.g. 8.5"
                value={form.cgpa} onChange={e => setForm({...form, cgpa: e.target.value})} />
              <label style={s.label}>Skills <span style={{ color: "#999", fontWeight: 400 }}>(comma separated)</span></label>
              <input style={s.input} placeholder="Python, React, ML, SQL"
                value={form.skills} onChange={e => setForm({...form, skills: e.target.value})} />
              <div style={{ display: "flex", gap: "10px" }}>
                <button style={s.btnBack} onClick={() => setStep(1)}>Back</button>
                <button style={{ ...s.btn, flex: 1, opacity: loading ? 0.7 : 1 }}
                  onClick={handleRegister} disabled={loading}>
                  {loading ? "Creating account..." : "Create account"}
                </button>
              </div>
            </>
          )}

          <p style={s.loginLink}>
            Already on OpportunityMatch?{" "}
            <span style={s.link} onClick={onLogin}>Sign in</span>
          </p>
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
  tagline: { color: "white", fontSize: "28px", fontWeight: "300", lineHeight: "1.3", marginBottom: "2rem" },
  steps: { display: "flex", flexDirection: "column", gap: "12px" },
  stepRow: { display: "flex", alignItems: "center", gap: "10px" },
  stepDot: { width: "8px", height: "8px", borderRadius: "50%" },
  stepLabel: { fontSize: "14px" },
  right: { width: "480px", display: "flex", alignItems: "center",
    justifyContent: "center", padding: "2rem", background: "#F3F2EF" },
  formCard: { width: "100%", maxWidth: "360px", background: "white",
    padding: "2rem", borderRadius: "8px", border: "1px solid #dce6f1" },
  formTitle: { fontSize: "22px", fontWeight: "600", marginBottom: "4px" },
  formSub: { fontSize: "13px", color: "#666", marginBottom: "12px" },
  progressBar: { height: "3px", background: "#e0e0e0", borderRadius: "2px", marginBottom: "1.5rem" },
  progressFill: { height: "100%", background: "#0A66C2", borderRadius: "2px", transition: "width 0.3s" },
  error: { background: "#FEE2E2", color: "#B91C1C", padding: "10px 12px",
    borderRadius: "6px", fontSize: "13px", marginBottom: "1rem" },
  label: { display: "block", fontSize: "13px", fontWeight: "500", color: "#444", marginBottom: "5px" },
  input: { width: "100%", padding: "10px 12px", border: "1px solid #ccc",
    borderRadius: "4px", fontSize: "14px", marginBottom: "1rem" },
  btn: { width: "100%", padding: "12px", background: "#0A66C2", color: "white",
    border: "none", borderRadius: "24px", fontSize: "15px", fontWeight: "600", cursor: "pointer" },
  btnBack: { padding: "12px 20px", background: "white", color: "#666",
    border: "1px solid #ccc", borderRadius: "24px", fontSize: "14px", cursor: "pointer" },
  loginLink: { textAlign: "center", fontSize: "13px", color: "#666", marginTop: "1.25rem" },
  link: { color: "#0A66C2", fontWeight: "600", cursor: "pointer" }
}
