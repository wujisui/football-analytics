import { createRouter, createWebHistory } from 'vue-router'

import AnalysisView from '@/views/AnalysisView.vue'
import FixturesView from '@/views/FixturesView.vue'
import LeaguesView from '@/views/LeaguesView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'leagues',
      component: LeaguesView,
    },
    {
      path: '/leagues/:leagueId',
      name: 'fixtures',
      component: FixturesView,
      props: true,
    },
    {
      path: '/fixtures/:fixtureId',
      name: 'analysis',
      component: AnalysisView,
      props: true,
    },
  ],
})

export default router
