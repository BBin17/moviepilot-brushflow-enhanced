import test from 'node:test'
import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import {adjacentTaskId, filterTaskNavigation, taskNavigationItems, taskNavigationSummary, validTaskSelection} from '../../plugins.v3/smartbrushflow/src/task-navigation.js'

const tasks=Array.from({length:50},(_,index)=>({
  id:`task-${index}`,name:`任务${index}`,site_name:`站点${index}`,downloader:'qb下载器',enabled:index%2===0,
  strategy:{ui_summary:{health:{level:index===7?'warning':'success'},download:{issue_count:index===9?2:0},performance:{uploaded_bytes_24h:index}}},
}))

test('50 tasks remain searchable by name, site and downloader with unique primitive IDs',()=>{
  const items=taskNavigationItems(tasks)
  assert.equal(items.length,50)
  assert.equal(new Set(items.map(item=>item.id)).size,50)
  assert.match(items[37].searchText,/任务37 站点37 qb下载器/)
  assert.equal(filterTaskNavigation('', '站点37', {raw:items[37]}),true)
  assert.equal(filterTaskNavigation('', 'QB', {raw:items[37]}),true)
  assert.equal(filterTaskNavigation('', '不存在', {raw:items[37]}),false)
  assert.deepEqual(taskNavigationSummary(items),{total:50,enabled:25,attention:2})
  assert.equal(items[0].uploaded,0)
  assert.equal(taskNavigationItems([{id:'new'}])[0].uploaded,null)
})

test('navigation boundaries and same, missing or object selections cannot change current task',()=>{
  const items=taskNavigationItems(tasks)
  assert.equal(adjacentTaskId(items,'task-0',-1),null)
  assert.equal(adjacentTaskId(items,'task-49',1),null)
  assert.equal(adjacentTaskId(items,'task-20',1),'task-21')
  assert.equal(adjacentTaskId(items,'missing',1),null)
  assert.equal(validTaskSelection(items,'task-0','task-1'),true)
  for(const invalid of ['task-0','missing',null,{id:'task-1'}])assert.equal(validTaskSelection(items,'task-0',invalid),false)
  assert.deepEqual(taskNavigationSummary(taskNavigationItems([])),{total:0,enabled:0,attention:0})
})

test('navigator uses one searchable, height-bounded picker rather than one expanded card per task',()=>{
  const component=readFileSync(new URL('../../plugins.v3/smartbrushflow/src/components/TaskNavigator.vue',import.meta.url),'utf8')
  assert.match(component,/item-value="id"/)
  assert.match(component,/maxHeight: 360/)
  assert.match(component,/@update:model-value="select"/)
  assert.match(component,/上一个任务/)
  assert.doesNotMatch(component,/v-for="task in tasks"|task-health-grid|return-object/)
  assert.match(component,/@media\(max-width:599px\)/)
  const parent=readFileSync(new URL('../../plugins.v3/smartbrushflow/src/components/SmartBrushFlow.vue',import.meta.url),'utf8')
  assert.match(parent,/<TaskNavigator[^>]+@select="selectTask"/)
  assert.doesNotMatch(parent,/TaskHealthCards/)
})
