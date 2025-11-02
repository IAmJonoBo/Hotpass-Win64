import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatDuration(seconds: number): string {
  if (seconds < 60) {
    return `${seconds}s`
  } else if (seconds < 3600) {
    const minutes = Math.floor(seconds / 60)
    const remainingSeconds = seconds % 60
    return `${minutes}m ${remainingSeconds}s`
  } else {
    const hours = Math.floor(seconds / 3600)
    const minutes = Math.floor((seconds % 3600) / 60)
    return `${hours}h ${minutes}m`
  }
}

export function getStatusColor(status: string): string {
  switch (status.toLowerCase()) {
    case 'completed':
    case 'success':
      return 'text-green-600 dark:text-green-400'
    case 'running':
    case 'in_progress':
      return 'text-blue-600 dark:text-blue-400'
    case 'failed':
    case 'error':
      return 'text-red-600 dark:text-red-400'
    case 'pending':
    case 'queued':
      return 'text-yellow-600 dark:text-yellow-400'
    default:
      return 'text-gray-600 dark:text-gray-400'
  }
}

export function getEnvironmentColor(env: string): string {
  switch (env.toLowerCase()) {
    case 'prod':
    case 'production':
      return 'bg-red-600 text-white'
    case 'staging':
      return 'bg-yellow-600 text-white'
    case 'local':
    case 'development':
      return 'bg-blue-600 text-white'
    default:
      return 'bg-gray-600 text-white'
  }
}

export function formatBytes(bytes: number): string {
  if (Number.isNaN(bytes) || bytes < 0) {
    return '0 B'
  }
  if (bytes === 0) {
    return '0 B'
  }
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1)
  const value = bytes / 1024 ** index
  return `${value.toFixed(value >= 10 || index === 0 ? 0 : 1)} ${units[index]}`
}
