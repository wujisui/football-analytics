<script setup lang="ts">
import MineSectionBody from '@/views/Mine/components/MineSectionBody.vue'
import pkg from '../../../../package.json'

defineOptions({name: 'MineAbout'})

/** 产品说明随版本走，直接写在前端；不建表、不加接口。 */
const pages: { name: string; detail: string }[] = [
  {
    name: '比赛（手机端为「计算器」）',
    detail:
        '按联赛与赛程日筛选未开赛比赛，逐场展示胜平负赔率、让球盘口、大小球、双方进球与比分预测，胜平负概率可视化；支持搜索联赛与球队；底部汇总已勾选玩法，算出串关注数与预计奖金，可保存为方案。胜平负在盘口已拉开明显热门时给单选，只有市场自己也没选出热门的胶着盘才给「胜/平」这类双选。',
  },
  {
    name: '赛程',
    detail:
        '按赛程日回看已开赛与完场比赛，完场标注实际比分；统计胜平负、让球、大小球、双方进球与每日推荐各自的命中率，含当日统计与近 30 天走势。日推与分析器是两条轨道，卡片头部 [荐] 显示当时冻结的投注项并按它自己结算，与下方五项分析器命中互不影响。让球命中按「我的 → 偏好设置」当前口径结算。',
  },
  {
    name: '关注',
    detail:
        '按比赛日（比赛所在地日历日，与【比赛】列表同一口径）汇总你手动点星的场次；日期条标出哪些天有记录。系统每日推荐不写入这里，只在【比赛】列表置顶显示。',
  },
  {
    name: '我的',
    detail:
        '账号信息、我的方案（按赛程日回溯方案命中情况）、主题与让球玩法（亚洲盘 / 竞彩三项）以及本页产品说明。管理员另有热门联赛勾选与数据同步开关。',
  },
]

const logic: { name: string; detail: string }[] = [
  {
    name: '每日推荐：每个比赛日最多 4 场',
    detail:
      '从未开赛且本地已有盘口的比赛中挑选，不限热门或「其他」。系统先用冻结历史按玩法校准预测概率：最近 20% 样本只做时间验证，校准没有同时改善误差的玩法继续使用原概率；再结合赔率价值、每日推荐命中反馈与联赛 × 玩法历史表现调整综合分。每个比赛日仍按综合分挑最多 4 场，不因校准减少数量。推荐场次排在【比赛】列表顶部，不自动点亮关注星标；只有你手动点星才会写入个人收藏。每次定时同步后重挑，开赛后的推荐轨迹冻结留档。',
  },
  {
    name: '[荐] 标签：每场只推一个玩法',
    detail:
        '一场比赛给出胜平负、让球、大小球、双方进球、比分五项预测，但只有一个玩法带 [荐]，代表这场最看好的选项。候选只收单选玩法，胜/平、让胜/负这类多选一律排除；精确比分只作详情提示，不参与主推。分析器让球以主盘去水概率为基线；只有历史模型在最新验证比赛中同时优于盘口的两项概率指标，才会用一半模型偏差保守修正，否则仍按盘口定价。日推再用冻结历史校准命中率并比较风险调整回报，因此两者通常同向，但仍可能因玩法结算与跨场排序而不同。',
  },
  {
    name: '质量提示：相对星级',
    detail:
      '入选后只在同一比赛日的推荐场次内部比较综合分：最高质量的一场为 5 星，其余每降低一个得分档位降 0.5 星，同分同星。星级不再设置样本门槛；关注星标只表示你的手动收藏。比赛列表中主推标签使用红色，其余预测标签退为灰色。',
  },
  {
    name: '使用路径',
    detail:
        '每天先看列表顶部这几场每日推荐，取带 [荐] 的玩法，在计算器里勾选组成串关，保存成方案，赛后到「我的方案」和「赛程」对照命中。',
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
          <n-thing :title="item.name" :description="item.detail"/>
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
          <n-thing :title="item.name" :description="item.detail"/>
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
<style scoped>
.n-list-item {
  padding: 12px;
}
</style>