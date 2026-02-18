import { Routes, Route, Navigate } from 'react-router-dom'
import { useState, useEffect } from 'react'
import { authApi } from './api/client'
import type { UserInfo } from './types'
import Layout from './components/Layout'
import ErrorBoundary from './components/ErrorBoundary'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Models from './pages/Models'
import APIKeys from './pages/APIKeys'
import Teams from './pages/Teams'
import Budgets from './pages/Budgets'
import MCPServers from './pages/MCPServers'
import Agents from './pages/Agents'
import Guardrails from './pages/Guardrails'
import Workflows from './pages/Workflows'
import Settings from './pages/Settings'
import Organizations from './pages/Organizations'
import OrganizationDetail from './pages/OrganizationDetail'
import AuditLog from './pages/AuditLog'
import Prompts from './pages/Prompts'
import RateLimits from './pages/RateLimits'
import ModelAccess from './pages/ModelAccess'
import Chargeback from './pages/Chargeback'
import SLAMonitoring from './pages/SLAMonitoring'
import ABTests from './pages/ABTests'
import Events from './pages/Events'
import RoutingPolicies from './pages/RoutingPolicies'
import SSOComplete from './pages/SSOComplete'

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [user, setUser] = useState<UserInfo | null>(null)

  useEffect(() => {
    const token = localStorage.getItem('admin_token')
    if (token) {
      const expiresAt = localStorage.getItem('token_expires_at')
      if (expiresAt && new Date(expiresAt) > new Date()) {
        setIsAuthenticated(true)
        authApi.me().then(setUser).catch(() => {})
      } else {
        localStorage.removeItem('admin_token')
        localStorage.removeItem('token_expires_at')
      }
    }
    setIsLoading(false)
  }, [])

  const handleLogin = (token: string, expiresAt: string) => {
    localStorage.setItem('admin_token', token)
    localStorage.setItem('token_expires_at', expiresAt)
    setIsAuthenticated(true)
    authApi.me().then(setUser).catch(() => {})
  }

  const handleLogout = () => {
    localStorage.removeItem('admin_token')
    localStorage.removeItem('token_expires_at')
    setIsAuthenticated(false)
    setUser(null)
  }

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-primary-600"></div>
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Login onLogin={handleLogin} />
  }

  return (
    <Layout onLogout={handleLogout} user={user}>
      <ErrorBoundary>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/models" element={<Models />} />
        <Route path="/api-keys" element={<APIKeys />} />
        <Route path="/teams" element={<Teams />} />
        <Route path="/budgets" element={<Budgets />} />
        <Route path="/mcp-servers" element={<MCPServers />} />
        <Route path="/agents" element={<Agents />} />
        <Route path="/guardrails" element={<Guardrails />} />
        <Route path="/workflows" element={<Workflows />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="/organizations" element={<Organizations />} />
        <Route path="/organizations/:orgId" element={<OrganizationDetail />} />
        <Route path="/audit-log" element={<AuditLog />} />
        <Route path="/prompts" element={<Prompts />} />
        <Route path="/rate-limits" element={<RateLimits />} />
        <Route path="/model-access" element={<ModelAccess />} />
        <Route path="/chargeback" element={<Chargeback />} />
        <Route path="/sla" element={<SLAMonitoring />} />
        <Route path="/ab-tests" element={<ABTests />} />
        <Route path="/events" element={<Events />} />
        <Route path="/routing" element={<RoutingPolicies />} />
        <Route path="/auth/sso/complete" element={<SSOComplete />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      </ErrorBoundary>
    </Layout>
  )
}

export default App
