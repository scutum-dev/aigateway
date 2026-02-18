import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import EmptyState from './EmptyState'

function MockIcon({ className }: { className?: string }) {
  return <svg data-testid="empty-icon" className={className} />
}

describe('EmptyState', () => {
  it('renders title and description', () => {
    render(
      <EmptyState icon={MockIcon} title="No items" description="There are no items yet." />
    )
    expect(screen.getByText('No items')).toBeInTheDocument()
    expect(screen.getByText('There are no items yet.')).toBeInTheDocument()
  })

  it('renders the icon component', () => {
    render(
      <EmptyState icon={MockIcon} title="No items" description="Nothing here." />
    )
    expect(screen.getByTestId('empty-icon')).toBeInTheDocument()
  })

  it('shows action button when actionLabel and onAction are provided', () => {
    const onAction = vi.fn()
    render(
      <EmptyState
        icon={MockIcon}
        title="No items"
        description="Nothing here."
        actionLabel="Create Item"
        onAction={onAction}
      />
    )
    expect(screen.getByRole('button', { name: 'Create Item' })).toBeInTheDocument()
  })

  it('does not show action button when actionLabel is not provided', () => {
    render(
      <EmptyState icon={MockIcon} title="No items" description="Nothing here." />
    )
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })

  it('does not show action button when onAction is not provided', () => {
    render(
      <EmptyState
        icon={MockIcon}
        title="No items"
        description="Nothing here."
        actionLabel="Create Item"
      />
    )
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })

  it('calls onAction when action button is clicked', async () => {
    const onAction = vi.fn()
    render(
      <EmptyState
        icon={MockIcon}
        title="No items"
        description="Nothing here."
        actionLabel="Create Item"
        onAction={onAction}
      />
    )
    await userEvent.click(screen.getByRole('button', { name: 'Create Item' }))
    expect(onAction).toHaveBeenCalledTimes(1)
  })
})
