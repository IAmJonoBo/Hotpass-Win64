import { expect, test } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'

const ROUTES = ['/', '/lineage', '/admin', '/assistant'] as const
const OUTPUT_DIR = process.env.AXE_OUTPUT_DIR ?? 'playwright-report/axe'

const slugify = (route: (typeof ROUTES)[number]) =>
  route === '/' ? 'root' : route.replace(/[^a-z0-9]+/gi, '-').replace(/^-|-$/g, '')

test.describe('Accessibility axe scans', () => {
  for (const route of ROUTES) {
    test(`should not report WCAG violations on ${route}`, async ({ page }) => {
      await page.goto(route)
      await page.waitForLoadState('networkidle')

      const results = await new AxeBuilder({ page })
        .withTags(['wcag2a', 'wcag2aa'])
        .analyze()

      await mkdir(OUTPUT_DIR, { recursive: true })
      const filePath = path.join(OUTPUT_DIR, `${slugify(route)}.json`)
      await writeFile(filePath, JSON.stringify(results, null, 2), 'utf-8')

      expect(results.violations, `Accessibility violations for ${route}`).toHaveLength(0)
    })
  }
})
