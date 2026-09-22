import { defineStore } from 'pinia';
import { ref, watch } from 'vue';
import axios from 'axios';
import { ElMessage } from 'element-plus';
export const useLogStore = defineStore('log', () => {
    // result is the single snapshot that drives the top-bar type label, the table
    // and every chart. Nothing keeps a parallel copy of logs/scores.
    const result = ref(null);
    const loading = ref(false);
    const searchQuery = ref('');
    const logType = ref('nginx');
    const hydrating = ref(true);
    const rules = ref([
        { id: 1, name: '高频ERROR', type: 'level', threshold: 5, enabled: true },
        { id: 2, name: '异常流量', type: 'count', threshold: 200, enabled: false },
        { id: 3, name: '关键词命中', type: 'keyword', threshold: 0, enabled: true }
    ]);
    function enabledRules() {
        return rules.value
            .filter(r => r.enabled)
            .map(({ id, name, type, threshold }) => ({ id, name, type, threshold }));
    }
    async function hydrate() {
        hydrating.value = true;
        try {
            const { data } = await axios.get('/api/snapshot/latest');
            result.value = data;
            logType.value = data.logType;
            searchQuery.value = data.query || '';
        }
        catch {
            // No snapshot yet — stay in the ungenerated state.
            result.value = null;
        }
        finally {
            hydrating.value = false;
        }
    }
    // Switching log type invalidates the previous snapshot immediately, so the
    // old type's table rows / chart points can never linger under a new label.
    watch(logType, (next, prev) => {
        if (!hydrating.value && next !== prev)
            result.value = null;
    });
    async function generate() {
        loading.value = true;
        try {
            const { data } = await axios.post('/api/generate', {
                type: logType.value,
                count: 1000,
                rules: enabledRules(),
                query: searchQuery.value
            });
            result.value = data;
        }
        catch (e) {
            // On failure keep the previous valid snapshot visible instead of showing
            // a half-broken mix; retrying replaces it atomically on success.
            ElMessage.error('日志生成失败，请重试');
            throw e;
        }
        finally {
            loading.value = false;
        }
    }
    async function detect() {
        if (!result.value)
            return;
        loading.value = true;
        try {
            const { data } = await axios.post('/api/detect', {
                // Snapshot id only: the server recomputes from the FULL stored log set,
                // guaranteeing identical windows/scores to /api/generate.
                snapshotId: result.value.snapshotId,
                rules: enabledRules(),
                query: searchQuery.value
            });
            result.value = data;
        }
        catch (e) {
            ElMessage.error('异常检测失败，请重试');
            throw e;
        }
        finally {
            loading.value = false;
        }
    }
    return { result, loading, searchQuery, logType, rules, hydrate, generate, detect };
});
