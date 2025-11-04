import { describe, expect, it, vi } from 'vitest'
import { EventEmitter } from 'events'

vi.mock('child_process', () => {
  const spawn = vi.fn(() => {
    const emitter = new EventEmitter()
    const stdout = new EventEmitter()
    const stderr = new EventEmitter()

    setTimeout(() => {
      stdout.emit('data', Buffer.from('test-output\n'))
    }, 0)

    setTimeout(() => {
      emitter.emit('close', 0, null)
    }, 10)

  return Object.assign(emitter, { stdout, stderr })
  })

  return { spawn, default: { spawn } }
})

describe('command job runner', () => {
  it('emits log and finished events for command jobs', async () => {
    const { createCommandJob, subscribeToJob } = await import('./job-runner.js')

    const job = createCommandJob({
      command: ['echo', 'hello'],
      label: 'smoke test',
    })

    const events = []
    const unsubscribe = subscribeToJob(job.id, (payload) => {
      events.push(payload)
    })

    await new Promise((resolve) => setTimeout(resolve, 30))

    unsubscribe()

    const types = events.map((event) => event.type)
    expect(types).toContain('log')
    expect(types).toContain('finished')
  })
})
