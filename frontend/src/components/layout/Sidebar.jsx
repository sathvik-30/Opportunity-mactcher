const NAV = [
  { id:"dashboard", label:"Dashboard",  icon:"⊞" },
  { id:"saved",     label:"Saved",      icon:"♡" },
  { id:"profile",   label:"Profile",    icon:"◎" },
  { id:"settings",  label:"Settings",   icon:"⚙" },
]

export default function Sidebar({ activeTab, onTabChange, student, onLogout, mobileOpen, onMobileClose }) {
  // Phase 8: Admin nav item only rendered client-side for admin users —
  // this is a UI convenience, NOT the security boundary. Every /admin/*
  // backend route independently re-checks is_admin via require_admin,
  // so hiding this button is not what protects the data.
  const nav = student?.is_admin ? [...NAV, { id:"admin", label:"Admin", icon:"🛡" }] : NAV
  return (
    <>
      {/* Mobile overlay */}
      {mobileOpen && (
        <div onClick={onMobileClose} style={{
          position:"fixed",inset:0,background:"rgba(0,0,0,0.4)",zIndex:199,
          animation:"fadeIn 0.2s ease"
        }} />
      )}

      <aside style={{
        position:"fixed",top:0,left:0,height:"100vh",
        width:"var(--sidebar-width)",background:"white",
        borderRight:"1px solid var(--gray-200)",
        display:"flex",flexDirection:"column",zIndex:200,
        transform: mobileOpen ? "translateX(0)" : undefined,
        transition:"transform 0.25s ease",
        boxShadow: mobileOpen ? "var(--shadow-xl)" : "none",
      }} className={!mobileOpen ? "sidebar-hidden" : ""}>

        {/* Brand */}
        <div style={{ padding:"20px 16px",borderBottom:"1px solid var(--gray-100)" }}>
          <div style={{ display:"flex",alignItems:"center",gap:10 }}>
            <div style={{
              width:36,height:36,background:"linear-gradient(135deg,#0A66C2,#004182)",
              borderRadius:10,display:"flex",alignItems:"center",justifyContent:"center",
              fontSize:13,fontWeight:700,color:"white",flexShrink:0
            }}>OM</div>
            <div>
              <div style={{ fontSize:14,fontWeight:700,color:"var(--gray-900)" }}>OpportunityMatch</div>
              <div style={{ fontSize:11,color:"var(--gray-400)" }}>Student Portal</div>
            </div>
          </div>
        </div>

        {/* Student info */}
        <div style={{ padding:"16px",borderBottom:"1px solid var(--gray-100)" }}>
          <div style={{ display:"flex",alignItems:"center",gap:10 }}>
            <div style={{
              width:38,height:38,borderRadius:"50%",
              background:"linear-gradient(135deg,#0A66C2,#6D28D9)",
              display:"flex",alignItems:"center",justifyContent:"center",
              fontSize:15,fontWeight:600,color:"white",flexShrink:0
            }}>{student?.name?.charAt(0).toUpperCase()}</div>
            <div style={{ minWidth:0 }}>
              <div style={{ fontSize:13,fontWeight:600,color:"var(--gray-800)",
                overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap" }}>
                {student?.name}
              </div>
              <div style={{ fontSize:11,color:"var(--gray-400)" }}>
                {student?.branch} · Year {student?.year}
              </div>
            </div>
          </div>
        </div>

        {/* Nav */}
        <nav style={{ flex:1,padding:"12px 8px",overflowY:"auto" }}>
          {nav.map(item => (
            <button key={item.id} onClick={() => { onTabChange(item.id); onMobileClose?.() }}
              style={{
                width:"100%",display:"flex",alignItems:"center",gap:10,
                padding:"10px 12px",borderRadius:"var(--radius)",border:"none",
                background: activeTab===item.id ? "var(--blue-light)" : "transparent",
                color: activeTab===item.id ? "var(--blue)" : "var(--gray-600)",
                fontSize:14,fontWeight: activeTab===item.id ? 600 : 400,
                cursor:"pointer",marginBottom:2,transition:"var(--transition)",textAlign:"left"
              }}>
              <span style={{ fontSize:16 }}>{item.icon}</span>
              {item.label}
              {item.id==="saved" && (
                <span style={{
                  marginLeft:"auto",fontSize:11,background:"var(--blue)",
                  color:"white",borderRadius:10,padding:"1px 6px",fontWeight:600
                }}>New</span>
              )}
            </button>
          ))}
        </nav>

        {/* Logout */}
        <div style={{ padding:"12px 8px",borderTop:"1px solid var(--gray-100)" }}>
          <button onClick={onLogout} style={{
            width:"100%",display:"flex",alignItems:"center",gap:10,
            padding:"10px 12px",borderRadius:"var(--radius)",border:"none",
            background:"transparent",color:"var(--gray-500)",fontSize:14,cursor:"pointer",
            transition:"var(--transition)",textAlign:"left"
          }}>
            <span style={{ fontSize:16 }}>⎋</span>
            Sign out
          </button>
        </div>
      </aside>

      <style>{`
        @media (max-width: 1023px) {
          .sidebar-hidden { transform: translateX(-100%) !important; }
        }
      `}</style>
    </>
  )
}
