import { BookOpen, CheckCircle2, ShieldAlert, X } from 'lucide-react'

export function FirstVisitGuide({ onDismiss }: { onDismiss: () => void }) {
  const concepts = [
    { title: 'Probability', detail: 'The model estimate for an outcome, using only evidence available before kickoff.' },
    { title: 'Fair odds', detail: 'The decimal price implied by a probability before bookmaker margin. It is not an offered price.' },
    { title: 'Value gate', detail: 'A price qualifies only when calibrated model evidence retains positive value at its conservative lower bound.' },
    { title: 'Blocked', detail: 'Required timestamped evidence is missing, stale, or unvalidated. Stored evidence stays visible with the exact unlock step.' },
  ]

  return (
    <section aria-label='Research guide' className='border-b border-sky-200 bg-sky-50 px-4 py-4 sm:px-6 lg:px-8'>
      <div className='mx-auto max-w-6xl'>
        <div className='flex items-start justify-between gap-4'>
          <div className='flex items-start gap-3'>
            <BookOpen aria-hidden='true' className='mt-0.5 shrink-0 text-sky-700' size={20} />
            <div>
              <p className='font-bold text-sky-950'>Read the evidence in under a minute</p>
              <p className='mt-1 text-sm leading-6 text-sky-900'>OddsQuant separates likely outcomes from exact prices and refuses to turn missing evidence into a recommendation.</p>
            </div>
          </div>
          <button aria-label='Dismiss research guide' className='grid h-9 w-9 shrink-0 place-items-center border border-sky-300 text-sky-800 hover:bg-sky-100' onClick={onDismiss} type='button'><X aria-hidden='true' size={17} /></button>
        </div>
        <div className='mt-4 grid gap-2 sm:grid-cols-2 xl:grid-cols-4'>
          {concepts.map((concept, index) => (
            <div className='border border-sky-200 bg-white p-3' key={concept.title}>
              <p className='flex items-center gap-2 text-sm font-bold text-zinc-900'>{index < 3 ? <CheckCircle2 aria-hidden='true' className='text-emerald-700' size={15} /> : <ShieldAlert aria-hidden='true' className='text-amber-700' size={15} />}{concept.title}</p>
              <p className='mt-1 text-xs leading-5 text-zinc-600'>{concept.detail}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
