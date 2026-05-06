import { useEffect, useState } from 'react'
import { authApi } from '../api/client'
import { BoltIcon } from '@heroicons/react/24/solid'

interface LoginProps {
  onLogin: (token: string, expiresAt: string) => void
}

export default function Login({ onLogin }: LoginProps) {
  const [apiKey, setApiKey] = useState('')
  const [error, setError] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  // True while we're auto-exchanging a magic-link bootstrap token from the
  // URL. Renders a "Logging you in…" overlay so the user doesn't briefly
  // see a credentials form they don't need.
  const [isBootstrapping, setIsBootstrapping] = useState(false)

  // On mount, check for a magic-link bootstrap token in the URL. The
  // trial-provisioner injects BOOTSTRAP_TOKEN into the trial Fly machine's
  // env and redirects the user to /admin/?bootstrap=<token>. We exchange
  // that for a JWT here and drop straight into the dashboard. On any
  // failure (already consumed, expired, server down) we fall through to
  // the normal API-key login form with a friendly banner.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const bootstrapToken = params.get('bootstrap')
    if (!bootstrapToken) return

    setIsBootstrapping(true)
    // Strip the token from the URL immediately so a refresh doesn't retry
    // (it's one-shot — the second attempt always fails) and so the token
    // doesn't sit in browser history / referrer headers for screen-shares.
    params.delete('bootstrap')
    const newSearch = params.toString()
    window.history.replaceState(
      {},
      '',
      window.location.pathname + (newSearch ? `?${newSearch}` : '') + window.location.hash,
    )

    authApi
      .bootstrap(bootstrapToken)
      .then((response) => {
        onLogin(response.access_token, response.expires_at)
      })
      .catch((err: unknown) => {
        const axiosErr = err as { response?: { data?: { detail?: string } } }
        setError(
          axiosErr.response?.data?.detail ||
            'Trial activation link expired or already used. Log in with your API key from the welcome email.',
        )
      })
      .finally(() => {
        setIsBootstrapping(false)
      })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setIsLoading(true)

    try {
      const response = await authApi.login(apiKey)
      onLogin(response.access_token, response.expires_at)
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } }
      setError(axiosErr.response?.data?.detail || 'Login failed')
    } finally {
      setIsLoading(false)
    }
  }

  if (isBootstrapping) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-gray-900 via-gray-900 to-indigo-900">
        <div className="text-center text-white">
          <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-white mx-auto"></div>
          <p className="mt-4">Logging you in…</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-gray-900 via-gray-900 to-indigo-900 relative overflow-hidden">
      {/* Decorative blobs */}
      <div className="absolute top-1/4 -left-32 w-96 h-96 bg-indigo-500/10 rounded-full blur-3xl" />
      <div className="absolute bottom-1/4 -right-32 w-96 h-96 bg-purple-500/10 rounded-full blur-3xl" />

      <div className="relative z-10 max-w-md w-full mx-4">
        <div className="bg-white rounded-2xl shadow-2xl p-8">
          <div className="text-center mb-8">
            <div className="inline-flex items-center justify-center w-14 h-14 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-xl mb-4">
              <BoltIcon className="w-8 h-8 text-white" />
            </div>
            <h1 className="text-2xl font-bold text-gray-900">Scutum</h1>
            <p className="text-gray-500 mt-1">Admin Console</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <label htmlFor="apiKey" className="label">
                API Key
              </label>
              <input
                id="apiKey"
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                className="input"
                placeholder="sk-litellm-..."
                required
              />
              <p className="mt-1 text-sm text-gray-500">
                Use your LiteLLM master key or an admin API key
              </p>
            </div>

            {error && (
              <div className="bg-red-50 text-red-700 p-3 rounded-lg text-sm">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={isLoading}
              className="w-full py-2.5 px-4 rounded-lg font-medium text-white bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 disabled:opacity-50 transition-all shadow-lg shadow-indigo-500/25"
            >
              {isLoading ? 'Signing in...' : 'Sign In'}
            </button>
          </form>
        </div>

        <p className="text-center text-gray-500 text-sm mt-6">
          Powered by Scutum Platform
        </p>
      </div>
    </div>
  )
}
