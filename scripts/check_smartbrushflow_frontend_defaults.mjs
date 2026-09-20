import assert from 'node:assert/strict'
import { applyProfile, cloneTaskV9, newTaskV9, normalizeTaskV9, profileDefaults, taskPreview } from '../plugins.v3/smartbrushflow/src/v9-ui.js'

const task = newTaskV9()
assert.equal(task.schema_version, 9)
assert.equal(task.selection.size_min_gb, 0.5)
assert.equal(task.deletion.enabled, false)
assert.equal(task.deletion.delete_data, true)
assert.equal(task.strategy.overrides.capacity_trigger_percent, 90)
assert.equal(task.strategy.overrides.capacity_target_percent, 85)
const conservative = applyProfile(task, 'conservative')
assert.equal(conservative.strategy.overrides.max_add_per_run, 2)
assert.equal(conservative.strategy.overrides.candidate_confirmations, 4)
assert.equal(profileDefaults.aggressive.max_release_percent_day, 15)
assert.equal(conservative.deletion.min_seed_hours, task.deletion.min_seed_hours)
assert.equal(conservative.deletion.delete_data, task.deletion.delete_data)
const cloned = cloneTaskV9({ ...task, identity: { ...task.identity, name: '测试任务' } })
assert.equal(cloned.identity.name, '测试任务')
assert.equal(cloned.schema_version, 9)
const normalized = normalizeTaskV9({ ...task, capacity: { ...task.capacity, limit_gb: '' } })
assert.equal(normalized.capacity.limit_gb, null)
assert.match(taskPreview(task, '咖啡'), /咖啡/)

console.log('SmartBrushFlow frontend defaults OK')
