export default function EmptyState({ title="No opportunities found", subtitle="Try changing your filters or search terms", onReset, icon="🔍" }) {
  return (
    <div className="fade-up" style={{ textAlign:"center",padding:"60px 24px",display:"flex",flexDirection:"column",alignItems:"center",gap:16 }}>
      <div style={{ fontSize:56,lineHeight:1 }}>{icon}</div>
      <div>
        <p style={{ fontSize:18,fontWeight:600,color:"var(--gray-800)",marginBottom:6 }}>{title}</p>
        <p style={{ fontSize:14,color:"var(--gray-500)",maxWidth:300,margin:"0 auto" }}>{subtitle}</p>
      </div>
      {onReset && (
        <button onClick={onReset} style={{
          marginTop:8,padding:"10px 24px",background:"var(--blue)",color:"white",
          border:"none",borderRadius:"var(--radius-xl)",fontSize:14,fontWeight:500,cursor:"pointer"
        }}>
          Reset Filters
        </button>
      )}
    </div>
  )
}
