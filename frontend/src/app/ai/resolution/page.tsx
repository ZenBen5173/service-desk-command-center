'use client'

// The decisions view lives in the Workbench, where every other ticket-level
// screen lives. This route stays so existing links keep working.
import { DecisionsPanel } from '@/components/ai/DecisionsPanel'

export default function ResolutionPage() {
  return <DecisionsPanel />
}
