'use client'

import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { Icons } from '@/components/ui/icons'

/**
 * The explanation behind a headline number, on hover.
 *
 * Every stat on this Command Center is a claim about what the agents did, and
 * most of them carry a caveat worth knowing — what is counted, what is
 * excluded, whether it is measured or forecast. Printed on the card those
 * caveats pushed the actual content below the fold; dropped entirely, the
 * number becomes something the reader has to take on trust.
 */
export function StatInfo({ children }: { children: React.ReactNode }) {
  return (
    <TooltipProvider>
      <Tooltip delayDuration={100}>
        <TooltipTrigger asChild>
          <span
            tabIndex={0}
            aria-label='What this number means'
            className='cursor-help text-muted-foreground/60 transition-colors hover:text-brand-navy'
          >
            <Icons.info className='h-3.5 w-3.5' strokeWidth={1.5} />
          </span>
        </TooltipTrigger>
        <TooltipContent side='top' className='max-w-xs text-xs leading-relaxed'>
          {children}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}
