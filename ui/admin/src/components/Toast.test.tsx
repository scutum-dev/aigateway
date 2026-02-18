import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import { ToastProvider, useToast } from './Toast'

// Helper component that triggers a toast via a button
function ToastTrigger({ type, message }: { type: 'success' | 'error' | 'info' | 'warning'; message: string }) {
  const toast = useToast()
  return (
    <button onClick={() => toast(type, message)}>
      Show Toast
    </button>
  )
}

// Helper component that just reads the hook
function HookReader() {
  const toast = useToast()
  return <span data-testid="hook-result">{typeof toast}</span>
}

describe('ToastProvider', () => {
  it('renders children', () => {
    render(
      <ToastProvider>
        <div data-testid="child">Content</div>
      </ToastProvider>
    )
    expect(screen.getByTestId('child')).toBeInTheDocument()
    expect(screen.getByText('Content')).toBeInTheDocument()
  })
})

describe('useToast', () => {
  it('throws when used outside ToastProvider', () => {
    // Suppress console.error from React for the expected error
    vi.spyOn(console, 'error').mockImplementation(() => {})
    expect(() => render(<HookReader />)).toThrow(
      'useToast must be used within ToastProvider'
    )
  })

  it('returns a function', () => {
    render(
      <ToastProvider>
        <HookReader />
      </ToastProvider>
    )
    expect(screen.getByTestId('hook-result')).toHaveTextContent('function')
  })
})

describe('Toast messages', () => {
  it('shows a success toast message', async () => {
    render(
      <ToastProvider>
        <ToastTrigger type="success" message="Item created successfully" />
      </ToastProvider>
    )
    await userEvent.click(screen.getByText('Show Toast'))
    await waitFor(() => {
      expect(screen.getByText('Item created successfully')).toBeInTheDocument()
    })
  })

  it('shows an error toast message', async () => {
    render(
      <ToastProvider>
        <ToastTrigger type="error" message="Something failed" />
      </ToastProvider>
    )
    await userEvent.click(screen.getByText('Show Toast'))
    await waitFor(() => {
      expect(screen.getByText('Something failed')).toBeInTheDocument()
    })
  })

  it('shows a dismiss button with accessible label', async () => {
    render(
      <ToastProvider>
        <ToastTrigger type="info" message="Info message" />
      </ToastProvider>
    )
    await userEvent.click(screen.getByText('Show Toast'))
    await waitFor(() => {
      expect(screen.getByLabelText('Dismiss notification')).toBeInTheDocument()
    })
  })

  it('removes toast when dismiss button is clicked', async () => {
    render(
      <ToastProvider>
        <ToastTrigger type="warning" message="Warning message" />
      </ToastProvider>
    )
    await userEvent.click(screen.getByText('Show Toast'))
    await waitFor(() => {
      expect(screen.getByText('Warning message')).toBeInTheDocument()
    })

    await userEvent.click(screen.getByLabelText('Dismiss notification'))
    await waitFor(() => {
      expect(screen.queryByText('Warning message')).not.toBeInTheDocument()
    })
  })

  it('renders the toast container with aria-live polite', () => {
    render(
      <ToastProvider>
        <div>child</div>
      </ToastProvider>
    )
    const container = screen.getByRole('status')
    expect(container).toHaveAttribute('aria-live', 'polite')
  })
})
