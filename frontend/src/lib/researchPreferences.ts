import { useCallback, useEffect, useState } from 'react'

const storagePrefix = 'oddsquant:preference:'

export function useResearchPreference(key: string, fallback: string, validate: (value: string) => boolean = () => true): [string, (value: string) => void] {
  const read = useCallback(() => readPreference(key, fallback, validate), [fallback, key, validate])
  const [value, setValue] = useState(read)
  useEffect(() => {
    const synchronize = () => setValue(read())
    window.addEventListener('popstate', synchronize)
    return () => window.removeEventListener('popstate', synchronize)
  }, [read])
  const update = useCallback((next: string) => {
    if (!validate(next)) return
    setValue(next)
    try { window.localStorage.setItem(`${storagePrefix}${key}`, next) } catch { /* storage is optional */ }
    const url = new URL(window.location.href)
    if (next === fallback) url.searchParams.delete(key)
    else url.searchParams.set(key, next)
    window.history.replaceState(null, '', `${url.pathname}${url.search}${url.hash}`)
  }, [fallback, key, validate])
  return [value, update]
}

export function readPreference(key: string, fallback: string, validate: (value: string) => boolean = () => true): string {
  const query = new URL(window.location.href).searchParams.get(key)
  if (query !== null && validate(query)) return query
  try {
    const stored = window.localStorage.getItem(`${storagePrefix}${key}`)
    if (stored !== null && validate(stored)) return stored
  } catch { /* storage is optional */ }
  return fallback
}
