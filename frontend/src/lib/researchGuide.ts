export const researchGuideStorageKey = 'oddsquant.research-guide.v1'

export function shouldShowResearchGuide(storage: Pick<Storage, 'getItem'> = window.localStorage): boolean {
  return storage.getItem(researchGuideStorageKey) !== 'dismissed'
}

export function rememberResearchGuideDismissal(storage: Pick<Storage, 'setItem'> = window.localStorage): void {
  storage.setItem(researchGuideStorageKey, 'dismissed')
}
