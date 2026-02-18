import { useState, Fragment } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { Dialog, Transition } from '@headlessui/react'
import {
  HomeIcon,
  ServerIcon,
  CircleStackIcon,
  ShieldCheckIcon,
  Cog6ToothIcon,
  ArrowRightOnRectangleIcon,
  ChevronRightIcon,
  Bars3Icon,
  ChevronLeftIcon,
  CubeIcon,
  KeyIcon,
  UserGroupIcon,
  CurrencyDollarIcon,
  CpuChipIcon,
  BuildingOffice2Icon,
  ClipboardDocumentListIcon,
  DocumentTextIcon,
  ClockIcon,
  LockClosedIcon,
  BanknotesIcon,
  HeartIcon,
  BeakerIcon,
  BellAlertIcon,
  ArrowsRightLeftIcon,
} from '@heroicons/react/24/outline'
import { BoltIcon } from '@heroicons/react/24/solid'
import type { UserInfo } from '../types'

interface LayoutProps {
  children: React.ReactNode
  onLogout: () => void
  user: UserInfo | null
}

const navigation = [
  { name: 'Dashboard', href: '/', icon: HomeIcon },
  { name: 'Models', href: '/models', icon: CubeIcon },
  { name: 'API Keys', href: '/api-keys', icon: KeyIcon },
  { name: 'Teams', href: '/teams', icon: UserGroupIcon },
  { name: 'Budgets', href: '/budgets', icon: CurrencyDollarIcon },
  { name: 'Organizations', href: '/organizations', icon: BuildingOffice2Icon },
  { name: 'Audit Log', href: '/audit-log', icon: ClipboardDocumentListIcon },
  { name: 'Prompts', href: '/prompts', icon: DocumentTextIcon },
  { name: 'Rate Limits', href: '/rate-limits', icon: ClockIcon },
  { name: 'Model Access', href: '/model-access', icon: LockClosedIcon },
  { name: 'Chargeback', href: '/chargeback', icon: BanknotesIcon },
  { name: 'SLA Monitor', href: '/sla', icon: HeartIcon },
  { name: 'A/B Tests', href: '/ab-tests', icon: BeakerIcon },
  { name: 'Events', href: '/events', icon: BellAlertIcon },
  { name: 'Routing', href: '/routing', icon: ArrowsRightLeftIcon },
  { name: 'MCP Servers', href: '/mcp-servers', icon: ServerIcon },
  { name: 'A2A Agents', href: '/agents', icon: CpuChipIcon },
  { name: 'Guardrails', href: '/guardrails', icon: ShieldCheckIcon },
  { name: 'Workflows', href: '/workflows', icon: CircleStackIcon },
  { name: 'Settings', href: '/settings', icon: Cog6ToothIcon },
]

const routeLabels: Record<string, string> = {
  '/': 'Dashboard',
  '/models': 'Models',
  '/api-keys': 'API Keys',
  '/teams': 'Teams',
  '/budgets': 'Budgets',
  '/organizations': 'Organizations',
  '/audit-log': 'Audit Log',
  '/prompts': 'Prompts',
  '/rate-limits': 'Rate Limits',
  '/model-access': 'Model Access',
  '/chargeback': 'Chargeback',
  '/sla': 'SLA Monitor',
  '/ab-tests': 'A/B Tests',
  '/events': 'Events',
  '/routing': 'Routing',
  '/mcp-servers': 'MCP Servers',
  '/agents': 'A2A Agents',
  '/guardrails': 'Guardrails',
  '/workflows': 'Workflows',
  '/settings': 'Settings',
}

