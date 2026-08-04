import { Component, type ReactNode } from 'react'

import { reportFrontendError } from '../lib/observability'

export class ErrorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false }

  static getDerivedStateFromError() {
    return { failed: true }
  }

  componentDidCatch(error: Error) {
    reportFrontendError(error)
  }

  render() {
    if (this.state.failed) return <main className="grid min-h-screen min-w-[1180px] place-items-center bg-zinc-50"><section className="border border-rose-200 bg-white p-8 text-center"><p className="text-xs font-bold uppercase text-rose-700">Desktop application error</p><h1 className="mt-2 text-xl font-bold">The research workspace could not render</h1><p className="mt-2 text-sm text-zinc-600">Reload the page. A privacy-safe error type and route were reported without notes, keys, cookies, or request content.</p></section></main>
    return this.props.children
  }
}
