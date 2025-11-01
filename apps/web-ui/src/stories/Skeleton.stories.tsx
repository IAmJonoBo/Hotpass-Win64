import type { Meta, StoryObj } from '@storybook/react'
import { Skeleton } from '../components/ui/skeleton'

const meta = {
  title: 'UI/Skeleton',
  component: Skeleton,
  tags: ['autodocs'],
  args: {
    className: 'h-8 w-64',
  },
} satisfies Meta<typeof Skeleton>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {}

export const CardPreview: Story = {
  render: () => (
    <div className="w-80 space-y-4 rounded-2xl border border-border/60 p-6">
      <Skeleton className="h-6 w-40" />
      <Skeleton className="h-4 w-full" />
      <Skeleton className="h-32 w-full" />
    </div>
  ),
}

