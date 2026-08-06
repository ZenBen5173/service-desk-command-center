'use client'

import { useRef, useEffect, useCallback, useState } from 'react'
import { createPortal } from 'react-dom'
import { useSession } from 'next-auth/react'
import { motion, AnimatePresence } from 'framer-motion'
import { cn } from '@/lib/utils'
import { apiClient } from '@/lib/api-client'
import { useAI } from '@/context/AIContext'
import { Icons } from '@/components/ui/icons'
import { Button } from '@/components/ui/button'
import { ChatMessage } from './ChatMessage'
import { ChatInput } from './ChatInput'
import { CapabilityBubbles } from './CapabilityBubbles'

// ============================================================================
// Animation Variants
// ============================================================================

const overlayVariants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1 },
  exit: { opacity: 0 },
}

const modalVariants = {
  hidden: { 
    opacity: 0, 
    scale: 0.95,
    y: 20,
  },
  visible: { 
    opacity: 1, 
    scale: 1,
    y: 0,
    transition: {
      type: 'spring',
      damping: 25,
      stiffness: 300,
    }
  },
  exit: { 
    opacity: 0, 
    scale: 0.95,
    y: 20,
    transition: {
      duration: 0.15,
    }
  },
}

// ============================================================================
// AI Manager Component
// ============================================================================

