import { test, expect } from '@playwright/test'

test.describe('Failure UX', () => {
  test.beforeEach(async ({ page }) => {
    await page.route('**/api/prefect/flow_runs**', async (route) => {
      await route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ detail: 'upstream error' }) })
    })
    await page.route('**/api/prefect/flows**', async (route) => {
      await route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ detail: 'upstream error' }) })
    })
    await page.route('**/api/marquez/api/v1/namespaces**', async (route) => {
      await route.fulfill({ status: 200, body: JSON.stringify({ namespaces: [{ name: 'hotpass' }] }) })
    })
    await page.route('**/api/marquez/api/v1/namespaces/hotpass/jobs**', async (route) => {
      await route.fulfill({ status: 200, body: JSON.stringify({ jobs: [] }) })
    })
  })

  test('shows API banner fallback when Prefect errors', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByText('Prefect API unreachable')).toBeVisible()
    await expect(page.getByText(/fallback/i)).toBeVisible()
    await expect(page.getByText('Latest 50 Spreadsheets')).toBeVisible()
  })
})
