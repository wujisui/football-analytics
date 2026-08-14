import { createRouter, createWebHistory } from 'vue-router'

import FixturesShellLayout from '@/layouts/FixturesShellLayout.vue'
import Predictions from '@/views/Predictions/index.vue'
import Results from '@/views/Results/index.vue'
import Detail from '@/views/Detail/index.vue'

// Off the first-paint path — keep secondary shells split so cold reload boots lists sooner.
const Favorites = () => import('@/views/Favorites/index.vue')
const Mine = () => import('@/views/Mine/index.vue')
const MineAccount = () => import('@/views/Mine/account/index.vue')
const MinePlans = () => import('@/views/Mine/plans/index.vue')
const MineTheme = () => import('@/views/Mine/theme/index.vue')
const MineAdmin = () => import('@/views/Mine/admin/index.vue')
const MineAbout = () => import('@/views/Mine/about/index.vue')

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
      name: 'favorites',
      component: Favorites,
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
      path: '/mine/favorites',
      redirect: { name: 'favorites' },
    },
    {
      path: '/mine',
      component: Mine,
      children: [
        {
          path: '',
          redirect: { name: 'mine-account' },
        },
        {
          path: 'account',
          name: 'mine-account',
          component: MineAccount,
        },
        {
          path: 'plans',
          name: 'mine-plans',
          component: MinePlans,
        },
        {
          path: 'theme',
          name: 'mine-theme',
          component: MineTheme,
        },
        {
          path: 'session',
          redirect: { name: 'mine-account' },
        },
        {
          path: 'admin',
          name: 'mine-admin',
          component: MineAdmin,
        },
        {
          path: 'about',
          name: 'mine-about',
          component: MineAbout,
        },
      ],
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
