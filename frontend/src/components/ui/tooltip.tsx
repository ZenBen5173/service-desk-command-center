'use client'

import * as React from 'react'
import * as TooltipPrimitive from '@radix-ui/react-tooltip'
import { cn } from '@/lib/utils'

const TooltipProvider = TooltipPrimitive.Provider

const Tooltip = TooltipPrimitive.Root

const TooltipTrigger = TooltipPrimitive.Trigger

const TooltipContent = React.forwardRef<
  React.ElementRef<typeof TooltipPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof TooltipPrimitive.Content>
>(({ className, sideOffset = 4, ...props }, ref) => (
  // Portalled to the body. Rendered inline, the tooltip is clipped by any
  // ancestor with overflow-hidden — which every Card here has, so a tooltip on
  // a stat tile was cut off at the card's edge.
  <TooltipPrimitive.Portal>
  <TooltipPrimitive.Content
    ref={ref}
    sideOffset={sideOffset}
    className={cn(
      'z-tooltip overflow-hidden',
      'rounded-lg px-3 py-1.5',
      'bg-brand-navy text-white',
      'text-xs font-medium',
      'shadow-float',
      'animate-fade-in',
      className
    )}
    {...props}
  />
  </TooltipPrimitive.Portal>
))
TooltipContent.displayName = TooltipPrimitive.Content.displayName

export { Tooltip, TooltipTrigger, TooltipContent, TooltipProvider }
