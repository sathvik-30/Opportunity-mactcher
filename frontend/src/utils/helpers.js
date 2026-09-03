export const getDeadlineStatus = (deadline) => {
  if (!deadline) return null
  const days = Math.ceil((new Date(deadline) - new Date()) / (1000 * 60 * 60 * 24))
  if (days < 0)  return { label: "Closed",           color: "#B91C1C", bg: "#FEE2E2", urgent: true }
  if (days === 0) return { label: "Closes Today",     color: "#B91C1C", bg: "#FEE2E2", urgent: true }
  if (days === 1) return { label: "Closing Tomorrow", color: "#B45309", bg: "#FEF3C7", urgent: true }
  if (days <= 5)  return { label: `${days} days left`, color: "#B45309", bg: "#FEF3C7", urgent: true }
  if (days <= 14) return { label: `${days} days left`, color: "#057642", bg: "#E6F4EA", urgent: false }
  return { label: `${days} days left`, color: "#4B5563", bg: "#F3F4F6", urgent: false }
}

export const getMatchColor = (score) => {
  if (score >= 80) return { color: "#057642", bg: "#E6F4EA", ring: "#057642" }
  if (score >= 50) return { color: "#B45309", bg: "#FEF3C7", ring: "#F59E0B" }
  return { color: "#B91C1C", bg: "#FEE2E2", ring: "#EF4444" }
}

export const getTimeOfDay = () => {
  const h = new Date().getHours()
  if (h < 12) return "Good morning"
  if (h < 17) return "Good afternoon"
  return "Good evening"
}

export const QUOTES = [
  "Your next big opportunity is one application away.",
  "Every expert was once a beginner.",
  "Skills open doors. Passion keeps them open.",
  "Today's effort is tomorrow's success.",
]

export const getQuote = () => QUOTES[new Date().getDay() % QUOTES.length]
