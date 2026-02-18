import { useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'

export default function SSOComplete() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()

  useEffect(() => {
    const token = searchParams.get('token')
    const expiresAt = searchParams.get('expires_at')

    if (token) {
      localStorage.setItem('admin_token', token)
      if (expiresAt) {
        localStorage.setItem('token_expires_at', expiresAt)
      }
      // Redirect to dashboard after storing the token
      navigate('/', { replace: true })
    } else {
      // No token received, redirect to login
      navigate('/', { replace: true })
    }
  }, [searchParams, navigate])

  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-primary-600 mx-auto"></div>
        <p className="mt-4 text-gray-600">Completing SSO authentication...</p>
      </div>
    </div>
  )
}
