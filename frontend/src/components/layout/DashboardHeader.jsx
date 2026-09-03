import { getTimeOfDay, getQuote } from "../../utils/helpers"

export default function DashboardHeader({ student }) {
  const today = new Date().toLocaleDateString("en-US",{ weekday:"long",month:"long",day:"numeric" })
  return (
    <div className="fade-up" style={{ marginBottom:24 }}>
      <div style={{ display:"flex",justifyContent:"space-between",alignItems:"flex-start",flexWrap:"wrap",gap:12 }}>
        <div>
          <h1 style={{ fontSize:22,fontWeight:700,color:"var(--gray-900)",marginBottom:4 }}>
            {getTimeOfDay()}, {student?.name?.split(" ")[0]} 👋
          </h1>
          <p style={{ fontSize:13,color:"var(--gray-500)" }}>{today}</p>
        </div>
        <div style={{
          background:"linear-gradient(135deg,#E8F0FE,#EDE9FE)",
          padding:"10px 16px",borderRadius:"var(--radius-lg)",
          border:"1px solid #C7D7F5",maxWidth:360
        }}>
          <p style={{ fontSize:12,color:"var(--blue)",fontStyle:"italic",lineHeight:1.5 }}>
            💡 {getQuote()}
          </p>
        </div>
      </div>
    </div>
  )
}
