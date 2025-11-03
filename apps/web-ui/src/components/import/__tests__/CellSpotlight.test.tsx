import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
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

describe('CellSpotlight', () => {
  it('renders latest cell fix details when logs contain matches', () => {
    render(
      <CellSpotlight
        logs={[
          '[info] Sheet Master Cell B14 auto-fix applied by rule rename_company -- trimmed whitespace',
        ]}
        profile={sampleProfile}
      />,
    )

    expect(screen.getByText(/Master/i)).toBeInTheDocument()
    expect(screen.getByText(/Cell B14/i)).toBeInTheDocument()
    expect(screen.getByText(/auto-fix applied/i)).toBeInTheDocument()
    expect(screen.getByText(/rename_company/i)).toBeInTheDocument()
  })

  it('shows fallback message when no matches found', () => {
    render(<CellSpotlight logs={['Generic log entry']} profile={null} />)

    expect(
      screen.getByText(/No cell corrections detected yet/i),
    ).toBeInTheDocument()
  })
})
