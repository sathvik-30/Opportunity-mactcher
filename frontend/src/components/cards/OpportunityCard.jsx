import { useState } from "react"
import { getDeadlineStatus, getMatchColor } from "../../utils/helpers"

const TYPE_CFG = {
  hackathon:   { bg:"#EDE9FE", color:"#6D28D9", label:"Hackathon",   icon:"🏆" },
  internship:  { bg:"#E8F0FE", color:"#0A66C2", label:"Internship",  icon:"💼" },
  scholarship: { bg:"#F3E5F5", color:"#9333EA", label:"Scholarship", icon:"🎓" },
  research:    { bg:"#FFF3E0", color:"#E65100", label:"Research",     icon:"🔬" }
}

function MatchRing({ score }) {
  const { color, bg } = getMatchColor(score)
  const r = 18, circ = 2 * Math.PI * r
  const offset = circ - (score / 100) * circ
  return (
    <div style={{ position:"relative",width:48,height:48,flexShrink:0 }}>
      <svg width="48" height="48" style={{ transform:"rotate(-90deg)" }}>
        <circle cx="24" cy="24" r={r} fill="none" stroke={bg} strokeWidth="4" />
        <circle cx="24" cy="24" r={r} fill="none" stroke={color} strokeWidth="4"
          strokeDasharray={circ} strokeDashoffset={offset}
          strokeLinecap="round" style={{ transition:"stroke-dashoffset 0.8s ease" }} />
      </svg>
      <div style={{
        position:"absolute",inset:0,display:"flex",alignItems:"center",
        justifyContent:"center",fontSize:11,fontWeight:700,color
      }}>{score}%</div>
    </div>
  )
}

