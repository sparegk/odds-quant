import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import App from './App'
import { ErrorBoundary } from './components/ErrorBoundary'
import { installGlobalErrorReporting } from './lib/observability'
import './styles.css'

const root = document.getElementById('root')
if (root === null) throw new Error('Root element is missing')
installGlobalErrorReporting()

createRoot(root).render(
  <StrictMode>
    <ErrorBoundary><App /></ErrorBoundary>
  </StrictMode>,
)
