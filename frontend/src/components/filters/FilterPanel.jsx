import { useState } from "react"

const TYPES = ["All","internship","hackathon","scholarship","research"]
const BRANCHES = ["CS","IT","ECE","ME","Civil","Chemical"]
const SORT_OPTIONS = ["Highest Match","Deadline Soon","Newest"]

export default function FilterPanel({ filters, onChange, onReset, mobileOpen, onMobileClose }) {
  const [localFilters, setLocalFilters] = useState(filters)

  const update = (key, val) => {
    const next = { ...localFilters, [key]: val }
    setLocalFilters(next)
    onChange(next)
  }

  const activeCount = [
    localFilters.type !== "All",
    localFilters.location,
    localFilters.branch,
    localFilters.minScore > 0,
    localFilters.remote,
  ].filter(Boolean).length

  const content = (
    <div style={{ display:"flex",flexDirection:"column",gap:20 }}>

      {/* Sort */}
      <div>
        <label style={labelStyle}>Sort By</label>
        <select value={localFilters.sortBy || "Highest Match"}
          onChange={e => update("sortBy", e.target.value)}
          style={selectStyle}>
          {SORT_OPTIONS.map(o => <option key={o}>{o}</option>)}
        </select>
      </div>

      {/* Type */}
      <div>
        <label style={labelStyle}>Opportunity Type</label>
        <div style={{ display:"flex",flexWrap:"wrap",gap:6 }}>
          {TYPES.map(t => (
            <button key={t} onClick={() => update("type", t)}
              style={{
                padding:"5px 12px",borderRadius:20,border:"1.5px solid",fontSize:12,fontWeight:500,
                cursor:"pointer",transition:"var(--transition)",
                borderColor: localFilters.type===t ? "var(--blue)" : "var(--gray-200)",
                background: localFilters.type===t ? "var(--blue)" : "white",
                color: localFilters.type===t ? "white" : "var(--gray-600)"
              }}>{t==="All"?"All":t.charAt(0).toUpperCase()+t.slice(1)}</button>
          ))}
        </div>
      </div>

      {/* Match score */}
      <div>
        <label style={labelStyle}>
          Min Match Score
          <span style={{ float:"right",color:"var(--blue)",fontWeight:600 }}>{localFilters.minScore || 0}%</span>
        </label>
        <input type="range" min={0} max={90} step={10}
          value={localFilters.minScore || 0}
          onChange={e => update("minScore", parseInt(e.target.value))}
          style={{ width:"100%",accentColor:"var(--blue)" }} />
        <div style={{ display:"flex",justifyContent:"space-between",fontSize:11,color:"var(--gray-400)",marginTop:4 }}>
          <span>Any</span><span>90%+</span>
        </div>
      </div>

      {/* Location */}
      <div>
        <label style={labelStyle}>Location</label>
        <input value={localFilters.location || ""}
          onChange={e => update("location", e.target.value)}
          placeholder="e.g. Bangalore, Remote"
          style={inputStyle} />
      </div>

      {/* Branch */}
      <div>
        <label style={labelStyle}>Branch</label>
        <div style={{ display:"flex",flexWrap:"wrap",gap:5 }}>
          {BRANCHES.map(b => (
            <button key={b} onClick={() => update("branch", localFilters.branch===b ? "" : b)}
              style={{
                padding:"4px 10px",borderRadius:20,border:"1.5px solid",fontSize:11,fontWeight:500,
                cursor:"pointer",transition:"var(--transition)",
                borderColor: localFilters.branch===b ? "var(--blue)" : "var(--gray-200)",
                background: localFilters.branch===b ? "var(--blue-light)" : "white",
                color: localFilters.branch===b ? "var(--blue)" : "var(--gray-600)"
              }}>{b}</button>
          ))}
        </div>
      </div>

      {/* Remote */}
      <div style={{ display:"flex",alignItems:"center",justifyContent:"space-between" }}>
        <label style={{ ...labelStyle,marginBottom:0 }}>Remote only</label>
        <button onClick={() => update("remote", !localFilters.remote)}
          style={{
            width:44,height:24,borderRadius:12,border:"none",cursor:"pointer",
            background: localFilters.remote ? "var(--blue)" : "var(--gray-300)",
            position:"relative",transition:"var(--transition)"
          }}>
          <div style={{
            width:18,height:18,borderRadius:"50%",background:"white",
            position:"absolute",top:3,
            left: localFilters.remote ? "calc(100% - 21px)" : 3,
            transition:"left 0.2s ease",boxShadow:"var(--shadow-sm)"
          }} />
        </button>
      </div>

      {/* Reset */}
      {activeCount > 0 && (
        <button onClick={() => {
          const reset = { type:"All",minScore:0,location:"",branch:"",remote:false,sortBy:"Highest Match" }
          setLocalFilters(reset)
          onReset()
        }} style={{
          padding:"10px",borderRadius:"var(--radius)",border:"1.5px solid var(--red-light)",
          background:"var(--red-light)",color:"var(--red)",fontSize:13,fontWeight:500,cursor:"pointer"
        }}>
          ✕ Clear all filters ({activeCount})
        </button>
      )}
    </div>
  )

  return (
    <>
      {/* Desktop panel */}
      <aside className="filter-sidebar" style={{
        width:220,flexShrink:0,position:"sticky",top:"calc(var(--navbar-height) + 16px)",
        height:"fit-content",maxHeight:"calc(100vh - 80px)",overflowY:"auto"
      }}>
        <div style={{ background:"white",borderRadius:"var(--radius-lg)",
          border:"1px solid var(--gray-200)",padding:16 }}>
          <div style={{ display:"flex",justifyContent:"space-between",
            alignItems:"center",marginBottom:16 }}>
            <span style={{ fontSize:14,fontWeight:600,color:"var(--gray-800)" }}>Filters</span>
            {activeCount > 0 && (
              <span style={{ fontSize:11,background:"var(--blue)",color:"white",
                borderRadius:10,padding:"2px 7px",fontWeight:600 }}>{activeCount}</span>
            )}
          </div>
          {content}
        </div>
      </aside>

      {/* Mobile drawer */}
      {mobileOpen && (
        <>
          <div onClick={onMobileClose} style={{
            position:"fixed",inset:0,background:"rgba(0,0,0,0.4)",zIndex:299,
            animation:"fadeIn 0.2s ease"
          }} />
          <div className="slide-up" style={{
            position:"fixed",bottom:0,left:0,right:0,
            background:"white",borderRadius:"20px 20px 0 0",
            padding:"20px 20px 32px",zIndex:300,
            maxHeight:"85vh",overflowY:"auto"
          }}>
            <div style={{ display:"flex",justifyContent:"space-between",
              alignItems:"center",marginBottom:20 }}>
              <span style={{ fontSize:16,fontWeight:700 }}>Filters</span>
              <button onClick={onMobileClose} style={{
                background:"var(--gray-100)",border:"none",borderRadius:"50%",
                width:32,height:32,fontSize:16,cursor:"pointer"
              }}>✕</button>
            </div>
            {content}
            <button onClick={onMobileClose} style={{
              marginTop:16,width:"100%",padding:"12px",
              background:"var(--blue)",color:"white",border:"none",
              borderRadius:"var(--radius-xl)",fontSize:14,fontWeight:600,cursor:"pointer"
            }}>Apply Filters</button>
          </div>
        </>
      )}

      <style>{`
        @media (max-width: 1023px) { .filter-sidebar { display: none !important; } }
      `}</style>
    </>
  )
}

const labelStyle = { display:"block",fontSize:12,fontWeight:600,color:"var(--gray-600)",
  textTransform:"uppercase",letterSpacing:"0.04em",marginBottom:8 }
const inputStyle = { width:"100%",padding:"8px 12px",border:"1.5px solid var(--gray-200)",
  borderRadius:"var(--radius-sm)",fontSize:13,outline:"none",transition:"var(--transition)" }
const selectStyle = { ...inputStyle,background:"white",cursor:"pointer" }
