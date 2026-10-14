import test from 'node:test'
import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import {newTaskV9, applyProfile, normalizeTaskV9, taskPreview} from '../../plugins.v3/smartbrushflow/src/v9-ui.js'

test('presets never overwrite minimum seeding, deletion choice or idle duration',()=>{
  const task=newTaskV9()
  task.deletion={...task.deletion,enabled:true,min_seed_hours:168,delete_data:false,exclude_tags:'keep',idle_zero_upload_hours:96}
  const result=applyProfile(task,'aggressive')
  assert.deepEqual(result.deletion,task.deletion)
  assert.equal(result.engine_mode,'performance')
})
test('plain preview explains performance pruning and minimum seeding without old capacity targets',()=>{
  const task=newTaskV9()
  task.deletion.enabled=true
  task.deletion.min_seed_hours=168
  task.capacity.limit_gb=800
  const text=taskPreview(task)
  assert.match(text,/保种不足168小时/)
  assert.match(text,/连续72小时零上传/)
  assert.match(text,/不等待空间满/)
  assert.doesNotMatch(text,/降到\d+GB停止|容量达到\d+GB开始/)
})
test('idle hours are normalized and legacy capacity controls are absent from the wizard',()=>{
  const task=newTaskV9()
  task.deletion.idle_zero_upload_hours='96'
  assert.equal(normalizeTaskV9(task).deletion.idle_zero_upload_hours,96)
  const wizard=readFileSync(new URL('../../plugins.v3/smartbrushflow/src/components/TaskWizardV9.vue',import.meta.url),'utf8')
  assert.doesNotMatch(wizard,/label="容量停止线|label="每天最多释放|label="每轮GB上限/)
  assert.match(wizard,/站点最低保种时间/)
})
