import { test, expect } from '@playwright/test'

test.describe('auth guardrails', () => {
  test('blocks admin route without admin role', async ({ page }) => {
    await page.addInitScript((roles: string) => {
      window.localStorage.setItem('hotpass_mock_roles', roles)
    }, 'operator')
    await page.goto('/')
    await page.goto('/admin')
    await expect(page.getByRole('heading', { name: 'Access restricted' })).toBeVisible()
    await expect(page.getByRole('alert')).toContainText('You do not have permission to view this area.')
  })

  test('allows admin route with admin role', async ({ page }) => {
    await page.addInitScript((roles: string) => {
      window.localStorage.setItem('hotpass_mock_roles', roles)
    }, 'admin')
    await page.goto('/admin')
    await expect(page.getByRole('heading', { name: 'Admin Settings' })).toBeVisible()
  })

  test('disables approval actions without approver role', async ({ page }) => {
    await page.addInitScript((roles: string) => {
      window.localStorage.setItem('hotpass_mock_roles', roles)
    }, 'operator')
    await page.goto('/runs/run-001')
    await expect(page.getByRole('button', { name: 'Review & Approve' })).toBeDisabled()
  })
})
