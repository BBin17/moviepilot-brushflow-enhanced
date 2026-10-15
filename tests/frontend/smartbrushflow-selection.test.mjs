import test from 'node:test'
import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import {selectionReasonText,selectionStatus,etaText,feedbackText} from '../../plugins.v3/smartbrushflow/src/selection-ui.js'

test('actual adds, failed requests and old qualified records have different labels',()=>{
  assert.equal(selectionStatus({status:'added'}),'已添加')
  assert.equal(selectionStatus({status:'add_failed'}),'添加失败')
  assert.equal(selectionStatus({selected:true}),'评分通过（旧记录）')
  assert.match(selectionStatus({status:'waiting'}),/等待/)
})
test('unknown outcomes and speed are not presented as zero or a guaranteed ETA',()=>{
  assert.match(etaText(null),/待积累/)
  assert.match(etaText(undefined),/待积累/)
  assert.match(etaText(2),/约 2.0 小时/)
  assert.match(feedbackText(),/不把缺失数据当零收益/)
  assert.match(feedbackText({sample_count:25,productive_count:4}),/25 个独立种子.*4 个/)
  assert.match(selectionReasonText(['demand_falling','download_backlog_unhealthy']),/正在减少.*先处理/)
  assert.doesNotMatch(selectionReasonText(['unknown_internal_code']),/unknown_internal_code/)
})
test('opportunity drilldown exposes explanations and responsive details without destructive actions',()=>{
  const source=readFileSync(new URL('../../plugins.v3/smartbrushflow/src/components/SelectionInsight.vue',import.meta.url),'utf8')
  assert.match(source,/重复检查不会增加样本/)
  assert.match(source,/评分通过不代表已经添加/)
  assert.match(source,/最低保种占用/)
  assert.match(source,/@download|emit\('download'\)/)
  assert.match(source,/@media\(max-width:599px\)/)
  assert.doesNotMatch(source,/api\.post|delete_data/)
})
