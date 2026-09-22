<script setup lang="ts">
import MineSectionBody from '@/views/Mine/components/MineSectionBody.vue'
import pkg from '../../../../package.json'

defineOptions({name: 'MineAbout'})

/** 产品说明随版本走，直接写在前端；不建表、不加接口。 */
const pages: { name: string; detail: string }[] = [
  {
    name: '比赛（手机端为「计算器」）',
    detail:
        '按联赛与赛程日筛选未开赛比赛，逐场展示胜平负赔率、让球盘口、大小球、双方进球与比分预测，胜平负概率可视化；玩法卡片按全场独赢、全场让球、全场大小、全场双进四列排列，每场只能选择一个投注格；底部汇总已选玩法，算出串关注数与预计奖金，可保存为方案。',
  },
  {
    name: '赛程',
    detail:
        '按赛程日回看已开赛与完场比赛，完场标注实际比分；统计胜平负、让球、大小球、双方进球与当日累计推荐各自的命中率，含当日统计与近 30 天走势。日推与分析器是两条轨道，卡片头部 [荐] 显示当时冻结的投注项并按它自己结算，与下方五项分析器命中互不影响。「当日累计推荐」统计的是该比赛日曾经进过推荐位的全部场次，不是屏幕上同时显示的那 4 场：推荐会随盘口滚动重排，开赛一场就固化一条，所以一个比赛日的样本数通常是 8~20 注。让球固定按亚盘结算。',
  },
  {
    name: '关注',
    detail:
        '按比赛日（比赛所在地日历日，与【比赛】列表同一口径）汇总你手动点星的场次；日期条标出哪些天有记录。系统每日推荐不写入这里，只在【比赛】列表置顶显示。',
  },
  {
    name: '我的',
    detail:
        '账号信息、我的方案（按赛程日回溯方案命中情况）、主题与让球结算口径（亚盘）以及本页产品说明。管理员另有热门联赛勾选与数据同步开关。',
  },
]

const logic: { name: string; detail: string }[] = [
  {
    name: '每日推荐：命中概率前 4 场',
    detail:
      '概率优先取盘口去水价：自研模型必须在最近一段比赛上同时以两项指标赢过市场，才允许接管它那个玩法的概率，目前四个模型都还没做到，所以推荐跑的是“市场基线 + 分层优选”，不是“我们比庄家更准”。有让球盘时先看让球，但命中概率扣完盘口方向惩罚后仍达到 50% 才保留；否则降到大小球与双方进球，由两者按调整后概率竞争。没有让球盘时，独赢只作最后兜底。方向逆着已明确移动的盘口会被淘汰，逆着弱方向则降权并可能触发降级。过闸后按“层级 → 调整后命中概率”取当天前 4 场，赔率不参与排序——概率本身就来自赔率，再乘一次净赔率只会系统性地挑最像抛硬币的盘。推荐落在「其他」联赛时，该联赛会在【比赛】筛选里自动勾上。每次批量同步后重挑，已开赛推荐冻结留档，所以「当日累计推荐」仍可能多于屏幕同时展示的 4 场。',
  },
  {
    name: '[荐] 标签：每场只推一个玩法',
    detail:
        '所有比赛都有一条“每场参考”：未入选当天前 4 的场次在推荐卡片右侧显示这条参考的命中概率，把方向、概率来源、期望收益和盘口一致性放进悬停说明。悬停里的期望收益按当前口径恒为负，负的幅度就是庄家抽水——它只用于审计，不代表这注没价值，也不代表有价值。只有进入当天前 4 的场次带 [荐]；[荐] 指向按“合格让球→大小球/双进→无盘独赢”降级选出的实际投注项。让球与四分之一大小球按全赢、赢半、走水、输半、全输分别计算，不再用简单二元命中率代替真实结算。',
  },
  {
    name: '推荐强度：命中概率',
    detail:
      '推荐强度就是校准后的命中概率本身，卡片右侧那个百分比：日推显示实际投注那一注的概率，其余场次显示每场参考的概率，两者是同一个量，不再分成星级档位。概率较低的场次也可能因为当天没有更好的选择而进入前 4，此时会如实显示较低的百分比。关注星标仍只表示你的手动收藏。',
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
    <section class="fa-section">
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
    </section>

    <section class="fa-section">
      <h2 class="fa-section-title">产品定位</h2>
      <n-p depth="3">
        Football Analytics 是一套人机协同的足球赛前决策辅助系统：机器把上百场比赛、几十种玩法压缩成少量可执行的建议，最终判断仍由你来做。
        开赛后预测快照冻结，只回写比分与命中结果，方便事后逐条验证。
      </n-p>
    </section>

    <section class="fa-section">
      <h2 class="fa-section-title">页面功能</h2>
      <n-list>
        <n-list-item v-for="item in pages" :key="item.name">
          <n-thing :title="item.name" :description="item.detail"/>
        </n-list-item>
      </n-list>
    </section>

    <section class="fa-section">
      <h2 class="fa-section-title">核心推荐逻辑</h2>
      <n-list>
        <n-list-item v-for="item in logic" :key="item.name">
          <n-thing :title="item.name" :description="item.detail"/>
        </n-list-item>
      </n-list>
    </section>

    <section class="fa-section">
      <h2 class="fa-section-title">产品价值</h2>
      <n-ul>
        <n-li v-for="item in values" :key="item">
          <n-text depth="3">{{ item }}</n-text>
        </n-li>
      </n-ul>
    </section>

    <section class="fa-section">
      <h2 class="fa-section-title">数据与同步</h2>
      <n-ul>
        <n-li v-for="item in dataNotes" :key="item">
          <n-text depth="3">{{ item }}</n-text>
        </n-li>
      </n-ul>
      <n-p depth="3">
        推荐与概率均由算法基于公开赔率和历史数据得出，仅供参考，不构成任何投注建议。
      </n-p>
    </section>
  </MineSectionBody>
</template>