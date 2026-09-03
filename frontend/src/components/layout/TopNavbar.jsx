import { useState, useRef, useEffect } from "react"

function timeAgo(isoString) {
  if (!isoString) return ""
  const diffMs = Date.now() - new Date(isoString).getTime()
  const mins = Math.floor(diffMs / 60000)
  if (mins < 1) return "just now"
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

const TYPE_ICON = {
  internship: "💼", job: "💼", hackathon: "🏆",
  scholarship: "🎓", research: "🔬", new_match: "🔔",
}

function NotificationMenu({ open, onClose, notifications, onMarkAllRead, onNotifClick }) {
  if (!open) return null
  return (
    <div className="scale-in" style={{
      position:"absolute",top:"calc(100% + 8px)",right:0,width:320,
      background:"white",borderRadius:"var(--radius-lg)",border:"1px solid var(--gray-200)",
      boxShadow:"var(--shadow-xl)",zIndex:500,overflow:"hidden",maxHeight:420,overflowY:"auto"
    }}>
      <div style={{ padding:"14px 16px",borderBottom:"1px solid var(--gray-100)",
        display:"flex",justifyContent:"space-between",alignItems:"center" }}>
        <span style={{ fontSize:14,fontWeight:600 }}>Notifications</span>
        <button onClick={onMarkAllRead} style={{ background:"none",border:"none",fontSize:14,
          color:"var(--blue)",cursor:"pointer",fontWeight:500 }}>Mark all read</button>
      </div>
      {notifications.length === 0 && (
        <div style={{ padding:"24px 16px",textAlign:"center",fontSize:13,color:"var(--gray-400)" }}>
          No notifications yet.
        </div>
      )}
      {notifications.map((n) => (
        <div key={n.id} onClick={() => onNotifClick(n)} style={{
          padding:"12px 16px",display:"flex",gap:12,alignItems:"flex-start",
          borderBottom:"1px solid var(--gray-50)",
          background: !n.is_read ? "var(--blue-light)" : "white",
          cursor:"pointer",transition:"var(--transition)"
        }}>
          <span style={{ fontSize:20 }}>{TYPE_ICON[n.type] || "🔔"}</span>
          <div style={{ flex:1,minWidth:0 }}>
            <p style={{ fontSize:13,color:"var(--gray-800)",lineHeight:1.4,marginBottom:3,
              fontWeight: !n.is_read ? 600 : 400 }}>{n.title}</p>
            <p style={{ fontSize:12,color:"var(--gray-600)",lineHeight:1.4,marginBottom:3,
              whiteSpace:"pre-line" }}>{n.message}</p>
            <p style={{ fontSize:11,color:"var(--gray-400)" }}>{timeAgo(n.created_at)}</p>
          </div>
          {!n.is_read && <div style={{ width:8,height:8,borderRadius:"50%",background:"var(--blue)",flexShrink:0,marginTop:4 }} />}
        </div>
      ))}
    </div>
  )
}

function ProfileMenu({ open, onClose, student, onLogout, onEditProfile }) {
  if (!open) return null
  return (
    <div className="scale-in" style={{
      position:"absolute",top:"calc(100% + 8px)",right:0,width:220,
      background:"white",borderRadius:"var(--radius-lg)",border:"1px solid var(--gray-200)",
      boxShadow:"var(--shadow-xl)",zIndex:500,overflow:"hidden"
    }}>
      <div style={{ padding:"14px 16px",borderBottom:"1px solid var(--gray-100)" }}>
        <div style={{ fontSize:14,fontWeight:600,color:"var(--gray-900)" }}>{student?.name}</div>
        <div style={{ fontSize:12,color:"var(--gray-400)",marginTop:2 }}>{student?.email}</div>
      </div>
      {[
        { label:"Edit Profile", icon:"◎", action: onEditProfile },
        { label:"Settings",     icon:"⚙", action: onClose },
        { label:"Sign out",     icon:"⎋", action: onLogout, red: true },
      ].map((item,i) => (
        <button key={i} onClick={() => { item.action?.(); onClose() }}
          style={{
            width:"100%",display:"flex",alignItems:"center",gap:10,
            padding:"11px 16px",border:"none",background:"white",
            fontSize:13,color: item.red ? "var(--red)" : "var(--gray-700)",
            cursor:"pointer",transition:"var(--transition)",textAlign:"left"
          }}>
          <span>{item.icon}</span>{item.label}
        </button>
      ))}
    </div>
  )
}

export default function TopNavbar({ student, onLogout, searchQuery, onSearch, onMenuToggle, onEditProfile, refreshing, onRefresh, lastUpdated, notifications = [], unreadCount = 0, onMarkAllRead, onNotifClick }) {
  const [notifOpen, setNotifOpen] = useState(false)
  const [profileOpen, setProfileOpen] = useState(false)
  const notifRef = useRef(null)
  const profileRef = useRef(null)

  useEffect(() => {
    const handler = (e) => {
      if (notifRef.current && !notifRef.current.contains(e.target)) setNotifOpen(false)
      if (profileRef.current && !profileRef.current.contains(e.target)) setProfileOpen(false)
    }
    document.addEventListener("mousedown", handler)
    return () => document.removeEventListener("mousedown", handler)
  }, [])

  return (
    <header style={{
      position:"fixed",top:0,right:0,
      left:"var(--sidebar-width)",
      height:"var(--navbar-height)",
      background:"white",borderBottom:"1px solid var(--gray-200)",
      display:"flex",alignItems:"center",gap:12,
      padding:"0 20px",zIndex:100,
    }} className="top-navbar">

      {/* Mobile menu button */}
      <button onClick={onMenuToggle} className="mobile-menu-btn" style={{
        display:"none",background:"none",border:"none",fontSize:20,
        color:"var(--gray-600)",cursor:"pointer",padding:4,flexShrink:0
      }}>☰</button>

      {/* Search */}
      <div style={{ flex:1,maxWidth:480,position:"relative" }}>
        <span style={{
          position:"absolute",left:12,top:"50%",transform:"translateY(-50%)",
          fontSize:16,color:"var(--gray-400)",pointerEvents:"none"
        }}>🔍</span>
        <input
          value={searchQuery} onChange={e => onSearch(e.target.value)}
          placeholder="Search internships, hackathons, scholarships..."
          style={{
            width:"100%",padding:"9px 14px 9px 38px",
            border:"1.5px solid var(--gray-200)",borderRadius:"var(--radius-xl)",
            fontSize:14,background:"var(--gray-50)",outline:"none",
            transition:"var(--transition)"
          }}
          onFocus={e => e.target.style.borderColor = "var(--blue)"}
          onBlur={e => e.target.style.borderColor = "var(--gray-200)"}
        />
      </div>

      {/* Right actions */}
      <div style={{ display:"flex",alignItems:"center",gap:6,marginLeft:"auto" }}>

        {/* Live indicator */}
        <div style={{ display:"flex",alignItems:"center",gap:6,
          padding:"5px 10px",borderRadius:20,border:"1px solid var(--gray-200)",
          background:"var(--gray-50)" }} className="live-indicator">
          <span style={{ width:7,height:7,borderRadius:"50%",background:"#22C55E",
            display:"inline-block",animation: refreshing ? "pulse 1s infinite" : "none" }} />
          <span style={{ fontSize:11,color:"var(--gray-500)",fontWeight:500,whiteSpace:"nowrap" }}>
            {refreshing ? "Updating..." : lastUpdated
              ? `${lastUpdated.toLocaleTimeString([],{hour:"2-digit",minute:"2-digit"})}`
              : "Live"}
          </span>
        </div>

        {/* Refresh */}
        <button onClick={onRefresh} disabled={refreshing} style={{
          width:36,height:36,borderRadius:"50%",border:"1px solid var(--gray-200)",
          background:"white",fontSize:16,display:"flex",alignItems:"center",
          justifyContent:"center",cursor:"pointer",transition:"var(--transition)",
          color:"var(--gray-600)",
          transform: refreshing ? "rotate(360deg)" : "none"
        }} title="Refresh">↻</button>

        {/* Notifications */}
        <div ref={notifRef} style={{ position:"relative" }}>
          <button onClick={() => { setNotifOpen(o=>!o); setProfileOpen(false) }}
            style={{
              width:36,height:36,borderRadius:"50%",border:"1px solid var(--gray-200)",
              background:"white",fontSize:18,display:"flex",alignItems:"center",
              justifyContent:"center",cursor:"pointer",position:"relative",color:"var(--gray-600)"
            }}>
            🔔
            {unreadCount > 0 && (
              <span style={{
                position:"absolute",top:2,right:2,minWidth:16,height:16,padding:"0 3px",
                borderRadius:8,background:"#EF4444",border:"2px solid white",
                fontSize:9,fontWeight:700,color:"white",
                display:"flex",alignItems:"center",justifyContent:"center"
              }}>{unreadCount > 9 ? "9+" : unreadCount}</span>
            )}
          </button>
          <NotificationMenu open={notifOpen} onClose={() => setNotifOpen(false)}
            notifications={notifications} onMarkAllRead={onMarkAllRead}
            onNotifClick={(n) => { onNotifClick?.(n); }} />
        </div>

        {/* Profile */}
        <div ref={profileRef} style={{ position:"relative" }}>
          <button onClick={() => { setProfileOpen(o=>!o); setNotifOpen(false) }}
            style={{
              width:36,height:36,borderRadius:"50%",
              background:"linear-gradient(135deg,#0A66C2,#6D28D9)",
              border:"2px solid var(--gray-200)",
              fontSize:14,fontWeight:600,color:"white",cursor:"pointer",
              display:"flex",alignItems:"center",justifyContent:"center"
            }}>
            {student?.name?.charAt(0).toUpperCase()}
          </button>
          <ProfileMenu open={profileOpen} onClose={() => setProfileOpen(false)}
            student={student} onLogout={onLogout} onEditProfile={onEditProfile} />
        </div>
      </div>

      <style>{`
        @media (max-width: 1023px) {
          .top-navbar { left: 0 !important; }
          .mobile-menu-btn { display: flex !important; }
          .live-indicator { display: none !important; }
        }
        @media (max-width: 480px) {
          .top-navbar { padding: 0 12px; gap: 8px; }
        }
      `}</style>
    </header>
  )
}
