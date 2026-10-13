/** Only the newest request may update the selected task or its loading state. */
export function createLatestRequest() {
  let sequence = 0
  return {
    invalidate() { sequence += 1 },
    async run(request, { commit, error, settled } = {}) {
      const ticket = ++sequence
      try {
        const result = await request()
        if (ticket !== sequence) return false
        commit?.(result)
        return true
      } catch (failure) {
        if (ticket === sequence) error?.(failure)
        return false
      } finally {
        if (ticket === sequence) settled?.()
      }
    },
  }
}
