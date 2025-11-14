# Hotpass Web UI Test Plan

## Overview

This document outlines the testing strategy for the Hotpass Web UI, a modern React-based dashboard for monitoring data pipeline runs and exploring lineage.

## Test Environment Setup

### Prerequisites

1. Node.js 24+ with Corepack (pnpm 9+) installed
2. Marquez backend running (optional - mock data available)
3. Prefect API running (optional - mock data available)

### Setup Steps

```bash
cd apps/web-ui
corepack enable pnpm
pnpm install
pnpm run dev
```

## Unit Testing

### Component Tests

Test individual React components in isolation:

**Card Component**

- ✅ Renders with title and content
- ✅ Supports different variants (default, ghost)
- ✅ Properly displays header, content, and footer sections

**Button Component**

- ✅ Renders with correct text
- ✅ Supports all variants (default, destructive, outline, secondary, ghost, link)
- ✅ Handles click events
- ✅ Disabled state works correctly
- ✅ Supports different sizes (sm, default, lg, icon)

**Badge Component**

- ✅ Renders with text
- ✅ Supports all variants (default, secondary, destructive, outline)
- ✅ Custom colors work correctly

**Sidebar Component**

- ✅ Displays navigation links
- ✅ Shows environment badge with correct color
- ✅ Dark/light mode toggle works
- ✅ Active route is highlighted

## Integration Testing

### Dashboard Page

**Test Case 1: Empty State**

- Navigate to `/`
- Verify "No runs in the last 24 hours" message displays
- Verify all summary cards show 0

**Test Case 2: With Mock Data**

- Start dev server with Prefect unavailable
- Verify mock data loads (3 runs)
- Verify summary cards show correct counts
- Verify table displays run information
- Click on a run link - verify navigation to details page

**Test Case 3: API Integration**

- Start Marquez backend (port 5000)
- Start Prefect API (port 4200)
- Refresh page
- Verify real data loads from APIs
- Verify status colors match run states

**Test Case 4: Skeleton + Failure Banner**

- Simulate Prefect API outage
- Verify a red API banner appears with fallback badge
- Confirm skeleton loaders display in summary cards and tables during initial load

**Test Case 5: Lineage Telemetry Card**

- With Marquez jobs available, ensure the telemetry card shows jobs today / failures / incomplete facets
- Confirm the card refresh indicator toggles when new data polls in

### Lineage Page

**Test Case 1: Namespace Filtering**

- Navigate to `/lineage`
- Click different namespace buttons
- Verify jobs list updates

**Test Case 2: Search Functionality**

- Enter job name in search box
- Verify filtered results display
- Clear search - verify all jobs return

**Test Case 3: Mock Data Display**

- With Marquez unavailable
- Verify 2 mock jobs display (refine_pipeline, enrich_pipeline)
- Verify job details are correct
- Click "View Lineage" button

**Test Case 4: Dataset Display**

- Verify datasets section shows when available
- Verify dataset details display correctly

**Test Case 5: React Flow Graph Rendering**

- With Marquez returning lineage data, confirm the graph renders via React Flow (nodes + edges visible)
- Verify the live badge reflects the active mode (`Live (WebSocket)` or `Live (Polling)`)
- Clicking a node pivots the selected entity panel

**Test Case 6: Manual Refresh & Auto-Fallback**

- Click the `Refresh` button on the lineage graph
- When the API returns updated edges, confirm the node count updates without a full page reload
- If WebSocket/SSE is unavailable, confirm polling fallback keeps the badge in `Live (Polling)`

### Run Details Page

**Test Case 1: Valid Run**

- Navigate to `/runs/run-001`
- Verify run name and ID display
- Verify status badge shows correct state
- Verify summary cards show duration, flow ID, tags
- Verify QA results table displays
- Verify run parameters JSON displays
- Verify raw event data displays

**Test Case 2: Invalid Run**

- Navigate to `/runs/nonexistent`
- Verify "Run not found" message
- Verify "Back to Dashboard" button works

**Test Case 3: QA Results**

- On valid run details page
- Verify all QA checks display with icons
- Verify passed checks show green
- Verify warning checks show yellow
- Verify failed checks show red

**Test Case 4: API Failure Fallback Banner**

