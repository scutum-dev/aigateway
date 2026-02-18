import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import ErrorBoundary from './ErrorBoundary'

// A component that throws an error on render
function ThrowingChild({ message }: { message: string }) {
  throw new Error(message)
}

// Suppress console.error noise from React error boundary logging
beforeEach(() => {
  vi.spyOn(console, 'error').mockImplementation(() => {})
})

describe('ErrorBoundary', () => {
  it('renders children when no error occurs', () => {
    render(
      <ErrorBoundary>
        <div data-testid="child">Hello</div>
      </ErrorBoundary>
    )
    expect(screen.getByTestId('child')).toBeInTheDocument()
    expect(screen.getByText('Hello')).toBeInTheDocument()
  })

  it('shows error UI when a child throws', () => {
    render(
      <ErrorBoundary>
        <ThrowingChild message="Test explosion" />
      </ErrorBoundary>
    )
    expect(screen.queryByText('Hello')).not.toBeInTheDocument()
    expect(screen.getByText('Something went wrong')).toBeInTheDocument()
  })

  it('shows "Something went wrong" heading', () => {
    render(
      <ErrorBoundary>
        <ThrowingChild message="fail" />
      </ErrorBoundary>
    )
    const heading = screen.getByText('Something went wrong')
    expect(heading.tagName).toBe('H2')
  })

  it('shows a descriptive paragraph', () => {
    render(
      <ErrorBoundary>
        <ThrowingChild message="fail" />
      </ErrorBoundary>
    )
    expect(
      screen.getByText('An unexpected error occurred. Please try reloading the page.')
    ).toBeInTheDocument()
  })

  it('shows a Reload button', () => {
    render(
      <ErrorBoundary>
        <ThrowingChild message="fail" />
      </ErrorBoundary>
    )
    const button = screen.getByRole('button', { name: 'Reload' })
    expect(button).toBeInTheDocument()
  })

  it('shows error message in dev mode', () => {
    // import.meta.env.DEV is true in vitest by default
    render(
      <ErrorBoundary>
        <ThrowingChild message="Detailed error info" />
      </ErrorBoundary>
    )
    expect(screen.getByText('Detailed error info')).toBeInTheDocument()
  })

  it('renders the error message inside a pre element in dev mode', () => {
    render(
      <ErrorBoundary>
        <ThrowingChild message="pre-formatted error" />
      </ErrorBoundary>
    )
    const pre = screen.getByText('pre-formatted error')
    expect(pre.tagName).toBe('PRE')
  })
})
