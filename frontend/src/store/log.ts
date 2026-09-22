import { defineStore } from 'pinia'
import { ref, watch } from 'vue'
import axios from 'axios'
import type { AnalysisResult, AlertRule } from '@/types'

const STORAGE_KEY = 'log-analysis-snapshot'

function loadSnapshot(): AnalysisResult | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) as AnalysisResult : null
  } catch {
    return null
  }
}

export const useLogStore = defineStore('log', () => {
  const result = ref<AnalysisResult | null>(loadSnapshot())
  const loading = ref(false)
  const searchQuery = ref('')
  // 顶部选中类型始终以最新快照为准，保证选择器与表格/图表同源
  const logType = ref(result.value?.type ?? 'nginx')
  const rules = ref<AlertRule[]>([
    { id:1, name:'高频ERROR', type:'level', threshold:5, enabled:true },
    { id:2, name:'异常流量', type:'count', threshold:200, enabled:false },
    { id:3, name:'关键词命中', type:'keyword', threshold:0, enabled:true }
  ])

  // 快照变更即持久化，刷新页面后恢复同一份结果
  watch(result, (snapshot) => {
    if (snapshot) localStorage.setItem(STORAGE_KEY, JSON.stringify(snapshot))
    else localStorage.removeItem(STORAGE_KEY)
  }, { deep: true })

  // 切换日志类型时旧快照必须作废，避免顶部类型与表格/图表错位
  watch(logType, (type, oldType) => {
    if (oldType !== type) result.value = null
  })

  // 请求序号：只接受最新一次请求的响应，杜绝重试/乱序覆盖
  let requestSeq = 0

  async function generate() {
    const seq = ++requestSeq
    result.value = null
    loading.value = true
    try {
      const { data } = await axios.post('/api/generate', { type: logType.value, count: 1000 })
      if (seq !== requestSeq) return
      result.value = data
    } catch (err) {
      if (seq !== requestSeq) return
      result.value = null
      throw err
    } finally {
      if (seq === requestSeq) loading.value = false
    }
  }

  async function detect() {
    if (!result.value) return
    const snapshot = result.value
    const seq = ++requestSeq
    loading.value = true
    try {
      const { data } = await axios.post('/api/detect', {
        type: snapshot.type,
        logs: snapshot.logs,
        rules: rules.value.filter(r => r.enabled),
        query: searchQuery.value
      })
      if (seq !== requestSeq) return
      result.value = data
    } catch (err) {
      // 检测失败保留原快照，不把界面打回空白；由按钮处提示
      throw err
    } finally {
      if (seq === requestSeq) loading.value = false
    }
  }

  return { result, loading, searchQuery, logType, rules, generate, detect }
})
