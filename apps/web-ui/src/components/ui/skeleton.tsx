import { cn } from '@/lib/utils'

interface SkeletonProps extends React.HTMLAttributes<HTMLDivElement> {}

export function Skeleton({ className, ...props }: SkeletonProps) {
  return (
    <div
      className={cn(
        'animate-pulse rounded-2xl bg-muted/60 dark:bg-muted/40',
        className,
      )}
      {...props}
    />
  )
}

