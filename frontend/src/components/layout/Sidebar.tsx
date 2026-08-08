'use client'

import React, { createContext, useContext, useState } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { cn } from '@/lib/utils'
import { Logomark } from '@/components/brand'
import { Icons } from '@/components/ui/icons'
import { Avatar } from '@/components/ui/avatar'
import { Button } from '@/components/ui/button'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { useSession } from 'next-auth/react'
import { useAIOptional } from '@/context/AIContext'

// Sidebar context for collapse state
interface SidebarContextType {
  isCollapsed: boolean
  setIsCollapsed: (collapsed: boolean) => void
  toggle: () => void
}

const SidebarContext = createContext<SidebarContextType | undefined>(undefined)

export function useSidebar() {
  const context = useContext(SidebarContext)
  if (!context) {
    throw new Error('useSidebar must be used within a SidebarProvider')
  }
  return context
}

export function SidebarProvider({ children }: { children: React.ReactNode }) {
  const [isCollapsed, setIsCollapsed] = useState(false)
  const toggle = () => setIsCollapsed(!isCollapsed)

  return (
    <SidebarContext.Provider value={{ isCollapsed, setIsCollapsed, toggle }}>
      {children}
    </SidebarContext.Provider>
  )
}

// Navigation items configuration
interface NavItem {
  href: string
  label: string
  icon: React.ElementType
  adminOnly?: boolean
  /** Opens the AI Manager panel instead of navigating. */
  opensManager?: boolean
}

interface NavSection {
  title: string
  items: NavItem[]
}

// Grouped so the five screens the brief asks for are visible together and in
// its order, rather than mixed in with the ones we added. Eight flat items gave
// no signal about which was which, and the AI Manager was reachable only from a
// button in the header — a required screen that a reader could miss entirely.
const navItems: NavSection[] = [
  {
    title: 'Command Center',
    items: [
      { href: '/', label: 'Dashboard', icon: Icons.dashboard },
      { href: '#ai-manager', label: 'AI Manager', icon: Icons.sparkles, opensManager: true },
      { href: '/ai/policies', label: 'AI Policies', icon: Icons.brain },
      { href: '/workbench', label: 'AI Workbench', icon: Icons.workbench },
      { href: '/ai/insights', label: 'AI Insights', icon: Icons.lightbulb },
    ],
  },
  {
    title: 'Beyond the brief',
    items: [
      { href: '/elimination', label: 'Elimination', icon: Icons.target },
      { href: '/ai/resolution', label: 'Auto Resolution', icon: Icons.zap },
      { href: '/data-manager', label: 'Data Manager', icon: Icons.database },
    ],
  },
  {
    title: 'System',
    items: [
      { href: '/settings', label: 'Settings', icon: Icons.settings },
    ],
  },
]

// Navigation Link Component
interface NavLinkProps {
  href: string
  icon: React.ElementType
  children: React.ReactNode
  isCollapsed?: boolean
  badge?: number
  opensManager?: boolean
}

function NavLink({
  href,
  icon: Icon,
  children,
  isCollapsed,
  badge,
  opensManager,
}: NavLinkProps) {
  const pathname = usePathname()
  // Optional: Next prerenders its 404 and error pages without the app's
  // providers, and a hook that throws there fails the whole production build.
  const ai = useAIOptional()
  const isActive = opensManager ? Boolean(ai?.isManagerOpen) : pathname === href

  // The AI Manager is a panel, not a route. It still belongs in the nav — it is
  // one of the five screens the brief asks for, and a header button is easy to
  // miss — so it renders as a nav item that opens the panel.
  // Written as two branches rather than one element with a swapped tag: a Link
  // and a button take different props, and the version that spread them
  // dynamically passed in dev and failed the production build.
  const className = cn(
    opensManager && 'w-full text-left',
    'group relative flex items-center gap-3 rounded-xl px-3 py-2.5',
    'text-sm font-medium',
    'transition-all duration-200 ease-out',
    isActive
      ? 'bg-brand-navy text-white shadow-soft'
      : 'text-brand-muted hover:translate-x-1 hover:bg-brand-cornflower/10 hover:text-brand-navy',
    isCollapsed && 'justify-center px-2 hover:translate-x-0'
  )

  const inner = (
    <>
      <Icon
        strokeWidth={1.5}
        className={cn(
          'h-5 w-5 shrink-0 transition-all duration-200',
          isActive
            ? 'text-white'
            : 'text-brand-muted group-hover:scale-110 group-hover:text-brand-navy'
        )}
      />

      {!isCollapsed && <span className='truncate'>{children}</span>}

      {badge !== undefined && badge > 0 && (
        <span
          className={cn(
            'ml-auto flex h-5 min-w-5 items-center justify-center rounded-full px-1.5',
            'text-[10px] font-semibold',
            'transition-transform duration-200',
            isActive
              ? 'bg-white/20 text-white'
              : 'bg-brand-cornflower/20 text-brand-navy group-hover:scale-110',
            isCollapsed && 'absolute -right-1 -top-1 h-4 min-w-4 text-[9px]'
          )}
        >
          {badge > 99 ? '99+' : badge}
        </span>
      )}
    </>
  )

  const linkContent = opensManager ? (
    <button type='button' onClick={() => ai?.openManager()} className={className}>
      {inner}
    </button>
  ) : (
    <Link href={href} className={className}>
      {inner}
    </Link>
  )

  // Wrap with tooltip when collapsed
  if (isCollapsed) {
    return (
      <Tooltip delayDuration={0}>
        <TooltipTrigger asChild>{linkContent}</TooltipTrigger>
        <TooltipContent side='right' className='ml-2'>
          {children}
        </TooltipContent>
      </Tooltip>
    )
  }

  return linkContent
}

