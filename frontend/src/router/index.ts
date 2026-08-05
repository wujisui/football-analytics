import { createRouter, createWebHistory } from 'vue-router'

import FixturesShellLayout from '@/layouts/FixturesShellLayout.vue'
import Home from '@/views/Home/index.vue'
import Predictions from '@/views/Predictions/index.vue'
import Results from '@/views/Results/index.vue'

// Off the first-paint path — split so a cold reload boots the lists sooner.
const Detail = () => import('@/views/Detail/index.vue')
const Favorites = () => import('@/views/Favorites/index.vue')
const Mine = () => import('@/views/Mine/index.vue')
const BetPlans = () => import('@/views/Plans/index.vue')
const BetPlanDetail = () => import('@/views/Plans/PlanDetail.vue')

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
      name: 'favorites',
      component: Favorites,
    },
    {
      path: '/plans',
      name: 'bet-plans',
      component: BetPlans,
    },
    {
      path: '/plans/:planId',
      name: 'bet-plan-detail',
      component: BetPlanDetail,
      props: true,
    },
    {
      path: '/mine',
      name: 'mine',
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
