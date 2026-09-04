import { useState, useEffect } from "react"
import axios from "axios"
import Login from "./pages/Login"
import Register from "./pages/Register"
import Dashboard from "./pages/Dashboard"

const API = import.meta.env.VITE_API_URL || "http://localhost:8000"

function App() {
  const [page, setPage] = useState("login")
  const [student, setStudent] = useState(null)
  // No stored token means there's nothing to restore — start non-restoring
  // immediately rather than flipping the flag from inside the effect.
  const [restoring, setRestoring] = useState(() => !!localStorage.getItem("token"))

  // On load, a valid stored token should restore the session instead of
  // forcing a re-login on every page refresh.
  useEffect(() => {
    const token = localStorage.getItem("token")
    if (!token) return
    axios.get(`${API}/me`, { headers: { Authorization: `Bearer ${token}` } })
      .then(res => setStudent(res.data.user))
      .catch(() => localStorage.removeItem("token")) // expired/invalid — fall back to login
      .finally(() => setRestoring(false))
  }, [])

  const handleLogout = () => {
    localStorage.removeItem("token")
    setStudent(null)
    setPage("login")
  }

  if (restoring) return <SplashScreen />
  if (student) return <Dashboard student={student} onLogout={handleLogout} />
  if (page === "register") return <Register onSuccess={setStudent} onLogin={() => setPage("login")} />
  return <Login onSuccess={setStudent} onRegister={() => setPage("register")} />
}

function SplashScreen() {
  return (
    <div style={{ minHeight:"100vh", display:"flex", alignItems:"center",
      justifyContent:"center", background:"#F3F2EF" }}>
      <div style={{ fontSize:14, color:"#666" }}>Loading…</div>
    </div>
  )
}

export default App
