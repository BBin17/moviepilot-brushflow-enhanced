import assert from 'node:assert/strict'
import { applyProfile, cloneTaskV9, newTaskV9, normalizeTaskV9, profileDefaults, taskPreview } from '../plugins.v3/brushflow/src/v9-ui.js'

const v9 = newTaskV9()
assert.equal(v9.schema_version, 9)
assert.equal(v9.selection.size_min_gb, 0.5)
assert.equal(v9.deletion.enabled, false)
assert.equal(v9.deletion.delete_data, true)
assert.equal(v9.strategy.overrides.capacity_trigger_percent, 90)
assert.equal(v9.strategy.overrides.capacity_target_percent, 85)
const conservative = applyProfile(v9, 'conservative')
assert.equal(conservative.strategy.overrides.max_add_per_run, 2)
assert.equal(conservative.strategy.overrides.candidate_confirmations, 4)
assert.equal(profileDefaults.aggressive.max_release_percent_day, 15)
assert.equal(conservative.deletion.min_seed_hours, v9.deletion.min_seed_hours)
assert.equal(conservative.deletion.delete_data, v9.deletion.delete_data)
const cloned = cloneTaskV9({ ...v9, identity: { ...v9.identity, name: '测试任务' } })
assert.equal(cloned.identity.name, '测试任务')
assert.equal(cloned.schema_version, 9)
const normalized = normalizeTaskV9({ ...v9, capacity: { ...v9.capacity, limit_gb: '' } })
assert.equal(normalized.capacity.limit_gb, null)
assert.match(taskPreview(v9, '咖啡'), /咖啡/)

console.log('BrushFlow frontend defaults OK')
