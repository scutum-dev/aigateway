import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import ConfirmDialog from './ConfirmDialog'

// Mock @headlessui/react to avoid Transition `show` prop issues in jsdom
vi.mock('@headlessui/react', () => {
  const Fragment = ({ children }: { children?: React.ReactNode }) => <>{children}</>
  return {
    Dialog: Object.assign(
      ({ children, onClose, className }: any) => (
        <div role="dialog" className={className} onClick={(e: any) => { if (e.target === e.currentTarget) onClose?.() }}>
          {children}
        </div>
      ),
      {
        Panel: ({ children, className }: any) => <div className={className}>{children}</div>,
        Title: ({ children, className }: any) => <h2 className={className}>{children}</h2>,
      }
    ),
    Transition: Object.assign(
      ({ show, children }: any) => (show !== false ? <>{children}</> : null),
      { Child: ({ children }: any) => <>{children}</> }
    ),
    Fragment,
  }
})

const defaultProps = {
  isOpen: true,
  onClose: vi.fn(),
  onConfirm: vi.fn(),
  title: 'Delete Item',
  message: 'Are you sure you want to delete this?',
}

describe('ConfirmDialog', () => {
  it('does not render dialog content when isOpen is false', () => {
    render(<ConfirmDialog {...defaultProps} isOpen={false} />)
    expect(screen.queryByText('Delete Item')).not.toBeInTheDocument()
    expect(screen.queryByText('Are you sure you want to delete this?')).not.toBeInTheDocument()
  })

  it('shows title and message when isOpen is true', () => {
    render(<ConfirmDialog {...defaultProps} />)
    expect(screen.getByText('Delete Item')).toBeInTheDocument()
    expect(screen.getByText('Are you sure you want to delete this?')).toBeInTheDocument()
  })

  it('shows default confirmLabel of "Confirm"', () => {
    render(<ConfirmDialog {...defaultProps} />)
    expect(screen.getByRole('button', { name: 'Confirm' })).toBeInTheDocument()
  })

  it('shows custom confirmLabel', () => {
    render(<ConfirmDialog {...defaultProps} confirmLabel="Yes, Delete" />)
    expect(screen.getByRole('button', { name: 'Yes, Delete' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Confirm' })).not.toBeInTheDocument()
  })

  it('calls onConfirm and onClose when confirm button is clicked', async () => {
    const onConfirm = vi.fn()
    const onClose = vi.fn()
    render(<ConfirmDialog {...defaultProps} onConfirm={onConfirm} onClose={onClose} />)

    await userEvent.click(screen.getByRole('button', { name: 'Confirm' }))
    expect(onConfirm).toHaveBeenCalledTimes(1)
    expect(onClose).toHaveBeenCalled()
  })

  it('calls onClose when cancel button is clicked', async () => {
    const onClose = vi.fn()
    render(<ConfirmDialog {...defaultProps} onClose={onClose} />)

    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('renders Cancel button', () => {
    render(<ConfirmDialog {...defaultProps} />)
    expect(screen.getByRole('button', { name: 'Cancel' })).toBeInTheDocument()
  })
})
