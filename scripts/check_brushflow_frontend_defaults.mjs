import assert from 'node:assert/strict'
import {
  applySmartProfile,
  normalizeTask,
  smartPresets,
  taskDefaults,
} from '../plugins.v3/brushflow/src/utils.js'

assert.equal(taskDefaults.smart_profile, 'balanced')
assert.equal(taskDefaults.smart_selection_min_score, 30)
assert.equal(taskDefaults.smart_allow_proactive_delete, false)
assert.equal(taskDefaults.smart_capacity_trigger_percent, 90)
assert.equal(taskDefaults.smart_capacity_target_percent, 85)
assert.equal(taskDefaults.delete_files, true)
assert.deepEqual(
  applySmartProfile({}, 'conservative').smart_candidate_confirmations,
  smartPresets.conservative.smart_candidate_confirmations,
)
assert.equal(applySmartProfile({}, 'aggressive').smart_max_delete_capacity_percent_day, 15)

const normalized = normalizeTask({
  name: 'test',
  site_id: '1',
  downloader: 'qb',
  smart_max_delete_gb_per_run: '',
  smart_max_delete_gb_per_day: '16',
})
assert.equal(normalized.smart_max_delete_gb_per_run, null)
assert.equal(normalized.smart_max_delete_gb_per_day, 16)
assert.equal(normalized.smart_allow_proactive_delete, false)

console.log('BrushFlow frontend defaults OK')
