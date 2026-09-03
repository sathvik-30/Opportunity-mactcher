export function CardSkeleton() {
  return (
    <div style={{ background:"white",borderRadius:"var(--radius-lg)",padding:"20px",border:"1px solid var(--gray-200)" }}>
      <div style={{ display:"flex",gap:"12px",marginBottom:"16px" }}>
        <div className="skeleton" style={{ width:44,height:44,borderRadius:"10px",flexShrink:0 }} />
        <div style={{ flex:1 }}>
          <div className="skeleton" style={{ height:14,width:"60%",marginBottom:8 }} />
          <div className="skeleton" style={{ height:12,width:"40%" }} />
        </div>
        <div className="skeleton" style={{ width:50,height:24,borderRadius:12 }} />
      </div>
      <div className="skeleton" style={{ height:18,width:"80%",marginBottom:10 }} />
      <div className="skeleton" style={{ height:13,width:"100%",marginBottom:6 }} />
      <div className="skeleton" style={{ height:13,width:"75%",marginBottom:16 }} />
      <div style={{ display:"flex",gap:6,marginBottom:16 }}>
        {[60,70,50].map((w,i)=><div key={i} className="skeleton" style={{ height:24,width:w,borderRadius:20 }} />)}
      </div>
      <div className="skeleton" style={{ height:5,width:"100%",borderRadius:3,marginBottom:16 }} />
      <div style={{ display:"flex",gap:8 }}>
        <div className="skeleton" style={{ height:36,flex:1,borderRadius:20 }} />
        <div className="skeleton" style={{ height:36,width:36,borderRadius:"50%" }} />
        <div className="skeleton" style={{ height:36,width:36,borderRadius:"50%" }} />
      </div>
    </div>
  )
}
export function StatSkeleton() {
  return (
    <div style={{ background:"white",borderRadius:"var(--radius-lg)",padding:"20px",border:"1px solid var(--gray-200)" }}>
      <div style={{ display:"flex",justifyContent:"space-between",marginBottom:12 }}>
        <div className="skeleton" style={{ height:13,width:80 }} />
        <div className="skeleton" style={{ width:36,height:36,borderRadius:10 }} />
      </div>
      <div className="skeleton" style={{ height:32,width:60,marginBottom:8 }} />
      <div className="skeleton" style={{ height:12,width:100 }} />
    </div>
  )
}
export function SkeletonGrid({ count=6 }) {
  return (
    <div style={{ display:"grid",gridTemplateColumns:"repeat(auto-fill,minmax(300px,1fr))",gap:16 }}>
      {Array(count).fill(0).map((_,i)=><CardSkeleton key={i} />)}
    </div>
  )
}
