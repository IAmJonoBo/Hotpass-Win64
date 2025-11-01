import { render } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { ApiBanner } from './ApiBanner'

const getText = (container: HTMLElement) => container.textContent ?? ''

describe('ApiBanner', () => {
  it('renders variant copy and badge', () => {
    const { container, getByText } = render(
      <ApiBanner
        variant="error"
        title="Prefect API unreachable"
        description="Fallback to cached data"
        badge="fallback"
      />
    )

    expect(getText(container)).toContain('Prefect API unreachable')
    expect(getText(container)).toContain('fallback')
    expect(getByText('Prefect API unreachable')).toBeTruthy()
  })

  it('supports custom action', () => {
    const { getByText } = render(
      <ApiBanner
        variant="warning"
        title="Telemetry degraded"
        action={<button type="button">Retry</button>}
      />
    )

    expect(getByText('Retry')).toBeTruthy()
  })
})
