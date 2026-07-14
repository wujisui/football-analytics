<script setup lang="ts">
import { computed } from 'vue'

import type { FixtureResponse, LineupPlayer, PrematchPackage } from '@/api/types'

const props = defineProps<{
  fixture: FixtureResponse
  pkg: PrematchPackage | null
}>()

const homeName = computed(() => props.fixture.home_team_name || '—')
const awayName = computed(() => props.fixture.away_team_name || '—')

function playerLabel(p: LineupPlayer): string {
  const num = p.number != null ? `${p.number}. ` : ''
  const pos = p.pos ? ` (${p.pos})` : ''
  return `${num}${p.name}${pos}`
}
</script>

<template>
  <div class="lineup-tab">
    <n-card size="small" title="伤病情况">
      <div class="split">
        <div>
          <div class="label">{{ homeName }}</div>
          <ul v-if="pkg?.injuries.home.length" class="list">
            <li v-for="(p, idx) in pkg.injuries.home" :key="idx">
              {{ p.player_name }}
              <span v-if="p.reason" class="muted"> — {{ p.reason }}</span>
              <span v-else-if="p.type" class="muted"> — {{ p.type }}</span>
            </li>
          </ul>
          <p v-else class="muted">无伤病信息</p>
        </div>
        <div>
          <div class="label">{{ awayName }}</div>
          <ul v-if="pkg?.injuries.away.length" class="list">
            <li v-for="(p, idx) in pkg.injuries.away" :key="idx">
              {{ p.player_name }}
              <span v-if="p.reason" class="muted"> — {{ p.reason }}</span>
              <span v-else-if="p.type" class="muted"> — {{ p.type }}</span>
            </li>
          </ul>
          <p v-else class="muted">无伤病信息</p>
        </div>
      </div>
    </n-card>

    <div class="split">
      <n-card size="small" :title="`阵容 · ${homeName}`">
        <template v-if="pkg?.lineups.available && pkg.lineups.home">
          <p class="formation">
            阵型 {{ pkg.lineups.home.formation || pkg.home_formation || '—' }}
            <span v-if="pkg.lineups.home.coach"> · 教练 {{ pkg.lineups.home.coach }}</span>
          </p>
          <p class="sub">首发</p>
          <ul class="list">
            <li v-for="(p, idx) in pkg.lineups.home.start_xi" :key="idx">
              {{ playerLabel(p) }}
            </li>
          </ul>
          <p class="sub">替补</p>
          <ul v-if="pkg.lineups.home.substitutes.length" class="list">
            <li v-for="(p, idx) in pkg.lineups.home.substitutes" :key="idx">
              {{ playerLabel(p) }}
            </li>
          </ul>
          <p v-else class="muted">暂无替补名单</p>
        </template>
        <n-empty v-else description="阵容尚未公布或未拉取" size="small" />
      </n-card>

      <n-card size="small" :title="`阵容 · ${awayName}`">
        <template v-if="pkg?.lineups.available && pkg.lineups.away">
          <p class="formation">
            阵型 {{ pkg.lineups.away.formation || pkg.away_formation || '—' }}
            <span v-if="pkg.lineups.away.coach"> · 教练 {{ pkg.lineups.away.coach }}</span>
          </p>
          <p class="sub">首发</p>
          <ul class="list">
            <li v-for="(p, idx) in pkg.lineups.away.start_xi" :key="idx">
              {{ playerLabel(p) }}
            </li>
          </ul>
          <p class="sub">替补</p>
          <ul v-if="pkg.lineups.away.substitutes.length" class="list">
            <li v-for="(p, idx) in pkg.lineups.away.substitutes" :key="idx">
              {{ playerLabel(p) }}
            </li>
          </ul>
          <p v-else class="muted">暂无替补名单</p>
        </template>
        <n-empty v-else description="阵容尚未公布或未拉取" size="small" />
      </n-card>
    </div>
  </div>
</template>

<style scoped>
.lineup-tab {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.split {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}

.label {
  font-weight: 600;
  margin-bottom: 8px;
  font-size: 13px;
}

.list {
  margin: 0;
  padding-left: 18px;
  font-size: 13px;
  line-height: 1.7;
  color: #444;
}

.muted {
  margin: 0;
  font-size: 12px;
  color: var(--fa-text-faint);
  font-weight: 400;
}

.formation {
  margin: 0 0 8px;
  font-size: 13px;
  color: var(--fa-text-secondary);
}

.sub {
  margin: 10px 0 4px;
  font-size: 12px;
  font-weight: 600;
  color: var(--fa-text-secondary);
}

@media (max-width: 720px) {
  .split {
    grid-template-columns: 1fr;
  }
}
</style>
