import { createRouter, createWebHistory } from 'vue-router'

import Detail from '@/views/Detail.vue'
import FixturesShellLayout from '@/layouts/FixturesShellLayout.vue'
import Home from '@/views/Home.vue'
import Predictions from '@/views/Predictions.vue'
import Results from '@/views/Results.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      component: FixturesShellLayout,
      children: [
        {
          path: '',
          name: 'home',
          component: Home,
        },
        {
          path: 'predictions',
          name: 'predictions',
          component: Predictions,
        },
        {
          path: 'results',
          name: 'results',
          component: Results,
        },
      ],
    },
    {
      path: '/favorites',
      redirect: { name: 'home' },
    },
    {
      path: '/fixture/:fixtureId',
      name: 'fixture-detail',
      component: Detail,
      props: true,
    },
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
    if (savedPosition) return savedPosition
    return false
  },
})

export default router
