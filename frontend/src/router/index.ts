import { createRouter, createWebHistory } from 'vue-router'

import Detail from '@/views/Detail.vue'
import Home from '@/views/Home.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'home',
      component: Home,
    },
    {
      path: '/fixture/:fixtureId',
      name: 'fixture-detail',
      component: Detail,
      props: true,
    },
    // Backward-compatible redirects from previous MVP routes
    {
      path: '/leagues/:leagueId',
      redirect: (to) => ({
        name: 'home',
        query: { league: String(to.params.leagueId) },
      }),
    },
    {
      path: '/fixtures/:fixtureId',
      redirect: (to) => ({
        name: 'fixture-detail',
        params: { fixtureId: to.params.fixtureId },
      }),
    },
  ],
  scrollBehavior() {
    return { top: 0 }
  },
})

export default router