// User section at bottom of sidebar
function SidebarUser({ isCollapsed }: { isCollapsed: boolean }) {
  const { data: session } = useSession()
  const basePath = process.env.NEXT_PUBLIC_BASE_PATH || ''

  if (!session?.user) return null

  return (
    <div
      className={cn(
        'flex items-center gap-3 rounded-xl p-3',
        'border border-black/[0.04] bg-black/[0.02]',
        isCollapsed && 'justify-center p-2'
      )}
    >
      <Avatar
        src={session.user.image}
        fallback={session.user.name || session.user.email || '?'}
        size='sm'
        showStatus
        status='online'
      />

      {!isCollapsed && (
        <div className='min-w-0 flex-1'>
          <p className='truncate text-sm font-medium text-brand-navy'>
            {session.user.name}
          </p>
          <p className='truncate text-xs text-brand-muted'>
            {session.user.email}
          </p>
        </div>
      )}

      {!isCollapsed && (
        <Button
          variant='ghost'
          size='icon-sm'
          onClick={() => {
            window.location.href = `${basePath}/api/auth/logout`
          }}
          className='shrink-0 text-brand-muted hover:text-brand-navy'
          title='Sign Out'
        >
          <Icons.logout className='h-4 w-4' />
        </Button>
      )}
    </div>
  )
}

export function Sidebar() {
  const { isCollapsed, setIsCollapsed } = useSidebar()
  const { data: session } = useSession()

  // Check if user is admin
  const isAdmin = session?.roles?.includes('admin')

  // Filter navigation items based on user role
  const filteredNavItems = navItems
    .map((section) => ({
      ...section,
      items: section.items.filter((item) => !item.adminOnly || isAdmin),
    }))
    .filter((section) => section.items.length > 0)

  return (
    <TooltipProvider>
      <aside
        role='navigation'
        aria-label='Main navigation'
        className={cn(
          'hidden flex-col md:flex',
          'fixed bottom-0 left-0 top-0 z-fixed',
          // Glass Rail effect
          'bg-white/70 backdrop-blur-xl',
          'border-r border-black/[0.06]',
          // Inner highlight
          'shadow-[inset_-1px_0_0_rgba(255,255,255,0.8)]',
          // Width transition
          'transition-all duration-300 ease-out',
          isCollapsed ? 'w-16' : 'w-64'
        )}
      >
        {/* Logo Section */}
        <div
          className={cn(
            'flex h-20 items-center px-4',
            'border-b border-black/[0.04]',
            isCollapsed && 'justify-center px-2'
          )}
        >
          <Link href='/' className='group flex items-center gap-3'>
            <div
              className={cn(
                'flex h-10 w-10 items-center justify-center rounded-xl bg-brand-navy shadow-soft',
                'transition-all duration-300 ease-out',
                'group-hover:scale-105 group-hover:shadow-accent'
              )}
            >
              <Logomark variant='light' size={24} />
            </div>

            {!isCollapsed && (
              <div className='flex flex-col transition-transform duration-200 group-hover:translate-x-0.5'>
                <span className='font-display text-lg font-bold tracking-tight text-brand-navy'>
                  AutoPilot
                </span>
                <span className='text-[10px] font-medium uppercase tracking-widest text-brand-muted'>
                  Command Center
                </span>
              </div>
            )}
          </Link>
        </div>

        {/* Navigation Section */}
        <nav
          aria-label='Primary navigation'
          className='scrollbar-hide flex-1 overflow-y-auto px-3 py-4'
        >
          {filteredNavItems.map((section, sectionIndex) => (
            <div key={section.title} className={cn(sectionIndex > 0 && 'mt-6')}>
              {!isCollapsed && (
                <p className='mb-2 px-3 text-[10px] font-semibold uppercase tracking-widest text-brand-muted/70'>
                  {section.title}
                </p>
              )}
              <div className='space-y-1'>
                {section.items.map((item) => (
                  <NavLink
                    key={item.href}
                    href={item.href}
                    icon={item.icon}
                    isCollapsed={isCollapsed}
                    opensManager={item.opensManager}
                  >
                    {item.label}
                  </NavLink>
                ))}
              </div>
            </div>
          ))}
        </nav>

        {/* User Section */}
        <div className='border-t border-black/[0.04] p-3'>
          <SidebarUser isCollapsed={isCollapsed} />
        </div>

        {/* Collapse Toggle */}
        <div className='border-t border-black/[0.04] p-3'>
          <Tooltip delayDuration={0}>
            <TooltipTrigger asChild>
              <Button
                variant='ghost'
                size={isCollapsed ? 'icon-sm' : 'sm'}
                onClick={() => setIsCollapsed(!isCollapsed)}
                className={cn(
                  'w-full text-brand-muted hover:text-brand-navy',
                  isCollapsed && 'px-0'
                )}
                aria-label={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
              >
                {isCollapsed ? (
                  <Icons.panelOpen className='h-4 w-4' />
                ) : (
                  <>
                    <Icons.panelClose className='h-4 w-4' />
                    <span className='ml-2'>Collapse</span>
                  </>
                )}
              </Button>
            </TooltipTrigger>
            {isCollapsed && (
              <TooltipContent side='right' className='ml-2'>
                Expand sidebar
              </TooltipContent>
            )}
          </Tooltip>
        </div>
      </aside>
    </TooltipProvider>
  )
}

