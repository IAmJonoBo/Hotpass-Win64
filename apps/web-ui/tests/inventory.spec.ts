import { test, expect } from '@playwright/test'

const inventoryFixture = {
  manifest: { version: '2025-10-26', maintainer: 'Security & Platform', reviewCadence: 'quarterly' },
  summary: { total: 7, byType: { filesystem: 3, secret: 2, database: 2 }, byClassification: { confidential: 4, sensitive: 2, internal: 1 } },
  requirements: [
    { id: 'backend-service', surface: 'backend', description: 'Inventory manifest loader, validator, and cache', status: 'implemented', detail: null },
    { id: 'frontend', surface: 'frontend', description: 'Governance inventory view renders asset register', status: 'implemented', detail: null },
  ],
  assets: [
    {
      id: 'raw-data-store',
      name: 'Raw ingestion datasets',
      type: 'filesystem',
      classification: 'sensitive_pii',
      owner: 'Data Governance',
      custodian: 'Platform Engineering',
      location: './data',
      description: 'Source spreadsheets uploaded by operators before refinement.',
      dependencies: ['Prefect refinement flow'],
      controls: ['Archive encryption planned via Vault-managed keys'],
    },
  ],
  generatedAt: '2025-11-01T00:00:00Z',
}

test.describe('Governance inventory', () => {
  test.beforeEach(async ({ page }) => {
    await page.route('**/api/inventory', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(inventoryFixture),
      })
    })
  })

  test('renders snapshot summary and table data', async ({ page }) => {
    await page.goto('/governance/inventory')
    await expect(page.getByRole('heading', { name: 'Asset inventory' })).toBeVisible()
    await expect(page.getByText('Total assets')).toBeVisible()
    await expect(page.getByText('Raw ingestion datasets')).toBeVisible()
    await expect(page.getByText('Inventory manifest loader, validator, and cache')).toBeVisible()
  })
})
