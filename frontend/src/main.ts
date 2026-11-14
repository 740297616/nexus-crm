import { createApp } from 'vue'

import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'

import App from './App.vue'
import router from './router'
import { createAppStore } from './stores/app'
import { initializeAuthTransport, useAuthStore } from './stores/auth'
import './styles.css'

const app = createApp(App)

const pinia = createAppStore()
app.use(pinia)
initializeAuthTransport(useAuthStore(pinia), () => {
  if (router.currentRoute.value.name !== 'login') {
    void router.push('/login')
  }
})
app.use(router)
app.use(ElementPlus)
app.mount('#app')