function SidebarContent({
  collapsed,
  onLogout,
}: {
  collapsed: boolean
  onLogout: () => void
}) {
  const location = useLocation()

  return (
    <>
      <div className={`p-4 border-b border-gray-800 ${collapsed ? 'flex justify-center' : ''}`}>
        {collapsed ? (
          <div className="w-8 h-8 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-lg flex items-center justify-center">
            <BoltIcon className="w-5 h-5 text-white" />
          </div>
        ) : (
          <>
            <h1 className="text-xl font-bold">AI Control Plane</h1>
            <p className="text-sm text-gray-400">Admin Console</p>
          </>
        )}
      </div>

      <nav aria-label="Main navigation" className="flex-1 p-4 space-y-1">
        {navigation.map((item) => {
          const isActive = location.pathname === item.href
          return (
            <Link
              key={item.name}
              to={item.href}
              title={collapsed ? item.name : undefined}
              className={`flex items-center ${collapsed ? 'justify-center' : ''} px-3 py-2 rounded-lg transition-colors ${
                isActive
                  ? 'bg-primary-600 text-white'
                  : 'text-gray-300 hover:bg-gray-800'
              }`}
            >
              <item.icon className={`w-5 h-5 ${collapsed ? '' : 'mr-3'}`} />
              {!collapsed && item.name}
            </Link>
          )
        })}
      </nav>

      <div className="p-4 border-t border-gray-800">
        <button
          onClick={onLogout}
          title={collapsed ? 'Logout' : undefined}
          className={`flex items-center ${collapsed ? 'justify-center' : ''} w-full px-3 py-2 text-gray-300 hover:bg-gray-800 rounded-lg transition-colors`}
        >
          <ArrowRightOnRectangleIcon className={`w-5 h-5 ${collapsed ? '' : 'mr-3'}`} />
          {!collapsed && 'Logout'}
        </button>
      </div>
    </>
  )
}

export default function Layout({ children, onLogout, user: _user }: LayoutProps) {
  const location = useLocation()
  const [collapsed, setCollapsed] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)

  const pageLabel = routeLabels[location.pathname] || 'Page'

  return (
    <div className="min-h-screen flex">
      {/* Mobile drawer */}
      <Transition show={mobileOpen} as={Fragment}>
        <Dialog onClose={() => setMobileOpen(false)} className="relative z-40 lg:hidden">
          <Transition
            as={Fragment}
            enter="ease-out duration-200"
            enterFrom="opacity-0"
            enterTo="opacity-100"
            leave="ease-in duration-150"
            leaveFrom="opacity-100"
            leaveTo="opacity-0"
          >
            <div className="fixed inset-0 bg-black/30" />
          </Transition>
          <div className="fixed inset-0 flex">
            <Transition
              as={Fragment}
              enter="ease-out duration-300"
              enterFrom="-translate-x-full"
              enterTo="translate-x-0"
              leave="ease-in duration-200"
              leaveFrom="translate-x-0"
              leaveTo="-translate-x-full"
            >
              <Dialog.Panel className="w-64 bg-gray-900 text-white flex flex-col" onClick={() => setMobileOpen(false)}>
                <SidebarContent collapsed={false} onLogout={onLogout} />
              </Dialog.Panel>
            </Transition>
          </div>
        </Dialog>
      </Transition>

      {/* Desktop sidebar */}
      <div
        className={`hidden lg:flex flex-col bg-gray-900 text-white transition-all duration-300 ${
          collapsed ? 'w-16' : 'w-64'
        }`}
      >
        <SidebarContent collapsed={collapsed} onLogout={onLogout} />
        <div className="p-2 border-t border-gray-800">
          <button
            onClick={() => setCollapsed(!collapsed)}
            className="w-full flex items-center justify-center p-2 text-gray-400 hover:text-white hover:bg-gray-800 rounded-lg transition-colors"
          >
            <ChevronLeftIcon className={`w-4 h-4 transition-transform duration-300 ${collapsed ? 'rotate-180' : ''}`} />
          </button>
        </div>
      </div>

      {/* Main content */}
      <div className="flex-1 overflow-auto flex flex-col">
        {/* Breadcrumbs bar */}
        <div className="bg-white border-b border-gray-200 px-4 lg:px-8 py-3 flex items-center gap-2">
          <button
            onClick={() => setMobileOpen(true)}
            className="lg:hidden p-1 text-gray-500 hover:text-gray-700"
            aria-label="Open navigation menu"
          >
            <Bars3Icon className="w-6 h-6" />
          </button>
          <Link to="/" className="text-gray-400 hover:text-gray-600 text-sm">
            Home
          </Link>
          {location.pathname !== '/' && (
            <>
              <ChevronRightIcon className="w-4 h-4 text-gray-300" />
              <span className="text-sm font-medium text-gray-700">{pageLabel}</span>
            </>
          )}
        </div>

        <main className="flex-1 p-4 lg:p-8">{children}</main>
      </div>
    </div>
  )
}
