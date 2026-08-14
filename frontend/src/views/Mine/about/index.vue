<script setup lang="ts">
import MineSectionBody from '@/views/Mine/components/MineSectionBody.vue'
import pkg from '../../../../package.json'

defineOptions({ name: 'MineAbout' })

/** 产品说明随版本走，直接写在前端；不建表、不加接口。 */
const pages: { name: string; detail: string }[] = [
  {
    name: '比赛（手机端为「计算器」）',
    detail:
      '按联赛与赛程日筛选未开赛比赛，逐场展示胜平负赔率、让球盘口、大小球、双方进球与比分预测，胜平负概率可视化；支持搜索联赛与球队；底部汇总已勾选玩法，算出串关注数与预计奖金，可保存为方案。',
  },
  {
    name: '赛程',
    detail:
      '按赛程日回看已开赛与完场比赛，完场标注实际比分；统计胜平负、让球、大小球、双方进球与每日推荐各自的命中率，含当日统计与近 30 天走势。',
  },
  {
    name: '关注',
    detail:
      '按赛程日汇总星标场次，既有你手动收藏的比赛，也有系统的每日推荐；日期条标出哪些天有关注。',
  },
  {
    name: '我的',
    detail:
      '账号信息、我的方案（按赛程日回溯方案命中情况）、主题设置与本页产品说明。',
  },
]

const logic: { name: string; detail: string }[] = [
  {
    name: '★ 星标：每个比赛日最多 4 场',
    detail:
      '只从热门联赛里已备好分析包、且尚未开赛的比赛中挑选，按单选玩法的期望回报排序，每个比赛日各挑最多 4 场。是上限而不是保底：某天可用场次不足时会少于 4 场。每次定时同步后重挑，开赛后的推荐轨迹冻结留档，供命中率统计学习。星标颜色统一，不表达质量。',
  },
  {
    name: '[荐] 标签：每场只推一个玩法',
    detail:
      '一场比赛给出胜平负、让球、大小球、双方进球、比分五项预测，但只有一个玩法带 [荐]，代表这场最看好的选项。候选只收单选玩法，胜/平、让胜/负这类多选一律排除；精确比分只作详情提示，不参与主推。',
  },
  {
    name: '质量提示：金色与蓝色',
    detail:
      '综合分低于历史 P30 阈值时，[荐] 标签由金色转为蓝色，提示这条推荐质量偏低、可以跳过；金色为正常质量。质量只影响这个标签，不影响关注星标。',
  },
  {
    name: '使用路径',
    detail:
      '每天先看这几场星标比赛，取带 [荐] 的玩法，在计算器里勾选组成串关，保存成方案，赛后到「我的方案」和「赛程」对照命中。',
  },
]

const values: string[] = [
  '降低筛选成本：几百场比赛收到最多 4 场，几十种玩法收到 1 个 [荐]。',
  '数据透明可验证：赔率、概率与历史准确率全部公开，不夸大、不保证。',
  '决策链路闭环：推荐 → 勾选 → 串关 → 奖金 → 方案命中回溯。',
  '人机协同：机器处理数据、给出建议，最终判断仍由你来做。',
]

const dataNotes: string[] = [
  '所有数据只来自本项目后端，官方 API Key 仅存在服务端，不进入前端。',
  '赛程、盘口、赛果与积分榜由固定定时批次同步；阵容、伤病、历史交锋、近况等展示包在你打开比赛详情时按需补拉并落库，供后续复用。',
  '列表页加载、刷新、下拉与切换筛选都只读本地库，不做实时比分轮询——这是赛前分析工具，不是实时比分站。',
  '未登录即可浏览每日推荐；登录后收藏与方案按账号隔离，每日推荐对所有账号一致。',
]
</script>

<template>
  <MineSectionBody>
    <n-card size="small" :bordered="false">
      <n-descriptions
        label-placement="left"
        :column="1"
        size="small"
        :label-style="{ width: '72px' }"
      >
        <n-descriptions-item label="定位">
          赛前分析工具，非实时比分站
        </n-descriptions-item>
        <n-descriptions-item label="版本">
          {{ pkg.version }} · 内测阶段
        </n-descriptions-item>
        <n-descriptions-item label="数据">
          仅调用本项目后端；官方 Key 不进入前端
        </n-descriptions-item>
        <n-descriptions-item label="账号">
          未登录也可浏览；登录后收藏与方案按账号保存
        </n-descriptions-item>
      </n-descriptions>
    </n-card>

    <n-card size="small" :bordered="false" title="产品定位">
      <n-p depth="3">
        Football Analytics 是一套人机协同的足球赛前决策辅助系统：机器把上百场比赛、几十种玩法压缩成少量可执行的建议，最终判断仍由你来做。
        开赛后预测快照冻结，只回写比分与命中结果，方便事后逐条验证。
      </n-p>
    </n-card>

    <n-card
      size="small"
      :bordered="false"
      title="页面功能"
      content-style="padding: 0;"
    >
      <n-list>
        <n-list-item v-for="item in pages" :key="item.name">
          <n-thing :title="item.name" :description="item.detail" />
        </n-list-item>
      </n-list>
    </n-card>

    <n-card
      size="small"
      :bordered="false"
      title="核心推荐逻辑"
      content-style="padding: 0;"
    >
      <n-list>
        <n-list-item v-for="item in logic" :key="item.name">
          <n-thing :title="item.name" :description="item.detail" />
        </n-list-item>
      </n-list>
    </n-card>

    <n-card size="small" :bordered="false" title="产品价值">
      <n-ul>
        <n-li v-for="item in values" :key="item">
          <n-text depth="3">{{ item }}</n-text>
        </n-li>
      </n-ul>
    </n-card>

    <n-card size="small" :bordered="false" title="数据与同步">
      <n-ul>
        <n-li v-for="item in dataNotes" :key="item">
          <n-text depth="3">{{ item }}</n-text>
        </n-li>
      </n-ul>
      <n-p depth="3">
        推荐与概率均由算法基于公开赔率和历史数据得出，仅供参考，不构成任何投注建议。
      </n-p>
    </n-card>
  </MineSectionBody>
</template>
