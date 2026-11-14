import { createApp } from 'vue'

import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'

import App from './App.vue'
import router from './router'
import { createAppStore } from './stores/app'
import './styles.css'

const app = createApp(App)

app.use(createAppStore())
app.use(router)
app.use(ElementPlus)
app.mount('#app')
