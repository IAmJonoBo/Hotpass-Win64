import { useInventory } from '@/api/inventory'
import { InventoryOverview } from '@/components/governance/InventoryOverview'

export function Inventory() {
  const { data, isLoading, error, refetch } = useInventory()
  const message = error ? (error instanceof Error ? error.message : String(error)) : null

  return (
    <InventoryOverview
      snapshot={data ?? null}
      isLoading={isLoading && !data && !error}
      error={message}
      onRetry={() => refetch()}
    />
  )
}

export default Inventory
