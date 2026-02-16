import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi } from 'vitest'
import Layout from './Layout'

function renderLayout(path = '/', onLogout = vi.fn()) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Layout onLogout={onLogout} user={null}>
        <div data-testid="child-content">Page Content</div>
      </Layout>
    </MemoryRouter>
  )
}

describe('Layout', () => {
  it('renders navigation links', () => {
    renderLayout()
    expect(screen.getByText('Dashboard')).toBeInTheDocument()
    expect(screen.getByText('API Keys')).toBeInTheDocument()
    expect(screen.getByText('Models')).toBeInTheDocument()
    expect(screen.getByText('Budgets')).toBeInTheDocument()
    expect(screen.getByText('Settings')).toBeInTheDocument()
  })

  it('renders children content', () => {
    renderLayout()
    expect(screen.getByTestId('child-content')).toBeInTheDocument()
    expect(screen.getByText('Page Content')).toBeInTheDocument()
  })

  it('highlights the active nav link', () => {
    renderLayout('/models')
    const modelsLinks = screen.getAllByText('Models')
    // The sidebar nav link should have the active class
    const navLink = modelsLinks.find(el => el.closest('a'))
    expect(navLink?.closest('a')).toHaveClass('bg-primary-600')
  })

  it('shows breadcrumb for non-root pages', () => {
    renderLayout('/budgets')
    expect(screen.getByText('Home')).toBeInTheDocument()
    // "Budgets" appears in both sidebar nav and breadcrumb
    const budgetsElements = screen.getAllByText('Budgets')
    expect(budgetsElements.length).toBeGreaterThanOrEqual(2)
  })

  it('renders logout button', async () => {
    const onLogout = vi.fn()
    renderLayout('/', onLogout)
    const logoutButtons = screen.getAllByText('Logout')
    expect(logoutButtons.length).toBeGreaterThan(0)
    await userEvent.click(logoutButtons[0])
    expect(onLogout).toHaveBeenCalled()
  })
})
