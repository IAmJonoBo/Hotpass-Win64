import { describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { InventoryOverview } from './InventoryOverview'
import type { InventorySnapshot } from '@/types/inventory'

const snapshot: InventorySnapshot = {
  manifest: {
    version: '1.2.3',
    maintainer: 'Platform',
    reviewCadence: 'quarterly',
  },
  summary: {
    total: 2,
    byType: { database: 1, secret: 1 },
    byClassification: { confidential: 1, internal: 1 },
  },
  requirements: [
    { id: 'backend', surface: 'backend', description: 'Service available', status: 'implemented', detail: null },
    { id: 'frontend', surface: 'frontend', description: 'UI available', status: 'planned', detail: null },
  ],
  assets: [
    {
      id: 'asset-1',
      name: 'Secret store',
      type: 'secret',
      classification: 'confidential',
      owner: 'Security',
      custodian: 'Platform',
      location: 'vault://secrets',
      description: 'Secrets',
      dependencies: ['vault'],
      controls: ['rotation'],
    },
    {
      id: 'asset-2',
      name: 'Telemetry database',
      type: 'database',
      classification: 'internal',
      owner: 'Observability',
      custodian: 'Platform',
      location: '/data',
      description: 'Telemetry events',
      dependencies: [],
      controls: [],
    },
  ],
  generatedAt: '2025-03-01T00:00:00Z',
}

describe('InventoryOverview', () => {
  it('renders summary and asset table', () => {
    render(<InventoryOverview snapshot={snapshot} />)

    expect(screen.getByText('Total assets')).toBeInTheDocument()
    expect(screen.getByText('2')).toBeInTheDocument()
    expect(screen.getByText('Secret store')).toBeInTheDocument()
    expect(screen.getByText('Telemetry database')).toBeInTheDocument()
    expect(screen.getByText('Backend, CLI, and UI readiness for the inventory feature')).toBeInTheDocument()
  })

  it('filters assets by search query', () => {
    render(<InventoryOverview snapshot={snapshot} />)

    const input = screen.getByPlaceholderText('Search by name, owner, custodian, or type')
    fireEvent.change(input, { target: { value: 'telemetry' } })

    expect(screen.getByText('Telemetry database')).toBeInTheDocument()
    expect(screen.queryByText('Secret store')).not.toBeInTheDocument()
  })

  it('shows loading state when requested', () => {
    const { container } = render(<InventoryOverview snapshot={null} isLoading />)
    expect(container.querySelectorAll('.animate-pulse').length).toBeGreaterThan(0)
  })

  it('renders error state and handles retry', () => {
    const onRetry = vi.fn()
    render(<InventoryOverview snapshot={null} error="failed" onRetry={onRetry} />)

    expect(screen.getByText('Unable to load inventory')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }))
    expect(onRetry).toHaveBeenCalled()
  })
})
