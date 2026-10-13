import test from 'node:test'
import assert from 'node:assert/strict'
import { createLatestRequest } from '../../plugins.v3/smartbrushflow/src/latest-request.js'

test('switching tasks cannot let an older response overwrite the new task', async () => {
  const loader = createLatestRequest()
  const committed = []
  let finishOld
  const old = loader.run(() => new Promise(resolve => { finishOld = resolve }), { commit: row => committed.push(row) })
  loader.invalidate()
  await loader.run(async () => ({task:{id:'new'}}), { commit: row => committed.push(row) })
  finishOld({task:{id:'old'}})
  await old
  assert.deepEqual(committed, [{task:{id:'new'}}])
})

test('an obsolete failed request does not replace current loading/error state', async () => {
  const loader = createLatestRequest()
  let rejectOld
  let error = null
  const old = loader.run(() => new Promise((_, reject) => { rejectOld = reject }), { error: failure => { error = failure } })
  await loader.run(async () => 'current', { commit: () => {} })
  rejectOld(new Error('obsolete'))
  await old
  assert.equal(error, null)
})
