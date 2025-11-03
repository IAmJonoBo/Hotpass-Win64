export interface InventoryAsset {
  id: string
  name: string
  type: string
  classification: string
  owner: string
  custodian: string
  location: string
  description: string
  dependencies: string[]
  controls: string[]
}

export interface InventorySummary {
  total: number
  byType: Record<string, number>
  byClassification: Record<string, number>
}

export interface InventoryRequirement {
  id: string
  surface: string
  description: string
  status: string
  detail: string | null
}

export interface InventorySnapshot {
  manifest: {
    version: string
    maintainer: string
    reviewCadence: string
  }
  summary: InventorySummary
  requirements: InventoryRequirement[]
  assets: InventoryAsset[]
  generatedAt: string
}
