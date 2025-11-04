import type { ReactElement } from 'react'
import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { CellSpotlight } from '../CellSpotlight'

const sampleProfile = {
  workbook: 'Vendors.xlsx',
  sheets: [
    {
      name: 'Master',
      rows: 120,
      columns: [],
      sampleRows: [],
      role: 'master',
      join_keys: [],
    },
  ],
  issues: [],
} as unknown as import('@/types').ImportProfile

const renderWithClient = (ui: ReactElement) => {
  const client = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  })
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>)
}

describe('CellSpotlight', () => {
  it('renders latest cell fix details when logs contain matches', async () => {
    renderWithClient(
      <CellSpotlight
        logs={[
          '[info] Sheet Master Cell B14 auto-fix applied by rule rename_company -- trimmed whitespace',
        ]}
        profile={sampleProfile}
      />,
    )

    expect(screen.getAllByText(/Master/i).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/Cell B14/i).length).toBeGreaterThan(0)
    expect(screen.getByText(/auto-fix applied/i)).toBeInTheDocument()
    expect(await screen.findByRole('button', { name: /Rule rename_company/i })).toBeInTheDocument()
  })

  it('shows fallback message when no matches found', () => {
    renderWithClient(<CellSpotlight logs={['Generic log entry']} profile={null} />)

    expect(
      screen.getByText(/No cell corrections detected yet/i),
    ).toBeInTheDocument()
  })
})
