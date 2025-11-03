import { useEffect, useMemo, useRef, useState } from 'react'
import { Search, LifeBuoy, BookOpen, ExternalLink, Sparkles, ArrowUpRight, Filter, MessageSquare } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Modal, ModalBody, ModalFooter, ModalHeader } from '@/components/ui/modal'
import { helpCategories, helpTopics, type HelpCategory, type HelpTopic } from './helpContent'

interface HelpCenterProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onOpenAssistant?: (message?: string) => void
  initialTopicId?: string
  initialQuery?: string
}

interface HelpResult extends HelpTopic {
  score: number
}

const defaultTopicOrder = helpTopics.map(topic => topic.id)

function computeScore(topic: HelpTopic, query: string, category?: HelpCategory | 'all'): number {
  const normalisedQuery = query.trim().toLowerCase()
  if (!normalisedQuery && (!category || category === 'all')) {
    return 0
  }

  let score = 0
  if (category && category !== 'all' && topic.category === category) {
    score += 2
  }

  if (!normalisedQuery) {
    return score
  }

  const corpus = [
    topic.title,
    topic.summary,
    topic.details,
    ...(topic.steps ?? []),
    ...(topic.keywords ?? []),
  ]
    .join(' ')
    .toLowerCase()

  if (corpus.includes(normalisedQuery)) {
    score += 4
  } else {
    // Lightweight fuzzy match: reward sequential character matches and keyword overlaps
    const queryTokens = normalisedQuery.split(/\s+/).filter(Boolean)
    for (const token of queryTokens) {
      if (corpus.includes(token)) {
        score += 2
      } else if (fuzzyTokenMatch(corpus, token)) {
        score += 1
      }
    }
  }

  // Slight boost for recent updates
  const updated = Date.parse(topic.lastUpdated)
  if (!Number.isNaN(updated)) {
    const daysElapsed = (Date.now() - updated) / (1000 * 60 * 60 * 24)
    if (daysElapsed <= 30) score += 1.5
    else if (daysElapsed <= 90) score += 0.5
  }

  return score
}

function fuzzyTokenMatch(corpus: string, token: string): boolean {
  let corpusIndex = 0
  for (const char of token) {
    corpusIndex = corpus.indexOf(char, corpusIndex)
    if (corpusIndex === -1) {
      return false
    }
    corpusIndex += 1
  }
  return true
}

const featuredTopics = helpTopics.filter(topic => topic.highlight)