export default function OpportunityCard({ result, student, isSaved, onSave, onViewDetail }) {
  const [hovered, setHovered] = useState(false)
  const { opportunity: opp, match_score, eligibility, recommended } = result
  const cfg = TYPE_CFG[opp.type] || TYPE_CFG.internship
  const deadline = getDeadlineStatus(opp.deadline)
  const matchClr = getMatchColor(match_score)
  const studentSkills = Array.isArray(student?.skills) ? student.skills.map(s => s.toLowerCase()) : []

  const logoLetter = opp.organization?.charAt(0).toUpperCase()
  const logoColors = ["#0A66C2","#6D28D9","#E65100","#057642","#B45309","#9333EA"]
  const logoColor = logoColors[opp.organization?.charCodeAt(0) % logoColors.length]

  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      className="fade-up"
      style={{
        background:"white",borderRadius:"var(--radius-lg)",
        border: recommended ? "2px solid var(--blue)" : "1px solid var(--gray-200)",
        padding:"18px",display:"flex",flexDirection:"column",gap:12,
        transition:"var(--transition)",cursor:"pointer",
        transform: hovered ? "translateY(-4px)" : "none",
        boxShadow: hovered ? "var(--shadow-xl)" : recommended ? "0 4px 20px rgba(10,102,194,0.1)" : "var(--shadow-sm)",
      }}
      onClick={() => onViewDetail?.(opp)}
    >
      {/* Recommended badge */}
      {recommended && (
        <div style={{
          background:"linear-gradient(90deg,#E8F0FE,#EDE9FE)",
          color:"var(--blue)",fontSize:11,fontWeight:600,
          padding:"3px 10px",borderRadius:20,alignSelf:"flex-start",
          border:"1px solid #C7D7F5"
        }}>⭐ Recommended</div>
      )}

      {/* Header: logo + info + match ring */}
      <div style={{ display:"flex",gap:12,alignItems:"flex-start" }}>
        <div style={{
          width:44,height:44,borderRadius:10,background:logoColor,
          display:"flex",alignItems:"center",justifyContent:"center",
          fontSize:16,fontWeight:700,color:"white",flexShrink:0
        }}>{logoLetter}</div>
        <div style={{ flex:1,minWidth:0 }}>
          <div style={{ display:"flex",alignItems:"center",gap:6,marginBottom:2 }}>
            <span style={{ fontSize:13,fontWeight:600,color:"var(--gray-800)",
              overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap" }}>
              {opp.organization}
            </span>
            <span style={{ fontSize:11,color:"var(--blue)" }} title="Verified">✓</span>
          </div>
          <h3 style={{ fontSize:15,fontWeight:700,color:"var(--gray-900)",lineHeight:1.3,
            overflow:"hidden",textOverflow:"ellipsis",
            display:"-webkit-box",WebkitLineClamp:2,WebkitBoxOrient:"vertical" }}>
            {opp.title}
          </h3>
        </div>
        <MatchRing score={match_score} />
      </div>

      {/* Badges row */}
      <div style={{ display:"flex",flexWrap:"wrap",gap:6 }}>
        <span style={{ fontSize:11,fontWeight:500,padding:"3px 10px",borderRadius:20,
          background:cfg.bg,color:cfg.color }}>
          {cfg.icon} {cfg.label}
        </span>
        {opp.location && (
          <span style={{ fontSize:11,padding:"3px 10px",borderRadius:20,
            background:"var(--gray-100)",color:"var(--gray-600)" }}>
            📍 {opp.location}
          </span>
        )}
        {opp.location?.toLowerCase().includes("remote") && (
          <span style={{ fontSize:11,padding:"3px 10px",borderRadius:20,
            background:"#E8F0FE",color:"var(--blue)" }}>🌐 Remote</span>
        )}
      </div>

      {/* Description */}
      <p style={{ fontSize:13,color:"var(--gray-500)",lineHeight:1.5,
        display:"-webkit-box",WebkitLineClamp:2,WebkitBoxOrient:"vertical",overflow:"hidden" }}>
        {opp.description}
      </p>

      {/* Requirements */}
      <div style={{ background:"var(--gray-50)",borderRadius:"var(--radius)",padding:"10px 12px" }}>
        <div style={{ fontSize:11,fontWeight:600,color:"var(--gray-500)",
          textTransform:"uppercase",letterSpacing:"0.04em",marginBottom:8 }}>Requirements</div>
        <div style={{ display:"grid",gridTemplateColumns:"1fr 1fr",gap:6 }}>
          {opp.eligibility?.min_year && (
            <div>
              <div style={{ fontSize:10,color:"var(--gray-400)",marginBottom:1 }}>MIN YEAR</div>
              <div style={{ fontSize:12,fontWeight:600,color:"var(--gray-700)" }}>{opp.eligibility.min_year}+ year</div>
            </div>
          )}
          {opp.eligibility?.min_cgpa && (
            <div>
              <div style={{ fontSize:10,color:"var(--gray-400)",marginBottom:1 }}>MIN CGPA</div>
              <div style={{ fontSize:12,fontWeight:600,color:"var(--gray-700)" }}>{opp.eligibility.min_cgpa}</div>
            </div>
          )}
          {opp.eligibility?.branches && (
            <div style={{ gridColumn:"1/-1" }}>
              <div style={{ fontSize:10,color:"var(--gray-400)",marginBottom:1 }}>BRANCHES</div>
              <div style={{ fontSize:12,fontWeight:500,color:"var(--gray-700)" }}>{opp.eligibility.branches.join(", ")}</div>
            </div>
          )}
        </div>
      </div>

      {/* Skills */}
      {opp.required_skills?.length > 0 && (
        <div style={{ display:"flex",flexWrap:"wrap",gap:5 }}>
          {opp.required_skills.map((sk,i) => {
            const have = studentSkills.includes(sk.toLowerCase())
            return (
              <span key={i} style={{
                fontSize:11,padding:"3px 9px",borderRadius:20,fontWeight:500,
                background: have ? "#E6F4EA" : "var(--gray-100)",
                color: have ? "#057642" : "var(--gray-600)",
                border:`1px solid ${have ? "#A8D5B5" : "var(--gray-200)"}`
              }}>{have ? "✓" : "+"} {sk}</span>
            )
          })}
        </div>
      )}

      {/* Match bar */}
      <div>
        <div style={{ display:"flex",justifyContent:"space-between",marginBottom:5 }}>
          <span style={{ fontSize:11,color:"var(--gray-500)" }}>Match score</span>
          <span style={{ fontSize:11,fontWeight:600,color:matchClr.color }}>{match_score}%</span>
        </div>
        <div style={{ height:5,background:"var(--gray-200)",borderRadius:3,overflow:"hidden" }}>
          <div style={{ height:"100%",width:`${match_score}%`,background:matchClr.color,
            borderRadius:3,transition:"width 0.8s ease" }} />
        </div>
      </div>

      {/* Meta row */}
      <div style={{ display:"flex",flexWrap:"wrap",gap:10 }}>
        {deadline && (
          <span style={{ fontSize:11,padding:"3px 9px",borderRadius:20,
            background:deadline.bg,color:deadline.color,fontWeight:500 }}>
            ⏰ {deadline.label}
          </span>
        )}
        {opp.stipend && (
          <span style={{ fontSize:11,color:"var(--blue)",fontWeight:600 }}>
            💰 {opp.stipend}
          </span>
        )}
      </div>

      {/* Eligibility issues */}
      {eligibility?.issues?.length > 0 && (
        <div style={{ background:"#FEF3C7",border:"1px solid #FDE68A",borderRadius:"var(--radius-sm)",
          padding:"7px 10px",fontSize:12,color:"#B45309" }}>
          ⚠️ {eligibility.issues[0]}
        </div>
      )}

      {/* Action buttons */}
      <div style={{ display:"flex",gap:8,marginTop:"auto",paddingTop:4 }}
        onClick={e => e.stopPropagation()}>
        <a href={opp.link} target="_blank" rel="noreferrer"
          style={{
            flex:1,padding:"9px",background:"var(--blue)",color:"white",
            borderRadius:"var(--radius-xl)",fontSize:13,fontWeight:600,
            textAlign:"center",textDecoration:"none",transition:"var(--transition)"
          }}>Apply →</a>
        <button onClick={() => onSave?.(opp)}
          title={isSaved ? "Remove from saved" : "Save"}
          style={{
            width:38,height:38,borderRadius:"50%",border:"1.5px solid var(--gray-200)",
            background: isSaved ? "#FEE2E2" : "white",fontSize:17,
            display:"flex",alignItems:"center",justifyContent:"center",
            cursor:"pointer",transition:"var(--transition)",flexShrink:0,
            color: isSaved ? "#EF4444" : "var(--gray-400)"
          }}>{isSaved ? "♥" : "♡"}</button>
        <button onClick={() => {
            const url = opp.link || window.location.href
            if (navigator.share) navigator.share({ title: opp.title, url })
            else { navigator.clipboard.writeText(url); alert("Link copied!") }
          }}
          title="Share"
          style={{
            width:38,height:38,borderRadius:"50%",border:"1.5px solid var(--gray-200)",
            background:"white",fontSize:15,display:"flex",alignItems:"center",
            justifyContent:"center",cursor:"pointer",transition:"var(--transition)",
            flexShrink:0,color:"var(--gray-400)"
          }}>↗</button>
      </div>
    </div>
  )
}
