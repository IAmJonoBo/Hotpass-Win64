import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Layout } from './components/Layout'
import { Dashboard } from './pages/Dashboard'
import { Lineage } from './pages/Lineage'
import { RunDetails } from './pages/RunDetails'
import { Admin } from './pages/Admin'
import { Health } from './pages/Health'
import { Assistant } from './pages/Assistant'
import { AuthProvider, RequireRole } from './auth'
import { AuthCallback } from './pages/AuthCallback'
import './index.css'

// Create a client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 30000, // 30 seconds
    },
  },
})

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/auth/callback" element={<AuthCallback />} />
            <Route element={<Layout />}>
              <Route path="/" element={<Dashboard />} />
              <Route path="/lineage" element={<Lineage />} />
              <Route path="/assistant" element={<Assistant />} />
              <Route path="/health" element={<Health />} />
              <Route
                path="/runs/:runId"
                element={(
                  <RequireRole roles={['operator', 'approver', 'admin']}>
                    <RunDetails />
                  </RequireRole>
                )}
              />
              <Route
                path="/admin"
                element={(
                  <RequireRole roles={['admin']}>
                    <Admin />
                  </RequireRole>
                )}
              />
            </Route>
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  )
}

export default App