export function HelpCenter({ open, onOpenChange, onOpenAssistant, initialTopicId, initialQuery }: HelpCenterProps) {
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState<HelpCategory | 'all'>('all')
  const searchRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (!open) {
      setQuery('')
      setCategory('all')
    }
  }, [open])

  useEffect(() => {
    if (!open) return
    if (initialQuery) {
      setQuery(initialQuery)
    } else if (initialTopicId) {
      const topic = helpTopics.find(item => item.id === initialTopicId)
      if (topic) {
        setQuery(topic.title)
        setCategory('all')
      }
    }
  }, [open, initialQuery, initialTopicId])

  const results = useMemo<HelpResult[]>(() => {
    return helpTopics
      .map(topic => ({
        ...topic,
        score: computeScore(topic, query, category),
      }))
      .filter(topic => topic.score > 0 || (!query && (category === 'all' || topic.category === category)))
      .sort((a, b) => {
        if (b.score !== a.score) return b.score - a.score
        // Preserve default ordering for equal scores
        return defaultTopicOrder.indexOf(a.id) - defaultTopicOrder.indexOf(b.id)
      })
  }, [category, query])

  const visibleTopics = results.length > 0 ? results : helpTopics

  return (
    <Modal
      open={open}
      onOpenChange={onOpenChange}
      initialFocusRef={searchRef}
    >
      <ModalHeader
        title="Help & Operator Guide"
        description="Search across playbooks, troubleshooting steps, and compliance guidance. Everything here is safe to share with partners."
        onClose={() => onOpenChange(false)}
      />
      <ModalBody className="grid gap-6 md:grid-cols-[260px_1fr]">
        <aside className="space-y-4">
          <div className="rounded-xl border bg-muted/50 p-4">
            <div className="flex items-center gap-2 text-sm font-medium">
              <LifeBuoy className="h-4 w-4" />
              Quick actions
            </div>
            <div className="mt-3 flex flex-col gap-2">
              <Button
                variant="outline"
                className="justify-start gap-2"
                onClick={() => onOpenAssistant?.('Summarise the latest Hotpass run issues')}
              >
                <Sparkles className="h-4 w-4" />
                Ask the Assistant
              </Button>
              <Button
                variant="ghost"
                className="justify-start gap-2"
                onClick={() => window.open('/docs/reference/repo-inventory.md', '_blank')}
              >
                <BookOpen className="h-4 w-4" />
                Open Repo Inventory
              </Button>
            </div>
          </div>

          <div className="space-y-3">
            <h3 className="text-xs font-semibold uppercase text-muted-foreground">Filter by category</h3>
            <div className="flex flex-wrap gap-2">
              <Button
                variant={category === 'all' ? 'default' : 'outline'}
                size="sm"
                onClick={() => setCategory('all')}
                className="gap-2"
              >
                <Filter className="h-3 w-3" />
                All
              </Button>
              {helpCategories.map(item => (
                <Button
                  key={item}
                  variant={category === item ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setCategory(item)}
                  className="gap-2"
                >
                  {item}
                </Button>
              ))}
            </div>
          </div>

          <div className="space-y-3">
            <h3 className="text-xs font-semibold uppercase text-muted-foreground">Featured</h3>
            <ul className="space-y-3">
              {featuredTopics.map(topic => (
                <li key={topic.id} className="rounded-lg border bg-card/70 p-3">
                  <p className="text-sm font-medium">{topic.title}</p>
                  <p className="mt-1 text-xs text-muted-foreground">{topic.summary}</p>
                  {topic.highlight && (
                    <Badge variant="outline" className="mt-2 text-[10px] uppercase tracking-wide">
                      {topic.highlight}
                    </Badge>
                  )}
                </li>
              ))}
            </ul>
          </div>
        </aside>
        <section className="flex flex-col gap-4">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              ref={searchRef}
              type="search"
              placeholder="Search playbooks, policies, troubleshooting… (⌘/Ctrl + Shift + F)"
              value={query}
              onChange={event => setQuery(event.target.value)}
              className="pl-9"
            />
          </div>
          <div className="grid gap-4">
            {visibleTopics.map(topic => (
              <article
                key={topic.id}
                className="rounded-2xl border border-border/60 bg-card/80 p-5 shadow-sm transition hover:border-primary/60 hover:shadow-md"
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <Badge variant="outline">{topic.category}</Badge>
                      <span className="text-xs text-muted-foreground">Updated {topic.lastUpdated}</span>
                    </div>
                    <h3 className="mt-2 text-lg font-semibold leading-snug">{topic.title}</h3>
                    <p className="mt-1 text-sm text-muted-foreground">{topic.summary}</p>
                  </div>
                  <div className="flex flex-col gap-2">
                    {topic.docPath && (
                      <Button
                        variant="outline"
                        size="sm"
                        className="gap-2"
                        onClick={() => window.open(`/${topic.docPath}`, '_blank')}
                      >
                        <BookOpen className="h-4 w-4" />
                        View doc
                      </Button>
                    )}
                    {onOpenAssistant && (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="gap-2"
                        onClick={() => onOpenAssistant(`Help me with: ${topic.title}. Context: ${topic.summary}`)}
                      >
                        <MessageSquare className="h-4 w-4" />
                        Ask assistant
                      </Button>
                    )}
                  </div>
                </div>
                <p className="mt-4 text-sm leading-relaxed text-muted-foreground">{topic.details}</p>
                {topic.steps && (
                  <ol className="mt-4 space-y-2 text-sm text-muted-foreground">
                    {topic.steps.map((step, index) => (
                      <li key={`${topic.id}-step-${index}`} className="flex gap-2">
                        <span className="mt-0.5 h-5 w-5 flex-shrink-0 rounded-full bg-primary/10 text-center text-xs font-semibold leading-5 text-primary">
                          {index + 1}
                        </span>
                        <span>{step}</span>
                      </li>
                    ))}
                  </ol>
                )}
                {topic.relatedIds && topic.relatedIds.length > 0 && (
                  <div className="mt-4 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                    <ArrowUpRight className="h-3 w-3" />
                    <span>Related:</span>
                    {topic.relatedIds
                      .map(id => helpTopics.find(item => item.id === id))
                      .filter(Boolean)
                      .map(related => (
                        <button
                          key={`${topic.id}-related-${related!.id}`}
                          type="button"
                          className="rounded-full border border-border/60 px-2 py-0.5 transition hover:border-primary hover:text-primary"
                          onClick={() => {
                            setQuery(related!.title)
                            setCategory('all')
                          }}
                        >
                          {related!.title}
                        </button>
                      ))}
                  </div>
                )}
                {topic.externalUrl && (
                  <div className="mt-4 flex items-center gap-2 text-xs text-muted-foreground">
                    <ExternalLink className="h-3 w-3" />
                    <a href={topic.externalUrl} target="_blank" rel="noreferrer" className="underline">
                      External resource
                    </a>
                  </div>
                )}
              </article>
            ))}
          </div>
        </section>
      </ModalBody>
      <ModalFooter>
        <div className="text-xs text-muted-foreground">
          Need escalated support? Ping <code className="rounded bg-muted/60 px-1.5 py-0.5 text-[11px]">#hotpass-ops</code> or review the <span className="underline cursor-pointer" onClick={() => window.open('/docs/docs/policies/THREAT_MODEL.md', '_blank')}>Threat Model</span>.
        </div>
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" onClick={() => onOpenChange(false)}>
            Close
          </Button>
          <Button
            size="sm"
            className="gap-2"
            onClick={() => onOpenAssistant?.('Summarise outstanding remediation tasks from the compliance backlog')}
          >
            <Sparkles className="h-4 w-4" />
            Generate action plan
          </Button>
        </div>
      </ModalFooter>
    </Modal>
  )
}
