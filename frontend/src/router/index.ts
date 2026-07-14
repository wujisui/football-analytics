import { createRouter, createWebHistory } from 'vue-router'

import Detail from '@/views/Detail.vue'
import Home from '@/views/Home.vue'
import Results from '@/views/Results.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'home',
      component: Home,
    },
    {
      path: '/results',
      name: 'results',
      component: Results,
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
  scrollBehavior(_to, _from, savedPosition) {
    // Prefer browser back/forward position; Home list scroll is kept via keep-alive.
    if (savedPosition) return savedPosition
    return false
  },
})

export default router
