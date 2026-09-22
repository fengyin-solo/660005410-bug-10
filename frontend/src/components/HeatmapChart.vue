<template>
  <div class="panel"><h4>🔥 日志级别热力图</h4><div ref="chart" class="chart"></div></div>
</template>
<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted } from 'vue'
import * as echarts from 'echarts'
import { useLogStore } from '../store/log'
const store = useLogStore(); const chart = ref<HTMLDivElement>(); let inst: echarts.ECharts|null=null
function update() {
  if (!inst) return
  if (!store.result) { inst.clear(); return }
  const ws = store.result.windows; const levels = ['INFO','WARN','ERROR','DEBUG']
  // Normalize level casing: apache/custom emit info/warn/error/notice variants.
  const norm = (lv: string) => {
    const u = lv.toUpperCase()
    if (u === 'WARNING') return 'WARN'
    if (u === 'NOTICE') return 'INFO'
    return u
  }
  const data: [number,number,number][] = []
  ws.forEach((w,i) => {
    const counts: Record<string, number> = { INFO:0, WARN:0, ERROR:0, DEBUG:0 }
    for (const [lv, c] of Object.entries(w.levels)) {
      const k = norm(lv)
      if (k in counts) counts[k] += c
    }
    levels.forEach((lv,j) => { data.push([i,j,counts[lv]]) })
  })
  inst.setOption({
    backgroundColor:'transparent',grid:{left:60,right:15,top:5,bottom:25},
    xAxis:{type:'category',data:ws.map((_,i)=>'W'+i),axisLabel:{color:'#94a3b8',fontSize:8}},
    yAxis:{type:'category',data:levels,axisLabel:{color:'#94a3b8',fontSize:9}},
    visualMap:{min:0,max:Math.max(...data.map(d=>d[2]),1),inRange:{color:['#1e293b','#fef08a','#ef4444']},calculable:false,show:false},
    series:[{type:'heatmap',data,label:{show:true,fontSize:8,color:'#94a3b8'}}],animation:false
  }, true)
}
onMounted(()=>{if(chart.value){inst=echarts.init(chart.value);update()}})
watch(()=>store.result,update)
onUnmounted(()=>inst?.dispose())
</script>
<style scoped>.panel{background:#1e293b;border-radius:8px;padding:12px;border:1px solid #334155}.panel h4{color:#38bdf8;font-size:13px;margin-bottom:4px}.chart{width:100%;height:200px}</style>