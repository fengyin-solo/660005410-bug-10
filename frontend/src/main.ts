import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import App from './App.vue'
import { useLogStore } from './store/log'

const pinia = createPinia()

// Restore the last result snapshot before first render so a refresh/re-entry
// shows the same type label, table and charts as the server has stored.
const store = useLogStore(pinia)
store.hydrate().finally(() => {
  const app = createApp(App)
  app.use(pinia)
  app.use(ElementPlus)
  app.mount('#app')
})
