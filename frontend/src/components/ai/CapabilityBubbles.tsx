'use client'

import { motion } from 'framer-motion'
import { cn } from '@/lib/utils'
import { Icons } from '@/components/ui/icons'

interface Capability {
  icon: React.ElementType
  label: string
  query: string
}

// Questions this surface can actually answer from mirrored agent data. Each
// maps to a real intent in the AI Manager service — nothing here is a prompt
// the operation cannot ground in an Operator's own output.
const CAPABILITIES: Capability[] = [
  { icon: Icons.activity, label: 'How are we doing?', query: 'How are we doing?' },
  { icon: Icons.target, label: 'Top problems', query: 'What are the top problems?' },
  { icon: Icons.trendingUp, label: 'What can we prevent?', query: 'How many tickets can we prevent?' },
  { icon: Icons.clock, label: 'SLA and breaches', query: 'How is our SLA compliance?' },
  { icon: Icons.workbench, label: 'Waiting on a human', query: 'What is waiting on a human?' },
  { icon: Icons.brain, label: 'Policies in force', query: 'What policies are in force?' },
  { icon: Icons.lightbulb, label: 'Insights', query: 'What insights do you have?' },
  { icon: Icons.users, label: 'The agents', query: 'What agents are running?' },
]

interface CapabilityBubblesProps {
  onSelect: (query: string) => void
}

export function CapabilityBubbles({ onSelect }: CapabilityBubblesProps) {
  return (
    <div className="flex flex-wrap justify-center gap-2 p-2">
      {CAPABILITIES.map((cap, i) => {
        const Icon = cap.icon
        return (
          <motion.button
            key={i}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.06, duration: 0.25, ease: 'easeOut' }}
            onClick={() => onSelect(cap.query)}
            className={cn(
              'flex items-center gap-2 px-3 py-2 rounded-full',
              'bg-white border border-brand-cornflower/20',
              'text-sm text-brand-navy',
              'shadow-sm',
              'transition-all duration-200',
              'hover:bg-brand-cornflower/10 hover:border-brand-cornflower/40 hover:shadow-md',
              'focus:outline-none focus:ring-2 focus:ring-brand-cornflower/50'
            )}
          >
            <Icon className="h-4 w-4 text-brand-cornflower" strokeWidth={1.5} />
            <span className="text-xs sm:text-sm font-medium">{cap.label}</span>
          </motion.button>
        )
      })}
    </div>
  )
}

