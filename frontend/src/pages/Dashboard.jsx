import { useEffect, useState, useRef, useCallback } from "react"
import axios from "axios"
import Sidebar from "../components/layout/Sidebar"
import TopNavbar from "../components/layout/TopNavbar"
import DashboardHeader from "../components/layout/DashboardHeader"
import StatsCard from "../components/cards/StatsCard"
import OpportunityCard from "../components/cards/OpportunityCard"
import FilterPanel from "../components/filters/FilterPanel"
import SavedView from "../components/cards/SavedView"
import AdminDashboard from "./AdminDashboard"
import EmptyState from "../components/common/EmptyState"
import { SkeletonGrid, StatSkeleton } from "../components/common/LoadingSkeleton"
import { useSaved } from "../hooks/useSaved"
import { useNotifications } from "../hooks/useNotifications"

const API = import.meta.env.VITE_API_URL || "http://localhost:8000"

const DEFAULT_FILTERS = { type:"All",minScore:0,location:"",branch:"",remote:false,sortBy:"Highest Match" }

export default function Dashboard({ student: initialStudent, onLogout }) {
  const [student, setStudent]         = useState(initialStudent)
  const [results, setResults]         = useState([])
  const [loading, setLoading]         = useState(true)
  const [refreshing, setRefreshing]   = useState(false)
  const [lastUpdated, setLastUpdated] = useState(null)
  const [fetchError, setFetchError]   = useState(null)
  const [filters, setFilters]         = useState(DEFAULT_FILTERS)
  const [searchQuery, setSearchQuery] = useState("")
  const [activeTab, setActiveTab]     = useState("dashboard")
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [filterDrawer, setFilterDrawer] = useState(false)
  const [showProfile, setShowProfile] = useState(false)
  const [editForm, setEditForm]       = useState(null)
  const [saving, setSaving]           = useState(false)
  const [chatOpen, setChatOpen]       = useState(false)
  const [emailPrefSaving, setEmailPrefSaving] = useState(false)

  const { saved, toggle: toggleSave, isSaved } = useSaved()
  const { notifications, unreadCount, markAsRead, markAllAsRead } = useNotifications()

  const fetchMatches = useCallback(async (std, silent = false) => {
    const target = std || student
    if (!silent) setLoading(true)
    else setRefreshing(true)
    setFetchError(null)
    try {
      const res = await axios.post(`${API}/match`, {
        name: target.name, branch: target.branch,
        year: target.year, skills: target.skills, cgpa: target.cgpa
      })
      setResults(res.data.results || [])
      setLastUpdated(new Date())
    } catch {
      setFetchError("Could not load matches. Make sure the backend is running on port 8000.")
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [student])

  useEffect(() => {
    (async () => { await fetchMatches(student) })()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
  useEffect(() => {
    const id = setInterval(() => fetchMatches(student, true), 30000)
    return () => clearInterval(id)
  }, [student, fetchMatches])

  // Apply filters + search
  const filtered = results.filter(r => {
    const opp = r.opportunity
    if (filters.type !== "All" && opp.type !== filters.type) return false
    if (r.match_score < filters.minScore) return false
    if (filters.location && !opp.location?.toLowerCase().includes(filters.location.toLowerCase())) return false
    if (filters.branch && !opp.eligibility?.branches?.includes(filters.branch)) return false
    if (filters.remote && !opp.location?.toLowerCase().includes("remote")) return false
    if (searchQuery) {
      const q = searchQuery.toLowerCase()
      if (!opp.title?.toLowerCase().includes(q) &&
          !opp.organization?.toLowerCase().includes(q) &&
          !opp.description?.toLowerCase().includes(q) &&
          !(opp.required_skills || []).some(s => s.toLowerCase().includes(q))) return false
    }
    return true
  }).sort((a, b) => {
    if (filters.sortBy === "Highest Match") return b.match_score - a.match_score
    if (filters.sortBy === "Deadline Soon") {
      // No deadline isn't "soonest" — new Date(null) evaluates to the Unix
      // epoch (1970), which would otherwise sort undated listings above
      // every real deadline. Push them to the end instead.
      const aDeadline = a.opportunity.deadline
      const bDeadline = b.opportunity.deadline
      if (!aDeadline && !bDeadline) return 0
      if (!aDeadline) return 1
      if (!bDeadline) return -1
      return new Date(aDeadline) - new Date(bDeadline)
    }
    if (filters.sortBy === "Newest") return new Date(b.opportunity.created_at) - new Date(a.opportunity.created_at)
    return b.match_score - a.match_score
  })

  const saveProfile = async () => {
    const token = localStorage.getItem("token")
    if (!token) return
    setSaving(true)
    const payload = {
      name: editForm.name,
      branch: editForm.branch,
      year: parseInt(editForm.year),
      cgpa: parseFloat(editForm.cgpa) || null,
      skills: typeof editForm.skills === "string"
        ? editForm.skills.split(",").map(s => s.trim()).filter(Boolean)
        : editForm.skills,
    }
    try {
      const res = await axios.patch(`${API}/users/profile`, payload, {
        headers: { Authorization: `Bearer ${token}` }
      })
      const updated = { ...student, ...res.data.user }
      setStudent(updated)
      await fetchMatches(updated, false)
      setShowProfile(false)
    } catch (err) {
      alert(err.response?.data?.detail || "Could not save profile. Please try again.")
    } finally {
      setSaving(false)
    }
  }

  const toggleEmailNotifications = async () => {
    const token = localStorage.getItem("token")
    if (!token) return
    const next = !editForm.email_notifications
    setEmailPrefSaving(true)
    setEditForm({ ...editForm, email_notifications: next })
    try {
      const res = await axios.patch(
        `${API}/users/preferences`,
        { email_notifications: next },
        { headers: { Authorization: `Bearer ${token}` } }
      )
      setStudent(prev => ({ ...prev, email_notifications: res.data.user.email_notifications }))
    } catch {
      setEditForm(prev => ({ ...prev, email_notifications: !next })) // revert on failure
      alert("Could not update email notification preference. Please try again.")
    } finally {
      setEmailPrefSaving(false)
    }
  }

  const recommended = results.filter(r => r.recommended).length
  const strongMatches = results.filter(r => r.match_score >= 70).length
  const eligible = results.filter(r => r.eligibility?.eligible).length

  const mainContent = () => {
    if (activeTab === "saved") return <SavedView saved={saved} onRemove={toggleSave} />
    if (activeTab === "admin") {
      // Frontend gate is a convenience only — every /admin/* call still
      // requires require_admin server-side regardless of this check.
      if (!student?.is_admin) return <EmptyState icon="🔒" title="Access denied" subtitle="You don't have admin privileges." />
      return <AdminDashboard />
    }

    if (activeTab === "profile") return (
      <div className="fade-in">
        <h2 style={{ fontSize:18,fontWeight:700,marginBottom:16 }}>Your Profile</h2>
        <div style={{ background:"white",borderRadius:"var(--radius-lg)",
          border:"1px solid var(--gray-200)",padding:24,maxWidth:480 }}>
          {[
            { label:"Name", value: student.name },
            { label:"Branch", value: student.branch },
            { label:"Year", value: `${student.year}${student.year===1?"st":student.year===2?"nd":student.year===3?"rd":"th"} Year` },
            { label:"CGPA", value: student.cgpa || "—" },
            { label:"Skills", value: (Array.isArray(student.skills)?student.skills:[]).join(", ") },
          ].map(({label,value}) => (
            <div key={label} style={{ display:"flex",gap:16,padding:"12px 0",
              borderBottom:"1px solid var(--gray-100)" }}>
              <span style={{ fontSize:13,color:"var(--gray-500)",width:80,flexShrink:0 }}>{label}</span>
              <span style={{ fontSize:13,fontWeight:500,color:"var(--gray-800)" }}>{value}</span>
            </div>
          ))}
          <button onClick={() => { setShowProfile(true); setEditForm({ ...student, skills: Array.isArray(student.skills)?student.skills.join(", "):"" }) }}
            style={{ marginTop:16,padding:"10px 24px",background:"var(--blue)",color:"white",
              border:"none",borderRadius:"var(--radius-xl)",fontSize:13,fontWeight:600,cursor:"pointer" }}>
            Edit Profile
          </button>
        </div>
      </div>
    )

    if (activeTab === "settings") return (
      <div className="fade-in">
        <h2 style={{ fontSize:18,fontWeight:700,marginBottom:16 }}>Settings</h2>
        <div style={{ background:"white",borderRadius:"var(--radius-lg)",
          border:"1px solid var(--gray-200)",padding:24,maxWidth:480 }}>
          <p style={{ fontSize:13,color:"var(--gray-500)" }}>Settings coming soon.</p>
        </div>
      </div>
    )

    // Main dashboard tab
    return (
      <>
        <DashboardHeader student={student} />

        {/* Stats */}
        <div style={{ display:"grid",gridTemplateColumns:"repeat(auto-fill,minmax(160px,1fr))",
          gap:12,marginBottom:24 }}>
          {loading ? Array(4).fill(0).map((_,i) => <StatSkeleton key={i} />) : <>
            <StatsCard icon="📋" title="Total" value={results.length} color="#0A66C2" bg="#E8F0FE" delay={0}
              trend={{ up:true, value:"Live", label:"opportunities" }} />
            <StatsCard icon="⭐" title="Recommended" value={recommended} color="#057642" bg="#E6F4EA" delay={60}
              trend={{ up:true, value:strongMatches, label:"strong matches" }} />
            <StatsCard icon="♥" title="Saved" value={saved.length} color="#9333EA" bg="#EDE9FE" delay={120}
              trend={{ up:false, value:"Apply", label:"before deadline" }} />
            <StatsCard icon="✓" title="Eligible" value={eligible} color="#E65100" bg="#FFF3E0" delay={180}
              trend={{ up:true, value:"100%", label:"eligibility" }} />
          </>}
        </div>

        {/* Skills bar */}
        <div style={{ background:"white",borderRadius:"var(--radius-lg)",
          border:"1px solid var(--gray-200)",padding:"10px 16px",
          display:"flex",alignItems:"center",flexWrap:"wrap",gap:6,marginBottom:16 }}>
          <span style={{ fontSize:12,fontWeight:600,color:"var(--gray-500)",
            textTransform:"uppercase",letterSpacing:"0.04em",marginRight:4 }}>Your skills</span>
          {(Array.isArray(student.skills)?student.skills:[]).map((sk,i) => (
            <span key={i} style={{ fontSize:12,padding:"3px 10px",background:"var(--blue-light)",
              color:"var(--blue)",borderRadius:20,border:"1px solid #C7D7F5" }}>{sk}</span>
          ))}
          <button onClick={() => { setShowProfile(true); setEditForm({ ...student, skills: Array.isArray(student.skills)?student.skills.join(", "):"" }) }}
            style={{ fontSize:12,padding:"3px 10px",background:"white",color:"var(--blue)",
              borderRadius:20,border:"1.5px solid var(--blue)",cursor:"pointer",marginLeft:"auto" }}>
            + Edit skills
          </button>
        </div>

        {/* Error */}
        {fetchError && (
          <div style={{ background:"var(--red-light)",border:"1px solid #FECACA",color:"var(--red)",
            borderRadius:"var(--radius)",padding:"10px 14px",fontSize:13,marginBottom:16,
            display:"flex",justifyContent:"space-between",alignItems:"center" }}>
            ⚠️ {fetchError}
            <button onClick={() => setFetchError(null)} style={{ background:"none",border:"none",
              color:"var(--red)",cursor:"pointer",fontWeight:700 }}>✕</button>
          </div>
        )}

        {/* Active filter chips */}
        {(filters.type!=="All"||filters.minScore>0||filters.location||filters.branch||filters.remote||searchQuery) && (
          <div style={{ display:"flex",flexWrap:"wrap",gap:6,marginBottom:12,alignItems:"center" }}>
            <span style={{ fontSize:12,color:"var(--gray-500)" }}>Active filters:</span>
            {filters.type!=="All" && <Chip label={filters.type} onRemove={() => setFilters(f=>({...f,type:"All"}))} />}
            {filters.minScore>0 && <Chip label={`${filters.minScore}%+ match`} onRemove={() => setFilters(f=>({...f,minScore:0}))} />}
            {filters.location && <Chip label={filters.location} onRemove={() => setFilters(f=>({...f,location:""}))} />}
            {filters.branch && <Chip label={filters.branch} onRemove={() => setFilters(f=>({...f,branch:""}))} />}
            {filters.remote && <Chip label="Remote" onRemove={() => setFilters(f=>({...f,remote:false}))} />}
            {searchQuery && <Chip label={`"${searchQuery}"`} onRemove={() => setSearchQuery("")} />}
          </div>
        )}

        {/* Results count + mobile filter button */}
        <div style={{ display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:12 }}>
          <p style={{ fontSize:13,color:"var(--gray-500)" }}>
            Showing <strong style={{ color:"var(--gray-800)" }}>{filtered.length}</strong> opportunities
          </p>
          <button onClick={() => setFilterDrawer(true)} className="mobile-filter-btn"
            style={{ display:"none",padding:"7px 14px",borderRadius:20,
              border:"1.5px solid var(--gray-200)",background:"white",
              fontSize:13,cursor:"pointer",color:"var(--gray-700)" }}>
            ⚙ Filters
          </button>
        </div>

        {/* Grid */}
        {loading ? <SkeletonGrid count={6} /> : filtered.length === 0 ? (
          <EmptyState onReset={() => { setFilters(DEFAULT_FILTERS); setSearchQuery("") }} />
        ) : (
          <div style={{ display:"grid",gridTemplateColumns:"repeat(auto-fill,minmax(300px,1fr))",gap:16 }}>
            {filtered.map((r,i) => (
              <div key={i} style={{ animationDelay:`${i*40}ms` }}>
                <OpportunityCard
                  result={r} student={student}
                  isSaved={isSaved(r.opportunity.id)}
                  onSave={() => toggleSave(r.opportunity)}
                />
              </div>
            ))}
          </div>
        )}
      </>
    )
  }

  return (
    <div style={{ minHeight:"100vh",background:"var(--gray-100)" }}>

      <Sidebar activeTab={activeTab} onTabChange={setActiveTab}
        student={student} onLogout={onLogout}
        mobileOpen={sidebarOpen} onMobileClose={() => setSidebarOpen(false)} />

      <TopNavbar student={student} onLogout={onLogout}
        searchQuery={searchQuery} onSearch={setSearchQuery}
        onMenuToggle={() => setSidebarOpen(true)}
        onEditProfile={() => { setShowProfile(true); setEditForm({ ...student, skills: Array.isArray(student.skills)?student.skills.join(", "):"" }) }}
        refreshing={refreshing} onRefresh={() => fetchMatches(student,true)}
        lastUpdated={lastUpdated}
        notifications={notifications} unreadCount={unreadCount}
        onMarkAllRead={markAllAsRead}
        onNotifClick={(n) => { if (!n.is_read) markAsRead(n.id) }} />

      {/* Main layout */}
      <div style={{
        marginLeft:"var(--sidebar-width)",
        paddingTop:"calc(var(--navbar-height) + 24px)",
        padding:"calc(var(--navbar-height) + 24px) 24px 40px",
      }} className="main-layout">
        <div style={{ display:"flex",gap:20,alignItems:"flex-start" }}>

          {/* Filter sidebar — only on dashboard tab */}
          {activeTab==="dashboard" && (
            <FilterPanel filters={filters} onChange={setFilters}
              onReset={() => setFilters(DEFAULT_FILTERS)}
              mobileOpen={filterDrawer} onMobileClose={() => setFilterDrawer(false)} />
          )}

          {/* Content */}
          <main style={{ flex:1,minWidth:0 }}>
            {mainContent()}
          </main>
        </div>
      </div>

      {/* Edit Profile Modal */}
      {showProfile && editForm && (
        <div style={{ position:"fixed",inset:0,background:"rgba(0,0,0,0.5)",
          display:"flex",alignItems:"center",justifyContent:"center",zIndex:500,padding:16 }}>
          <div className="scale-in" style={{ background:"white",borderRadius:"var(--radius-xl)",
            width:"100%",maxWidth:460,maxHeight:"90vh",overflow:"auto",
            boxShadow:"var(--shadow-xl)" }}>
            <div style={{ display:"flex",justifyContent:"space-between",alignItems:"center",
              padding:"20px 24px",borderBottom:"1px solid var(--gray-100)" }}>
              <h2 style={{ fontSize:18,fontWeight:700 }}>Edit Profile</h2>
              <button onClick={() => setShowProfile(false)} style={{ background:"none",border:"none",
                fontSize:20,cursor:"pointer",color:"var(--gray-500)" }}>✕</button>
            </div>
            <div style={{ padding:"20px 24px",display:"flex",flexDirection:"column",gap:16 }}>
              {[{label:"Full name",key:"name",type:"text"},{label:"CGPA",key:"cgpa",type:"number"}].map(({label,key,type}) => (
                <div key={key}>
                  <label style={{ display:"block",fontSize:12,fontWeight:600,color:"var(--gray-500)",
                    textTransform:"uppercase",letterSpacing:"0.04em",marginBottom:6 }}>{label}</label>
                  <input type={type} value={editForm[key]||""} onChange={e=>setEditForm({...editForm,[key]:e.target.value})}
                    style={{ width:"100%",padding:"10px 12px",border:"1.5px solid var(--gray-200)",
                      borderRadius:"var(--radius)",fontSize:14 }} />
                </div>
              ))}
              <div>
                <label style={{ display:"block",fontSize:12,fontWeight:600,color:"var(--gray-500)",
                  textTransform:"uppercase",letterSpacing:"0.04em",marginBottom:6 }}>Branch</label>
                <select value={editForm.branch} onChange={e=>setEditForm({...editForm,branch:e.target.value})}
                  style={{ width:"100%",padding:"10px 12px",border:"1.5px solid var(--gray-200)",
                    borderRadius:"var(--radius)",fontSize:14 }}>
                  {["CS","IT","ECE","ME","Civil","Chemical"].map(b=><option key={b}>{b}</option>)}
                </select>
              </div>
              <div>
                <label style={{ display:"block",fontSize:12,fontWeight:600,color:"var(--gray-500)",
                  textTransform:"uppercase",letterSpacing:"0.04em",marginBottom:6 }}>Year</label>
                <select value={editForm.year} onChange={e=>setEditForm({...editForm,year:e.target.value})}
                  style={{ width:"100%",padding:"10px 12px",border:"1.5px solid var(--gray-200)",
                    borderRadius:"var(--radius)",fontSize:14 }}>
                  {[1,2,3,4].map(y=><option key={y} value={y}>{y===1?"1st":y===2?"2nd":y===3?"3rd":"4th"} Year</option>)}
                </select>
              </div>
              <div>
                <label style={{ display:"block",fontSize:12,fontWeight:600,color:"var(--gray-500)",
                  textTransform:"uppercase",letterSpacing:"0.04em",marginBottom:6 }}>
                  Skills <span style={{ color:"var(--gray-400)",fontWeight:400,textTransform:"none" }}>(comma separated)</span>
                </label>
                <textarea value={editForm.skills} onChange={e=>setEditForm({...editForm,skills:e.target.value})}
                  style={{ width:"100%",padding:"10px 12px",border:"1.5px solid var(--gray-200)",
                    borderRadius:"var(--radius)",fontSize:14,height:80,resize:"vertical",fontFamily:"inherit" }} />
              </div>
              <div style={{ display:"flex",alignItems:"center",justifyContent:"space-between",
                padding:"12px 14px",background:"var(--gray-50)",borderRadius:"var(--radius)" }}>
                <div>
                  <div style={{ fontSize:13,fontWeight:600,color:"var(--gray-800)" }}>Email Notifications</div>
                  <div style={{ fontSize:12,color:"var(--gray-500)",marginTop:2 }}>
                    Receive email alerts when new opportunities match your profile.
                  </div>
                </div>
                <button onClick={toggleEmailNotifications} disabled={emailPrefSaving}
                  style={{
                    width:44,height:24,borderRadius:12,border:"none",flexShrink:0,marginLeft:12,
                    background: editForm.email_notifications ? "var(--blue)" : "var(--gray-300)",
                    position:"relative",cursor: emailPrefSaving ? "wait" : "pointer",
                    opacity: emailPrefSaving ? 0.6 : 1, transition:"var(--transition)"
                  }}>
                  <span style={{
                    position:"absolute",top:3,left: editForm.email_notifications ? 23 : 3,
                    width:18,height:18,borderRadius:"50%",background:"white",
                    transition:"var(--transition)"
                  }} />
                </button>
              </div>
              <div style={{ display:"flex",gap:10,paddingTop:4 }}>
                <button onClick={() => setShowProfile(false)}
                  style={{ flex:1,padding:11,background:"white",color:"var(--gray-600)",
                    border:"1.5px solid var(--gray-200)",borderRadius:"var(--radius-xl)",
                    fontSize:14,cursor:"pointer" }}>Cancel</button>
                <button onClick={saveProfile} disabled={saving}
                  style={{ flex:2,padding:11,background:"var(--blue)",color:"white",
                    border:"none",borderRadius:"var(--radius-xl)",fontSize:14,fontWeight:600,
                    cursor:"pointer",opacity:saving?0.7:1 }}>
                  {saving ? "Saving..." : "Save & Re-match"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* AI Chatbot */}
      <Chatbot open={chatOpen} onToggle={() => setChatOpen(o=>!o)}
        student={student} opportunities={results.map(r=>r.opportunity)} />

      <style>{`
        @media (max-width: 1023px) {
          .main-layout { margin-left: 0 !important; }
          .mobile-filter-btn { display: flex !important; }
        }
        @media (max-width: 640px) {
          .main-layout { padding: calc(var(--navbar-height) + 16px) 12px 80px !important; }
        }
      `}</style>
    </div>
  )
}

function Chip({ label, onRemove }) {
  return (
    <span style={{ display:"inline-flex",alignItems:"center",gap:5,fontSize:12,
      padding:"3px 10px",background:"var(--blue-light)",color:"var(--blue)",
      borderRadius:20,border:"1px solid #C7D7F5" }}>
      {label}
      <button onClick={onRemove} style={{ background:"none",border:"none",
        color:"var(--blue)",cursor:"pointer",fontSize:13,lineHeight:1,padding:0 }}>×</button>
    </span>
  )
}

function Chatbot({ open, onToggle, student, opportunities }) {
  const [messages, setMessages] = useState([
    { role:"assistant", text:`Hi ${student.name}! 👋 I'm your AI career advisor. Ask me anything — should you apply, what skills to learn, or I can write a cover letter!` }
  ])
  const [input, setInput]       = useState("")
  const [thinking, setThinking] = useState(false)
  const bottomRef = useRef(null)

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior:"smooth" }) }, [messages, open])

  const send = async (override) => {
    const userMsg = override || input.trim()
    if (!userMsg || thinking) return
    setInput("")
    const newMsgs = [...messages, { role:"user", text:userMsg }]
    setMessages(newMsgs)
    setThinking(true)
    try {
      const token = localStorage.getItem("token")
      if (!token) throw new Error("Please log in again.")
      // The Groq API key lives only on the backend now — this just sends
      // the conversation + opportunity context and gets a reply back.
      const res = await axios.post(`${API}/chat/advisor`, {
        messages: newMsgs.slice(1).map(m => ({ role: m.role, text: m.text })),
        opportunities: opportunities.slice(0, 8),
      }, { headers: { Authorization: `Bearer ${token}` } })
      setMessages(m => [...m, { role:"assistant", text:res.data.reply }])
    } catch (err) {
      setMessages(m => [...m, { role:"assistant", text:`Error: ${err.response?.data?.detail || err.message}` }])
    }
    setThinking(false)
  }

  return (
    <>
      <button onClick={onToggle} style={{
        position:"fixed",bottom:24,right:24,
        background: open ? "var(--gray-700)" : "linear-gradient(135deg,#0A66C2,#6D28D9)",
        color:"white",border:"none",borderRadius:28,padding:"12px 20px",
        fontSize:15,cursor:"pointer",zIndex:400,display:"flex",alignItems:"center",gap:8,
        boxShadow:"0 4px 24px rgba(0,0,0,0.2)",transition:"var(--transition)"
      }}>
        {open ? "✕" : "🤖"}{!open && <span style={{ fontSize:14,fontWeight:600 }}>AI Advisor</span>}
      </button>

      {open && (
        <div className="slide-up" style={{
          position:"fixed",bottom:80,right:24,width:360,
          background:"white",borderRadius:"var(--radius-xl)",
          boxShadow:"var(--shadow-xl)",zIndex:400,
          display:"flex",flexDirection:"column",
          border:"1px solid var(--gray-200)",maxHeight:540,overflow:"hidden"
        }}>
          <div style={{ background:"linear-gradient(135deg,#0A66C2,#6D28D9)",padding:"14px 16px",
            display:"flex",justifyContent:"space-between",alignItems:"center" }}>
            <div style={{ display:"flex",alignItems:"center",gap:10 }}>
              <div style={{ width:36,height:36,borderRadius:"50%",background:"rgba(255,255,255,0.2)",
                display:"flex",alignItems:"center",justifyContent:"center",fontSize:18 }}>🤖</div>
              <div>
                <div style={{ fontSize:14,fontWeight:600,color:"white" }}>AI Career Advisor</div>
                <div style={{ fontSize:11,color:"rgba(255,255,255,0.75)" }}>
                  {thinking ? "Typing..." : "Online · Groq AI"}
                </div>
              </div>
            </div>
            <button onClick={onToggle} style={{ background:"none",border:"none",color:"white",fontSize:16,cursor:"pointer" }}>✕</button>
          </div>

          <div style={{ flex:1,overflowY:"auto",padding:16,display:"flex",flexDirection:"column",gap:12,maxHeight:280 }}>
            {messages.map((m,i) => (
              <div key={i} style={{ display:"flex",gap:8,alignItems:"flex-end",
                justifyContent:m.role==="user"?"flex-end":"flex-start" }}>
                {m.role==="assistant" && <span style={{ fontSize:18 }}>🤖</span>}
                <div style={{
                  padding:"10px 14px",fontSize:13,lineHeight:1.5,maxWidth:"82%",
                  border:"1px solid var(--gray-200)",whiteSpace:"pre-wrap",
                  background:m.role==="user"?"var(--blue)":"white",
                  color:m.role==="user"?"white":"var(--gray-800)",
                  borderRadius:m.role==="user"?"16px 16px 4px 16px":"16px 16px 16px 4px"
                }}>{m.text}</div>
              </div>
            ))}
            {thinking && (
              <div style={{ display:"flex",gap:8,alignItems:"flex-end" }}>
                <span style={{ fontSize:18 }}>🤖</span>
                <div style={{ padding:"10px 14px",background:"white",border:"1px solid var(--gray-200)",borderRadius:"16px 16px 16px 4px" }}>
                  <span style={{ color:"var(--gray-400)",fontSize:20,letterSpacing:3 }}>···</span>
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          <div style={{ display:"flex",gap:6,padding:"4px 12px 8px",flexWrap:"wrap" }}>
            {["Should I apply to SIH?","What skills to learn?","Cover letter for Swiggy"].map((s,i) => (
              <button key={i} onClick={() => !thinking && send(s)}
                style={{ fontSize:11,padding:"4px 10px",border:"1px solid #BBDEFB",
                  borderRadius:20,background:"var(--blue-light)",color:"var(--blue)",
                  cursor:"pointer",opacity:thinking?0.5:1 }}>{s}</button>
            ))}
          </div>

          <div style={{ display:"flex",gap:8,padding:"10px 12px",borderTop:"1px solid var(--gray-100)" }}>
            <input value={input} onChange={e=>setInput(e.target.value)}
              onKeyDown={e=>e.key==="Enter"&&send()}
              placeholder="Ask anything..."
              style={{ flex:1,padding:"9px 14px",border:"1.5px solid var(--gray-200)",
                borderRadius:20,fontSize:13,fontFamily:"inherit",outline:"none" }} />
            <button onClick={() => send()} disabled={!input.trim()||thinking}
              style={{ width:38,height:38,background:"var(--blue)",color:"white",
                border:"none",borderRadius:"50%",fontSize:16,cursor:"pointer",flexShrink:0,
                opacity:!input.trim()||thinking?0.5:1 }}>↑</button>
          </div>
        </div>
      )}

      <style>{`
        @media (max-width: 480px) {
          .chatbot-window { width: calc(100vw - 32px) !important; right: 16px !important; }
        }
      `}</style>
    </>
  )
}
