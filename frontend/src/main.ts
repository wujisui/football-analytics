import { createApp } from 'vue'

import App from './App.vue'
import { vNestedScroll } from './directives/nestedScroll'
import router from './router'
import './style.css'

const app = createApp(App)

app.directive('nested-scroll', vNestedScroll)
app.use(router)
app.mount('#app')
