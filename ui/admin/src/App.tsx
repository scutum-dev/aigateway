import { Routes, Route, Navigate } from 'react-router-dom'
import { useState, useEffect } from 'react'
import Layout from './components/Layout'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Models from './pages/Models'
import Budgets from './pages/Budgets'
import Teams from './pages/Teams'
import MCPServers from './pages/MCPServers'
import Workflows from './pages/Workflows'
import Settings from './pages/Settings'

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    const token = localStorage.getItem('admin_token')
    if (token) {
      // Verify token is still valid
      const expiresAt = localStorage.getItem('token_expires_at')
      if (expiresAt && new Date(expiresAt) > new Date()) {
        setIsAuthenticated(true)
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
  }

  const handleLogout = () => {
    localStorage.removeItem('admin_token')
    localStorage.removeItem('token_expires_at')
    setIsAuthenticated(false)
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
    <Layout onLogout={handleLogout}>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/models" element={<Models />} />
        <Route path="/budgets" element={<Budgets />} />
        <Route path="/teams" element={<Teams />} />
        <Route path="/mcp-servers" element={<MCPServers />} />
        <Route path="/workflows" element={<Workflows />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Layout>
  )
}

export default App