- Force Prefect flow run endpoint to return 500
- Verify the error banner appears with fallback badge and mock data continues to render

**Test Case 5: Skeleton Loader**

- Hard-refresh the page
- Confirm skeleton placeholders show for header, summary cards, tables, and JSON blocks until data arrives

### Admin Page

**Test Case 1: Configuration Display**

- Navigate to `/admin`
- Verify environment selector shows (local, staging, prod)
- Verify Prefect API URL field populated
- Verify Marquez API URL field populated

**Test Case 2: Save Settings**

- Change Prefect API URL
- Click "Save Changes"
- Verify "Saved!" confirmation appears
- Refresh page - verify setting persisted

**Test Case 3: Test Connection**

- Click "Test Connection" for Prefect
- With API running: verify green "Connected" badge
- With API down: verify red "Failed" badge
- Repeat for Marquez API

**Test Case 4: Reset to Defaults**

- Modify all settings
- Click "Reset to Defaults"
- Verify all fields reset to default values
- Verify localStorage cleared

## User Experience Testing

### Navigation

- ✅ Sidebar navigation works on all pages
- ✅ Active route is highlighted
- ✅ Logo is visible and branding consistent

### Dark/Light Mode

- ✅ Toggle switches between modes
- ✅ Preference persists across page refreshes
- ✅ All components render correctly in both modes
- ✅ Color contrast meets accessibility standards

### Responsive Design

- Test at 1920px (desktop)
- Test at 1366px (laptop)
- Test at 1024px (min supported)
- Verify layout doesn't break
- Verify text remains readable

### Performance

- Initial page load < 3 seconds
- Navigation between pages instant
- API requests show loading states
- No memory leaks during extended use

## API Integration Testing

### Prefect API

**Test Case 1: Successful Connection**

- Start Prefect at localhost:4200
- Verify flows load
- Verify flow runs load with correct data
- Verify filtering works

**Test Case 2: Connection Failure**

- Stop Prefect API
- Verify graceful fallback to mock data
- Verify error doesn't crash app
- Verify console shows connection error

### Marquez API

**Test Case 1: Successful Connection**

- Start Marquez at localhost:5000
- Verify namespaces load
- Verify jobs load
- Verify datasets load
- Verify lineage requests work

**Test Case 2: Connection Failure**

- Stop Marquez API
- Verify graceful fallback to mock data
- Verify error doesn't crash app

## Accessibility Testing

### Keyboard Navigation

- ✅ Tab through all interactive elements
- ✅ Enter activates buttons and links
- ✅ Escape closes modals/dropdowns
- ✅ Arrow keys work in form fields

### Screen Reader Support

- ✅ All images have alt text
- ✅ Form fields have labels
- ✅ Semantic HTML elements used
- ✅ ARIA labels where needed

### Color Contrast

- ✅ Text meets WCAG AA standards (4.5:1)
- ✅ Large text meets AA standards (3:1)
- ✅ Interactive elements distinguishable

## Browser Compatibility

### Supported Browsers

- ✅ Chrome 100+
- ✅ Firefox 100+
- ✅ Safari 15+
- ✅ Edge 100+

### Test Each Browser

- Dashboard loads correctly
- Lineage visualization works
- Forms submit properly
- Dark mode toggle works
- API integration functions

## Security Testing

### XSS Prevention

- Verify user input sanitized
- Verify JSON data properly escaped
- Verify no inline scripts executed

### CSRF Protection

- API requests use proper CORS
- No sensitive data in URLs
- localStorage access secured

### Data Validation

- Verify API URL validation
- Verify form input validation
- Verify error messages don't leak info

## Regression Testing

After each update, verify:

1. All existing features still work
2. No new console errors
3. Build completes successfully
4. Storybook stories render
5. TypeScript compilation passes

## Manual Exploratory Testing

### Scenario 1: New Operator Onboarding

1. Open app for first time
2. Navigate through all pages
3. Configure APIs in Admin
4. Test connection to backends
5. View pipeline runs
6. Explore lineage

### Scenario 2: Monitoring Active Pipeline

1. Run hotpass refine command
2. Check dashboard for new run
3. View run details
4. Check QA results
5. Explore lineage for the run

