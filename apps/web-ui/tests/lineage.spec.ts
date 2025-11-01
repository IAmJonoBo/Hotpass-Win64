import { test, expect } from '@playwright/test'

const namespacesPayload = { namespaces: [{ name: 'hotpass' }] }

const jobsPayload = {
  jobs: [
    {
      id: { namespace: 'hotpass', name: 'refine_pipeline' },
      name: 'refine_pipeline',
      namespace: 'hotpass',
      type: 'BATCH',
      latestRun: { state: 'COMPLETED', updatedAt: new Date().toISOString() },
    },
    {
      id: { namespace: 'hotpass', name: 'enrich_pipeline' },
      name: 'enrich_pipeline',
      namespace: 'hotpass',
      type: 'BATCH',
      latestRun: { state: 'FAILED', updatedAt: new Date().toISOString() },
    },
  ],
}

const datasetsPayload = {
  datasets: [
    {
      id: { namespace: 'hotpass', name: 'refined_aviation' },
      name: 'refined_aviation',
      namespace: 'hotpass',
      type: 'TABLE',
      sourceName: 'snowflake',
    },
    {
      id: { namespace: 'hotpass', name: 'enriched_aviation' },
      name: 'enriched_aviation',
      namespace: 'hotpass',
      type: 'TABLE',
      sourceName: 'snowflake',
    },
  ],
}

const baseGraph = {
  graph: {
    nodes: [
      {
        id: 'hotpass:refine_pipeline',
        type: 'JOB',
        data: {
          name: 'refine_pipeline',
          namespace: 'hotpass',
          type: 'BATCH',
        },
      },
      {
        id: 'hotpass:refined_aviation',
        type: 'DATASET',
        data: {
          name: 'refined_aviation',
          namespace: 'hotpass',
          type: 'TABLE',
          sourceName: 'snowflake',
        },
      },
      {
        id: 'hotpass:enrich_pipeline',
        type: 'JOB',
        data: {
          name: 'enrich_pipeline',
          namespace: 'hotpass',
          type: 'BATCH',
        },
      },
      {
        id: 'hotpass:enriched_aviation',
        type: 'DATASET',
        data: {
          name: 'enriched_aviation',
          namespace: 'hotpass',
          type: 'TABLE',
          sourceName: 'snowflake',
        },
      },
    ],
    edges: [
      { origin: 'hotpass:refine_pipeline', destination: 'hotpass:refined_aviation' },
      { origin: 'hotpass:refined_aviation', destination: 'hotpass:enrich_pipeline' },
      { origin: 'hotpass:enrich_pipeline', destination: 'hotpass:enriched_aviation' },
    ],
  },
  lastUpdatedAt: new Date().toISOString(),
}

const refreshedGraph = {
  graph: {
    ...baseGraph.graph,
    nodes: [
      ...baseGraph.graph.nodes,
      {
        id: 'hotpass:audited_aviation',
        type: 'DATASET',
        data: {
          name: 'audited_aviation',
          namespace: 'hotpass',
          type: 'TABLE',
          sourceName: 'snowflake',
        },
      },
    ],
    edges: [
      ...baseGraph.graph.edges,
      { origin: 'hotpass:enriched_aviation', destination: 'hotpass:audited_aviation' },
    ],
  },
  lastUpdatedAt: new Date().toISOString(),
}

test.describe('Lineage graph', () => {
  test.beforeEach(async ({ page }) => {
    await page.route('**/api/marquez/api/v1/namespaces**', async (route) => {
      await route.fulfill({ status: 200, body: JSON.stringify(namespacesPayload) })
    })
    await page.route('**/api/marquez/api/v1/namespaces/hotpass/jobs**', async (route) => {
      await route.fulfill({ status: 200, body: JSON.stringify(jobsPayload) })
    })
    await page.route('**/api/marquez/api/v1/namespaces/hotpass/datasets**', async (route) => {
      await route.fulfill({ status: 200, body: JSON.stringify(datasetsPayload) })
    })

    let lineageCallCount = 0
    await page.route('**/api/marquez/api/v1/lineage**', async (route) => {
      lineageCallCount += 1
      const body = lineageCallCount >= 3 ? refreshedGraph : baseGraph
      await route.fulfill({ status: 200, body: JSON.stringify(body) })
    })
  })

  test('renders React Flow graph and supports refresh', async ({ page }) => {
    await page.goto('/lineage')

    await expect(page.locator('.react-flow__node')).toHaveCount(4)
    await expect(page.getByText(/Live \(/)).toBeVisible()

    await page.getByRole('button', { name: 'Datasets' }).click()
    await page.getByRole('button', { name: 'refined_aviation' }).click()
    await expect(page.getByText('Selected Entity').locator('text=refined_aviation')).toBeVisible()

    await page.getByRole('button', { name: 'Jobs' }).click()
    await page.getByRole('button', { name: 'Refresh' }).click()

    await expect(page.locator('.react-flow__node')).toHaveCount(5)
    await expect(page.getByText('audited_aviation')).toBeVisible()
  })
})

