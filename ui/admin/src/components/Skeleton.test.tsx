import { render } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { SkeletonLine, SkeletonCard, SkeletonTable, SkeletonStatCard } from './Skeleton'

describe('SkeletonLine', () => {
  it('renders with animate-pulse class', () => {
    const { container } = render(<SkeletonLine />)
    const el = container.firstElementChild!
    expect(el.className).toContain('animate-pulse')
  })

  it('renders with bg-gray-200 and rounded classes', () => {
    const { container } = render(<SkeletonLine />)
    const el = container.firstElementChild!
    expect(el.className).toContain('bg-gray-200')
    expect(el.className).toContain('rounded')
  })

  it('accepts and applies a custom className', () => {
    const { container } = render(<SkeletonLine className="w-1/3 h-5" />)
    const el = container.firstElementChild!
    expect(el.className).toContain('w-1/3')
    expect(el.className).toContain('h-5')
    // Still has base classes
    expect(el.className).toContain('animate-pulse')
  })
})

describe('SkeletonCard', () => {
  it('renders multiple skeleton lines', () => {
    const { container } = render(<SkeletonCard />)
    const pulseElements = container.querySelectorAll('.animate-pulse')
    // SkeletonCard has 5 SkeletonLine instances
    expect(pulseElements.length).toBe(5)
  })

  it('renders within a card container', () => {
    const { container } = render(<SkeletonCard />)
    const card = container.firstElementChild!
    expect(card.className).toContain('card')
  })
})

describe('SkeletonTable', () => {
  it('renders correct number of rows and columns', () => {
    const { container } = render(<SkeletonTable rows={3} cols={4} />)
    // Header row: 4 skeleton lines
    const headerRow = container.querySelector('.bg-gray-50')!
    const headerLines = headerRow.querySelectorAll('.animate-pulse')
    expect(headerLines.length).toBe(4)

    // Body rows: 3 rows x 4 cols = 12 skeleton lines
    const bodyRows = container.querySelectorAll('.divide-y > div')
    expect(bodyRows.length).toBe(3)
    bodyRows.forEach((row) => {
      const lines = row.querySelectorAll('.animate-pulse')
      expect(lines.length).toBe(4)
    })
  })

  it('uses default 5 rows and 5 cols when no props given', () => {
    const { container } = render(<SkeletonTable />)
    // Header: 5 skeleton lines
    const headerRow = container.querySelector('.bg-gray-50')!
    expect(headerRow.querySelectorAll('.animate-pulse').length).toBe(5)

    // Body: 5 rows
    const bodyRows = container.querySelectorAll('.divide-y > div')
    expect(bodyRows.length).toBe(5)
    // Each row has 5 cols
    bodyRows.forEach((row) => {
      expect(row.querySelectorAll('.animate-pulse').length).toBe(5)
    })
  })
})

describe('SkeletonStatCard', () => {
  it('renders with animate-pulse elements', () => {
    const { container } = render(<SkeletonStatCard />)
    const pulseElements = container.querySelectorAll('.animate-pulse')
    // 1 large square + 2 SkeletonLines = 3 animate-pulse elements
    expect(pulseElements.length).toBe(3)
  })

  it('renders a card container', () => {
    const { container } = render(<SkeletonStatCard />)
    expect(container.firstElementChild!.className).toContain('card')
  })
})
