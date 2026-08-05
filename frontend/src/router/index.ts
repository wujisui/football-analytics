import { createRouter, createWebHistory } from 'vue-router'

import FixturesShellLayout from '@/layouts/FixturesShellLayout.vue'
import Predictions from '@/views/Predictions/index.vue'
import Results from '@/views/Results/index.vue'

// Off the first-paint path — split so a cold reload boots the lists sooner.
const Detail = () => import('@/views/Detail/index.vue')
const Mine = () => import('@/views/Mine/index.vue')

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      component: FixturesShellLayout,
      children: [
        {
          path: '',
          redirect: { name: 'predictions' },
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
      redirect: { name: 'mine-favorites' },
    },
    {
      path: '/plans',
      redirect: { name: 'mine-plans' },
    },
    {
      path: '/plans/:planId',
      redirect: { name: 'mine-plans' },
    },
    {
      path: '/mine',
      name: 'mine',
      redirect: { name: 'mine-account' },
    },
    {
      path: '/mine/account',
      name: 'mine-account',
      component: Mine,
    },
    {
      path: '/mine/favorites',
      name: 'mine-favorites',
      component: Mine,
    },
    {
      path: '/mine/plans',
      name: 'mine-plans',
      component: Mine,
    },
    {
      path: '/mine/theme',
      name: 'mine-theme',
      component: Mine,
    },
    {
      path: '/mine/session',
      name: 'mine-session',
      component: Mine,
    },
    {
      path: '/mine/about',
      name: 'mine-about',
      component: Mine,
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
        name: 'predictions',
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
