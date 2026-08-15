import { createApp } from 'vue'

import App from './App.vue'
import router from './router'
import './style.css'

const app = createApp(App)

/**
 * vueuc 的虚拟列表（naive 表格 `virtual-scroll` / `n-virtual-list`）在 activated
 * 钩子里直接 `listElRef.value.scrollTo(...)`。本站是嵌套 keep-alive
 * （App 缓存 FixturesShellLayout，shell 内再缓存 Predictions / Results），
 * 从【比赛】切到【我的】时会对一个已脱离文档、ref 已置空的列表跑这个钩子，抛
 * TypeError。dev 版 Vue 在没有 errorHandler 时会把它重新抛出，直接打断 keep-alive
 * 这一批 post 回调：路由变了、视图还停在旧页面，赛程列表整块消失。
 *
 * 恢复滚动位置失败对这类已销毁的列表没有影响，单独放过；其余错误照常打日志，
 * 与生产版行为一致。
 */
app.config.errorHandler = (err, _instance, info) => {
  // info 在 dev 是 'activated hook'，生产构建下是内部代号 'a'
  const isStaleVirtualListScroll =
    (info === 'activated hook' || info === 'a') &&
    err instanceof TypeError &&
    err.message.includes('scrollTo')
  if (isStaleVirtualListScroll) return
  console.error(`[vue] ${info}`, err)
}

app.use(router)
app.mount('#app')
