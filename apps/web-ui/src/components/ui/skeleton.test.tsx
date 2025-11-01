import { render } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { Skeleton } from './skeleton'

describe('Skeleton', () => {
  it('merges custom class names', () => {
    const { container } = render(<Skeleton className="h-4 w-4" />)
    const div = container.querySelector('div')
    expect(div).not.toBeNull()
    expect(div?.className).toContain('h-4')
    expect(div?.className).toContain('animate-pulse')
  })
})
