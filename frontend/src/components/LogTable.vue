<template>
  <div class="panel" style="height:100%">
    <h4>📋 日志流 ({{ store.result?.totalLogs || 0 }} 条)</h4>
    <div class="table-wrap">
      <el-table :data="store.result?.logs||[]" size="small" max-height="400" stripe>
        <el-table-column prop="id" label="#" width="50"/>
        <el-table-column prop="timestamp" label="时间" width="150"/>
        <el-table-column prop="level" label="级别" width="70">
          <template #default="{row}"><el-tag size="small" :type="['ERROR','error'].includes(row.level)?'danger':['WARN','warn','WARNING','warning','notice'].includes(row.level)?'warning':'info'">{{ row.level }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="source" label="来源" width="120"/>
        <el-table-column prop="message" label="消息" show-overflow-tooltip/>
      </el-table>
    </div>
  </div>
</template>
<script setup lang="ts">
import { useLogStore } from '../store/log'
const store = useLogStore()
</script>
<style scoped>.panel{background:#1e293b;border-radius:8px;padding:12px;height:100%;border:1px solid #334155}.panel h4{color:#38bdf8;font-size:13px;margin-bottom:8px}.table-wrap{height:calc(100% - 30px);overflow:auto}</style>