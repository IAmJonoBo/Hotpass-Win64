import type { Meta, StoryObj } from '@storybook/react'
import { ApiBanner } from '../components/feedback/ApiBanner'

const meta = {
  title: 'Feedback/ApiBanner',
  component: ApiBanner,
  tags: ['autodocs'],
  args: {
    title: 'Prefect API unreachable',
    description: 'Fallback to cached data until connectivity is restored.',
  },
  parameters: {
    backgrounds: {
      default: 'light',
    },
  },
} satisfies Meta<typeof ApiBanner>

export default meta
type Story = StoryObj<typeof meta>

export const Error: Story = {
  args: {
    variant: 'error',
    badge: 'fallback',
  },
}

export const Warning: Story = {
  args: {
    variant: 'warning',
    title: 'Telemetry degraded',
    description: 'Lineage refresh failed. Insights may be stale.',
  },
}

export const Info: Story = {
  args: {
    variant: 'info',
    title: 'Read-only mode',
    description: 'This UI is connected to a staging backend.',
  },
}

export const Success: Story = {
  args: {
    variant: 'success',
    title: 'Prefect connected',
    description: 'Prefect API health and flow runs synced successfully.',
  },
}