export function AIManager() {
  const { data: session } = useSession()
  const {
    isManagerOpen,
    closeManager,
    chatHistory,
    addMessage,
    clearHistory,
    isTyping,
    setIsTyping,
    currentPageContext,
  } = useAI()

  const messagesEndRef = useRef<HTMLDivElement>(null)
  const modalRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [chatHistory, isTyping])

  // Handle escape key to close
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isManagerOpen) {
        closeManager()
      }
    }
    
    if (isManagerOpen) {
      document.addEventListener('keydown', handleKeyDown)
      // Prevent body scroll when modal is open
      document.body.style.overflow = 'hidden'
    }
    
    return () => {
      document.removeEventListener('keydown', handleKeyDown)
      document.body.style.overflow = ''
    }
  }, [isManagerOpen, closeManager])

  // Focus trap - focus the modal when it opens
  useEffect(() => {
    if (isManagerOpen && modalRef.current) {
      modalRef.current.focus()
    }
  }, [isManagerOpen])

  const [followUps, setFollowUps] = useState<string[]>([])

  // Handle sending a message
  const handleSendMessage = useCallback(async (content: string) => {
    // Add user message
    addMessage({ role: 'user', content })

    // Add loading message
    addMessage({ role: 'assistant', content: '', isLoading: true })
    setIsTyping(true)

    try {
      // Answers come from the AI Manager service, which assembles them from
      // mirrored Supervity Auto data and names the Operator each figure came
      // from. Deliberately not a language model: a summary that drifts from
      // the audit record is the exact failure this project set out to avoid.
      const data = await apiClient.post<{
        answer: string
        intent: string
        citations: string[]
        suggestions: string[]
      }>('/api/manager/ask', { question: content })

      const cited = data.citations?.length
        ? `

Source: ${data.citations.join(', ')}`
        : ''

      addMessage({
        role: 'assistant',
        content: (data.answer || 'I could not answer that from agent data.') + cited,
      })

      if (data.suggestions?.length) {
        setFollowUps(data.suggestions)
      }
    } catch {
      addMessage({
        role: 'assistant',
        content:
          'I could not reach the operation data. Check the backend is running, then try again.',
      })
    } finally {
      setIsTyping(false)
    }
  }, [addMessage, setIsTyping])

  // Handle quick action click
  const handleQuickAction = (action: string) => {
    handleSendMessage(action)
  }

  // Get page name from context
  const getPageName = () => {
    if (currentPageContext === '/') return 'Dashboard'
    const segments = currentPageContext.split('/').filter(Boolean)
    return segments.map(s => s.charAt(0).toUpperCase() + s.slice(1)).join(' > ')
  }

  // Handle backdrop click
  const handleBackdropClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) {
      closeManager()
    }
  }

  // Only render in browser (for portal)
  if (typeof window === 'undefined') return null

  return createPortal(
    <AnimatePresence mode="wait">
      {isManagerOpen && (
        <>
          {/* Backdrop with blur - covers entire viewport including sidebar */}
          <motion.div
            key="ai-manager-backdrop"
            variants={overlayVariants}
            initial="hidden"
            animate="visible"
            exit="exit"
            transition={{ duration: 0.2 }}
            onClick={handleBackdropClick}
            className="fixed inset-0 z-modal-backdrop flex items-center justify-center p-4 sm:p-8 md:p-12"
            style={{
              backgroundColor: 'rgba(26, 35, 64, 0.5)',
              backdropFilter: 'blur(12px)',
              WebkitBackdropFilter: 'blur(12px)',
            }}
            aria-hidden="true"
          >
            {/* Modal Container - centered and properly sized */}
            <motion.div
              ref={modalRef}
              key="ai-manager-modal"
              variants={modalVariants}
              initial="hidden"
              animate="visible"
              exit="exit"
              role="dialog"
              aria-modal="true"
              aria-labelledby="ai-manager-title"
              aria-describedby="ai-manager-description"
              tabIndex={-1}
              onClick={(e) => e.stopPropagation()}
              className={cn(
                // Z-index for proper stacking
                'z-modal',
                // Size and positioning
                'relative w-full max-w-2xl',
                'h-[80vh] max-h-[700px] min-h-[450px]',
                // Solid white background for better readability
                'bg-white',
                // Border and shadow
                'border border-gray-200',
                'rounded-2xl',
                'shadow-2xl',
                // Layout
                'flex flex-col',
                'overflow-hidden'
              )}
            >
              {/* Decorative gradient border */}
              <div className="absolute inset-0 rounded-2xl bg-gradient-to-br from-brand-cornflower/20 via-transparent to-brand-purple/20 pointer-events-none" />
              
              {/* Header */}
              <div className="relative border-b border-border/30 px-6 py-5">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    {/* AI Icon */}
                    <div className={cn(
                      'flex h-12 w-12 items-center justify-center rounded-xl',
                      'bg-gradient-to-br from-brand-navy via-brand-purple to-brand-cornflower',
                      'shadow-lg shadow-brand-purple/25',
                      'ring-2 ring-white/50'
                    )}>
                      <Icons.sparkles className="h-6 w-6 text-white" strokeWidth={1.5} />
                    </div>
                    
                    <div>
                      <h2 
                        id="ai-manager-title"
                        className="text-xl font-semibold text-brand-navy"
                      >
                        AutoPilot AI
                      </h2>
                      <p 
                        id="ai-manager-description"
                        className="text-sm text-muted-foreground"
                      >
                        Your intelligent command center assistant
                      </p>
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-2">
                    {chatHistory.length > 0 && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={clearHistory}
                        className="text-muted-foreground hover:text-foreground gap-1.5"
                        title="Clear conversation"
                      >
                        <Icons.trash className="h-4 w-4" strokeWidth={1.5} />
                        <span className="hidden sm:inline">Clear</span>
                      </Button>
                    )}
                    
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={closeManager}
                      className="text-muted-foreground hover:text-foreground hover:bg-red-50 hover:text-red-600"
                      title="Close (Esc)"
                    >
                      <Icons.close className="h-5 w-5" strokeWidth={1.5} />
                    </Button>
                  </div>
                </div>

                {/* Page Context Badge */}
                <div className="mt-4 flex items-center gap-3">
                  <div className={cn(
                    'inline-flex items-center gap-2 rounded-full px-3 py-1.5',
                    'bg-gradient-to-r from-brand-cornflower/10 to-brand-purple/10',
                    'text-brand-navy border border-brand-cornflower/20',
                    'text-sm font-medium'
                  )}>
                    <Icons.globe className="h-4 w-4 text-brand-cornflower" strokeWidth={1.5} />
                    <span>Viewing: {getPageName()}</span>
                  </div>
                  
                  <kbd className={cn(
                    'hidden items-center rounded-md px-2 py-1 sm:inline-flex',
                    'text-xs font-medium',
                    'border border-border/50 bg-muted/50 text-muted-foreground'
                  )}>
                    <Icons.command className="h-3 w-3 mr-1" />
                    J to toggle
                  </kbd>
                </div>
              </div>

              {/* Messages Area */}
              <div className="relative flex-1 overflow-y-auto px-6 py-5">
                {chatHistory.length === 0 ? (
                  /* Empty State */
                  <div className="flex h-full flex-col items-center justify-center text-center py-8">
                    <div className={cn(
                      'mb-6 flex h-20 w-20 items-center justify-center rounded-2xl',
                      'bg-gradient-to-br from-brand-cornflower/20 to-brand-purple/20',
                      'ring-1 ring-brand-cornflower/30'
                    )}>
                      <Icons.messageSquare className="h-10 w-10 text-brand-cornflower" strokeWidth={1.5} />
                    </div>
                    
                    <h3 className="font-display text-xl font-semibold text-brand-navy">
                      How can I help you?
                    </h3>
                    <p className="mt-2 max-w-sm text-muted-foreground">
                      Ask about the operation. Every answer is built from what the
                      Operators reported on Supervity Auto, and names the agent it
                      came from.
                    </p>

                    {/* Quick Actions - Capability Bubbles */}
                    <div className="mt-8 w-full max-w-lg">
                      <CapabilityBubbles onSelect={handleQuickAction} />
                    </div>
                  </div>
                ) : (
                  /* Chat Messages */
                  <div className="space-y-4">
                    {chatHistory.map((message) => (
                      <ChatMessage
                        key={message.id}
                        message={message}
                        userName={session?.user?.name || undefined}
                        userImage={session?.user?.image}
                      />
                    ))}
                    <div ref={messagesEndRef} />

                    {followUps.length > 0 && !isTyping && (
                      <div className="flex flex-wrap gap-2 pt-1">
                        {followUps.map((q) => (
                          <button
                            key={q}
                            onClick={() => handleQuickAction(q)}
                            className={cn(
                              'rounded-full border border-brand-cornflower/25 bg-white',
                              'px-3 py-1.5 text-xs font-medium text-brand-navy',
                              'transition-colors hover:bg-brand-cornflower/10'
                            )}
                          >
                            {q}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Input Area */}
              <div className="relative border-t border-border/30">
                <ChatInput
                  onSend={handleSendMessage}
                  disabled={isTyping}
                  placeholder={isTyping ? 'AI is thinking...' : 'Ask anything...'}
                />
              </div>
            </motion.div>
          </motion.div>
        </>
      )}
    </AnimatePresence>,
    document.body
  )
}
