export function SkeletonLine({ className = '' }: { className?: string }) {
  return <div className={`animate-pulse bg-gray-200 rounded h-4 ${className}`} />
}

export function SkeletonCard() {
  return (
    <div className="card space-y-4">
      <div className="flex justify-between">
        <SkeletonLine className="w-1/3 h-5" />
        <SkeletonLine className="w-16 h-5" />
      </div>
      <SkeletonLine className="w-full" />
      <SkeletonLine className="w-2/3" />
      <SkeletonLine className="w-1/2" />
    </div>
  )
}

export function SkeletonTable({ rows = 5, cols = 5 }: { rows?: number; cols?: number }) {
  return (
    <div className="card overflow-hidden">
      <div className="bg-gray-50 px-6 py-3 flex gap-6">
        {Array.from({ length: cols }).map((_, i) => (
          <SkeletonLine key={i} className="flex-1 h-3" />
        ))}
      </div>
      <div className="divide-y divide-gray-200">
        {Array.from({ length: rows }).map((_, r) => (
          <div key={r} className="px-6 py-4 flex gap-6">
            {Array.from({ length: cols }).map((_, c) => (
              <SkeletonLine key={c} className="flex-1" />
            ))}
          </div>
        ))}
      </div>
    </div>
  )
}

export function SkeletonStatCard() {
  return (
    <div className="card flex items-center">
      <div className="animate-pulse bg-gray-200 rounded-lg w-12 h-12" />
      <div className="ml-4 space-y-2 flex-1">
        <SkeletonLine className="w-20 h-3" />
        <SkeletonLine className="w-16 h-6" />
      </div>
    </div>
  )
}
