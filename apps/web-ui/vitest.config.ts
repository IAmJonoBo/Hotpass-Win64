import { defineConfig } from 'vitest/config'
import path from 'path'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  test: {
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
    globals: true,
    coverage: {
      provider: 'v8',
      reporter: ['text', 'lcov', 'html'],
      reportsDirectory: './coverage/unit',
      include: [
        'src/hooks/**/*.{ts,tsx}',
        'src/components/feedback/**/*.{ts,tsx}',
        'src/components/ui/skeleton.tsx',
      ],
      exclude: [
        'src/main.tsx',
        'src/App.tsx',
        'src/**/*.stories.tsx',
        'src/**/*.spec.ts',
        'src/tests/**',
        'src/test/**',
      ],
      thresholds: {
        statements: 60,
        branches: 50,
        functions: 60,
        lines: 60,
      },
    },
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
})
