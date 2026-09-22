<template>
  <div class="app-root">
    <header class="top-bar">
      <h1>📊 分布式日志聚合与智能异常检测平台</h1>
      <div class="toolbar">
        <el-select v-model="store.logType" size="small" style="width:140px">
          <el-option v-for="t in ['nginx','apache','json_app','custom']" :key="t" :label="t" :value="t"/>
        </el-select>
        <el-tag v-if="store.result" size="small" type="success" style="margin-left:-4px">
          当前结果：{{ store.result.type }}（{{ store.result.totalLogs }} 条 / {{ store.result.windows.length }} 窗口）
        </el-tag>
        <el-tag v-else size="small" type="info">未生成</el-tag>
        <el-input v-model="store.searchQuery" placeholder="搜索关键词..." size="small" style="width:200px" clearable/>
        <el-button size="small" @click="generate" :loading="store.loading">🔍 生成日志</el-button>
        <el-button size="small" type="warning" @click="detect" :loading="store.loading" :disabled="!store.result">⚠ 检测异常</el-button>
      </div>
    </header>
    <div class="main-grid">
      <div class="grid-col">
        <LogTable />
      </div>
      <div class="grid-col">
        <AnomalyChart />
        <AlertPanel />
      </div>
    </div>
    <div class="bottom-row">
      <TrendChart />
      <HeatmapChart />
    </div>
  </div>
</template>

<script setup lang="ts">
import LogTable from './components/LogTable.vue'
import AnomalyChart from './components/AnomalyChart.vue'
import AlertPanel from './components/AlertPanel.vue'
import TrendChart from './components/TrendChart.vue'
import HeatmapChart from './components/HeatmapChart.vue'
import { useLogStore } from './store/log'
import { ElMessage } from 'element-plus'
const store = useLogStore()

async function generate() {
  try {
    await store.generate()
    ElMessage.success(`已生成 ${store.logType} 日志`)
  } catch {
    ElMessage.error('日志生成失败，请重试')
  }
}

async function detect() {
  try {
    await store.detect()
    ElMessage.success('异常检测完成')
  } catch {
    ElMessage.error('检测失败，请重试')
  }
}
</script>

<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:system-ui,monospace;background:#0f172a;color:#e2e8f0}
.app-root{min-height:100vh}
.top-bar{display:flex;justify-content:space-between;align-items:center;padding:10px 20px;background:#1e293b;border-bottom:1px solid #334155}
.top-bar h1{font-size:1.1rem;color:#38bdf8}
.toolbar{display:flex;gap:8px;align-items:center}
.main-grid{display:grid;grid-template-columns:1fr 400px;gap:12px;padding:12px 20px;min-height:50vh}
.grid-col{overflow:hidden}
.bottom-row{display:grid;grid-template-columns:1fr 1fr;gap:12px;padding:0 20px 16px}
</style>