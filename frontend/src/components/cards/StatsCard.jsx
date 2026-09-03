import { useState } from "react"

export default function StatsCard({ icon, title, value, trend, color="#0A66C2", bg="#E8F0FE", delay=0 }) {
  const [hovered, setHovered] = useState(false)
  return (
    <div className="fade-up"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        background:"white",borderRadius:"var(--radius-lg)",
        padding:"18px 20px",border:"1px solid var(--gray-200)",
        transition:"var(--transition)",cursor:"default",
        transform: hovered ? "translateY(-3px)" : "none",
        boxShadow: hovered ? "var(--shadow-lg)" : "var(--shadow-sm)",
        animationDelay:`${delay}ms`
      }}>
      <div style={{ display:"flex",justifyContent:"space-between",alignItems:"flex-start",marginBottom:12 }}>
        <span style={{ fontSize:12,fontWeight:500,color:"var(--gray-500)",textTransform:"uppercase",letterSpacing:"0.04em" }}>
          {title}
        </span>
        <div style={{
          width:36,height:36,borderRadius:10,background:bg,
          display:"flex",alignItems:"center",justifyContent:"center",fontSize:18
        }}>{icon}</div>
      </div>
      <div style={{ fontSize:30,fontWeight:700,color,marginBottom:6 }}>{value}</div>
      {trend && (
        <div style={{ fontSize:12,color:"var(--gray-500)",display:"flex",alignItems:"center",gap:4 }}>
          <span style={{ color:trend.up ? "#057642" : "#B91C1C" }}>{trend.up ? "↑" : "↓"} {trend.value}</span>
          <span>{trend.label}</span>
        </div>
      )}
    </div>
  )
}