### Scenario 3: Troubleshooting Failed Run

1. Identify failed run in dashboard
2. Click to view details
3. Review QA failures
4. Check error messages
5. Navigate to lineage to see upstream

## Playwright Automation

- `dashboard.spec.ts` – baseline smoke for dashboard rendering
- `lineage.spec.ts` – verifies React Flow graph rendering, selection, and live refresh badge/state
- `failure-ux.spec.ts` – asserts Prefect outage surfaces API banner and fallback data stays readable

## Storybook Testing

### Component Stories

- View all component stories at localhost:6006
- Test all variants of each component
- Verify props control panel works
- Test interactions in each story

**Card Stories**

- ✅ Default card
- ✅ With stats
- ✅ Ghost variant

**ApiBanner Stories**

- ✅ Error variant with fallback badge
- ✅ Warning + info variants render copy and colors correctly
- ✅ Success state displays confirmation messaging

**Skeleton Stories**

- ✅ Basic skeleton renders with rounded-2xl styling
- ✅ Card preview demonstrates stacked skeleton blocks

**Button Stories**

- ✅ All variants
- ✅ All sizes
- ✅ With icons
- ✅ Loading state

**Badge Stories**

- ✅ All variants
- ✅ Status badges
- ✅ Environment badges

## Performance Benchmarks

### Metrics

- First Contentful Paint: < 1.5s
- Time to Interactive: < 3s
- Largest Contentful Paint: < 2.5s
- Cumulative Layout Shift: < 0.1
- Total Blocking Time: < 300ms

### Bundle Size

- Main bundle: < 300kb (gzipped)
- CSS bundle: < 20kb (gzipped)
- Lazy loaded chunks: < 100kb each

## Test Data

### Mock Flow Runs

```json
[
  {
    "id": "run-001",
    "name": "hotpass-refine-20240115-120000",
    "state_type": "COMPLETED",
    "total_run_time": 1800,
    "tags": ["aviation"]
  },
  {
    "id": "run-002",
    "name": "hotpass-enrich-20240115-130000",
    "state_type": "COMPLETED",
    "total_run_time": 2700
  },
  {
    "id": "run-003",
    "name": "hotpass-refine-20240115-140000",
    "state_type": "RUNNING",
    "tags": ["generic"]
  }
]
```

### Mock Marquez Jobs

```json
[
  {
    "namespace": "hotpass",
    "name": "refine_pipeline",
    "type": "BATCH"
  },
  {
    "namespace": "hotpass",
    "name": "enrich_pipeline",
    "type": "BATCH"
  }
]
```

## Deployment Testing

### Production Build

```bash
pnpm run build
```

- ✅ Build completes without errors
- ✅ No TypeScript errors
- ✅ Bundle size acceptable
- ✅ Source maps generated

### Preview Build

```bash
pnpm run preview
```

- ✅ Production build works locally
- ✅ All routes accessible
- ✅ Assets load correctly

## Continuous Integration

### Pre-commit Checks

- ✅ ESLint passes
- ✅ TypeScript compilation succeeds
- ✅ Build completes

### CI Pipeline

1. Install dependencies
2. Run linter
3. Build for production
4. Build Storybook

## Known Issues / Limitations

1. **Mock Data Dependency**: When APIs are unavailable, app falls back to mock data. This is intentional for demo purposes.

2. **Lineage Visualization**: Currently uses table view. Future enhancement would add interactive graph visualization with react-flow or d3.

3. **Live Updates**: Lineage subscriptions fall back to polling when the `/lineage/stream` endpoint is unavailable. Verify the badge reflects the active mode.

4. **Authentication**: No authentication implemented. Intended for internal/VPN-only deployment.

## Success Criteria

✅ All pages render without errors
✅ Dark/light mode works correctly
✅ Navigation functions properly
✅ API integration with fallback to mock data
✅ Responsive layout (1024px+)
✅ TypeScript compilation passes
✅ Production build succeeds
✅ Storybook stories render
✅ Screenshots demonstrate UX quality

## Future Testing Considerations

- Add E2E tests with Playwright
- Add unit tests with Vitest/React Testing Library
- Add visual regression tests
- Add API integration tests
- Add performance monitoring
- Add error tracking (Sentry)
