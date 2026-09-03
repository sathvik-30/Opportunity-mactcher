import { getDeadlineStatus, getMatchColor } from "../../utils/helpers"
import EmptyState from "../common/EmptyState"

export default function SavedView({ saved, onRemove }) {
  if (!saved.length) return (
    <EmptyState icon="♡" title="No saved opportunities yet"
      subtitle="Click the heart icon on any opportunity to save it here" />
  )
  return (
    <div>
      <h2 style={{ fontSize:18,fontWeight:700,marginBottom:16,color:"var(--gray-900)" }}>
        Saved Opportunities <span style={{ fontSize:14,color:"var(--gray-400)",fontWeight:400 }}>({saved.length})</span>
      </h2>
      <div style={{ display:"flex",flexDirection:"column",gap:12 }}>
        {saved.map((opp,i) => {
          const deadline = getDeadlineStatus(opp.deadline)
          const matchColor = getMatchColor(opp.match_score || 0)
          return (
            <div key={i} className="fade-up" style={{
              background:"white",borderRadius:"var(--radius-lg)",
              border:"1px solid var(--gray-200)",padding:"16px 18px",
              display:"flex",alignItems:"center",gap:14,
              transition:"var(--transition)"
            }}>
              <div style={{
                width:40,height:40,borderRadius:10,
                background:"var(--blue)",color:"white",flexShrink:0,
                display:"flex",alignItems:"center",justifyContent:"center",
                fontSize:16,fontWeight:700
              }}>{opp.organization?.charAt(0)}</div>
              <div style={{ flex:1,minWidth:0 }}>
                <div style={{ fontSize:14,fontWeight:600,color:"var(--gray-900)",marginBottom:2 }}>{opp.title}</div>
                <div style={{ fontSize:12,color:"var(--gray-500)",marginBottom:4 }}>{opp.organization}</div>
                <div style={{ display:"flex",gap:8,flexWrap:"wrap" }}>
                  {deadline && (
                    <span style={{ fontSize:11,padding:"2px 8px",borderRadius:20,
                      background:deadline.bg,color:deadline.color,fontWeight:500 }}>
                      ⏰ {deadline.label}
                    </span>
                  )}
                  <span style={{ fontSize:11,color:matchColor.color,fontWeight:600 }}>
                    {opp.match_score || 0}% match
                  </span>
                  <span style={{ fontSize:11,color:"var(--gray-400)" }}>
                    Saved {new Date(opp.savedAt).toLocaleDateString()}
                  </span>
                </div>
              </div>
              <div style={{ display:"flex",gap:8,flexShrink:0 }}>
                <a href={opp.link} target="_blank" rel="noreferrer" style={{
                  padding:"7px 14px",background:"var(--blue)",color:"white",
                  borderRadius:20,fontSize:12,fontWeight:600,textDecoration:"none"
                }}>Apply</a>
                <button onClick={() => onRemove(opp)}
                  style={{ width:32,height:32,borderRadius:"50%",border:"1px solid var(--gray-200)",
                    background:"white",fontSize:14,cursor:"pointer",color:"#EF4444" }}>♥</button>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
