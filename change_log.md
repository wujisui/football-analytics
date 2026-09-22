# 变更日志

从 **2026-08-24** 起按日期记录已落地修改。产品现行口径以 `PROJECT_PLAN.md` 和
`.cursor/rules/` 为准；本文件只记录改了什么、真源和必要验证。

---

## 待办

- 用户管理页未落地：待补 `admin/users` 接口、分页列表、角色与 VIP 授权；口径见 `docs/AUTH_VIP_QUOTA.md`。
- 移动端滚动时隐藏浏览器地址栏 / 底部操作区未落地，浏览器兼容成本待评估。

---

## 2026-08-24（周一）

- 亚盘特征由 `ah_v1` 升至 `ah_v2`：`iter_ah_quotes` 读取完整盘口档位，新增副盘与初盘→即时盘同档水位变化特征。真源 `ah_features.py`、`ah_predictor.py`。
- 亚盘特征继续升至 `ah_v3`：利用既有刷新冻结中盘（T-6h）与临场盘口并生成分段变化特征，不增加官方请求。
- 统一盘口准入：只处理仍在【比赛】、当前比赛日、`leagues.is_catalog=true` 的场次；未来场次只补缺盘，比赛日才刷新即时盘。
- `odds_snapshot.py` 在读写两端校验采集时刻早于开赛时刻；开赛后不再请求或改写赛前盘口。
- 盘口解析改为单庄归集后择优，次级庄可暂存初盘，主庄开盘后由 `board_outranks` 替换，避免跨庄报价被误判为走势。
- 「打开免费配额」更名为「订阅」，并按订阅状态重排赛程、赛果、盘口和详情批次。真源 `tasks/scheduler.py`、`fixtures_sync.py`。
- 已订阅赛程改为本地保留 8 天滑动窗口，每天只补末端缺失日期；详情预拉取消数量上限，删除平行开关。
- 「立即同步」改为仅已订阅可用且不限每日次数，继续受官方请求锁限制。
- 运维页新增官方剩余、本次消耗和持久化的上次同步结果；刷新页面可恢复进行中任务与最近结果。
- 抽出 `TextSwitch`，订阅、调度和主题开关统一在轨道内显示状态。
- 赛果列表排序改为进行中优先，其次日推、关注、开赛时间。
- 「我的方案」新增中奖 / 已结算 / 全部三档统计。

## 2026-08-25（周二）

- 对阵区域只保留一个悬停浮层，避免完整队名与详情提示重叠。
- 让球悬停改为完整盘口表；初盘与即时盘按采集时间判定是否并排，统一使用 `isOpeningDistinct`。
- 列表接口新增 `odds_opening_snippet`；摘要构造收敛到 `_odds_snippet_from_package`，保留 `captured_at`。
- 盘口浮层改为一张外卡承载初盘 / 即时盘两张表，并显示各自采集时间。
- 新增全局圆角 token `--fa-radius-card`，清理业务组件中的字面圆角；规范写入 `frontend-ui.mdc`。
- 管理员新增「只更新赛果」，仅执行 `scheduled_fixtures_sync(mode=results)`，与完整同步共用请求锁。
- 已订阅曾新增 21:00～00:00 半小时轻刷；该时刻表后于 09-01 被统一密刷方案取代。

## 2026-08-26（周三）

- 联赛目录、分类、热门状态改以数据库为唯一真源，`config/leagues.json` 只作首次建库种子。
- 系统保护联赛收敛为五大联赛、荷甲、葡超、欧冠、中超；其余目录联赛允许改 ID 或确认后连历史删除。
- 新增联赛官方 ID「核对」接口，优先使用 7 天缓存，未命中才请求一次官方 `/leagues?id=`。
- 运维「批量更新盘口」接入 `prematch_odds_sync`，后端按持久化比赛日与 `is_catalog` 二次过滤。
- 定时刷盘范围改为全部目录联赛，`is_hot` 仅控制默认展示。
- 初盘写入改为源头自动判定：任何路径首次拿到可用盘口都同时写初盘和即时盘，之后只刷新即时盘。
- 四分盘推荐不再结构性输出对冲双选；整数盘仍允许包含走水项。
- 预测准确率统一为全赢 / 赢半算中，半输 / 全输算不中，走水不进分母；资金结算口径不变。
- 同步成功后通过 `notifyLocalDataChanged` / `clientDataEpoch` 作废赛果缓存，只刷新当前页面。
- 交锋页为未开赛场次插入 `VS` 行且不计统计；详情面包屑补本地开赛时间。
- 顶栏删除玩法开关，入口收敛到「我的 → 偏好设置」；手机日期输入不再唤起键盘。
- 曾新增默认 / 密刷两套晚间盘口时刻表；09-01 删除并收敛为单一密刷开关。
- 球队译名默认范围收窄到 `is_hot=true` 联赛，手工 `BY_ID` 修改必须执行 `audit-team-names`。

## 2026-08-27（周四）

- 热门联赛、订阅 / 调度开关与 Key 摘要增加标签页级 `sessionStorage` 缓存；保存后以接口结果回写，登出或鉴权失效时清除。
- 运维任务状态只在前端会话首次进入时恢复，之后复用模块级状态。
- 「主题与玩法」更名为「偏好设置」。
- 已订阅完整批次曾把未来盘口窗口扩大到三天；09-01 收窄为今天和明天。
- 后端批次完成后递增 `client_data_revision`；前端 30 秒版本检查仅在【比赛】/【赛果】前台运行。
- 亚盘独立「让平」显示为「走水」且不进入日推；历史陈旧让平自动记录在列表读取时过滤。
- 保护联赛名单收敛为 `PROTECTED_CORE_LEAGUE_IDS`，旧库在启动时通过 `sync_catalog_protection` 对齐。
- 新增 `docs/LEAGUE_ID_NAMES.md`、目录外联赛译名与 `backfill-league-names` 命令。
- 后台官方任务运行时，详情单场更新盘口返回 409；前端提前置灰并提示。
- 比分提示增加 `_align_score_with_outcomes`，确保结果方向与比分一致。
- 日推在 Top-N 前增加方向、真实让球与比分一致性校验，无法表达的候选由后续场次补位。
- 新增 `market_analysis.py` 作为盘口解释唯一真源；前端删除平行解释实现。
- 新增护眼主题，表面色真源为 `styles/themes/eye-care.css`，Naive 覆盖集中在 `theme/presets.ts`。

## 2026-08-28（周五）

- 主题选择改为深色 / 浅色 / 护眼下拉，新用户默认护眼；偏好键升级为 `fa-theme-preset-v2` 并迁移旧值。
- 样式归拢到 `src/styles`：删除 `src/style.css`，共用 token 与三套主题分文件维护，`index.html` 同步写入 `data-theme` 防闪烁。
- 【我的】移出 `keep-alive`；PC 记住上次子路由，手机仍进入个人主页。
- 日推最初只生成主胜 / 客胜独赢候选，平局不入池；让 0 按亚盘走水结算。
- `[荐]` 卡片改读日推三件套 `auto_lean` / `auto_handicap_lean` / `auto_score_hint`，不回写分析器快照。
- 曾加入严格 `EV > 0` 门槛并导致推荐池为空；同日回滚为按校准置信度选场，EV 仅作审计。
- 修复校准测试夹具按类别分块导致留出段单一类别的问题，改为固定种子打散。
- 日推候选扩为独赢与真实 AH，同一场只允许一个玩法入选。
- 曾采用 `校准概率 × sqrt(赔率-1)` 排序；该公式于 09-21 被证伪并删除。
- 浅盘按真实退半 / 走水拆分概率，深盘读取冻结 AH 概率并向市场收缩。
- 删除对退半的重复风险惩罚，`risk_adjusted_return_score` 移除 `stake_share`。
- 删除每玩法最多 3 场的配额，只保留同场单玩法限制。

## 2026-08-29（周六）

- 手机投注倍数隐藏加减按钮并收窄输入框。
- 【关注】日期条与列表分组统一读取持久化 `match_day`。
- 手机「我的方案」改为固定表头、列表滚动并适配底部安全区。
- 赛果命中标签改为命中红色、未命中灰色且不可筛选。
- `HelpTip` 在手机使用居中模态框，PC 保持 tooltip。
- 07:00、完整批次和手动更新赛果统一只回写昨天 + 今天；新增 `scheduled_results_sync_07`。
- 赛果卡片的 `[荐]` 从分析器标签中拆出，独立读取冻结日推玩法与结算结果。
- 比赛页只高亮真正入选的日推玩法，其余预测标签使用普通样式。
- 浅盘独赢与 AH 改为先做同场取舍，再叠加历史 EMA / 联赛软权重做跨场排序。
- 删除 `auto_favorites` 中已无生产引用的旧排序链。
- 对冻结快照做命中率核查，确认单日 4 场的剧烈波动不足以支持调参。
- `PAYOUT_EXPONENT` 曾从 0.5 调到 1/3，因压平分差并放大历史权重影响而当日回退；相关整套赔率加权逻辑于 09-21 删除。

## 2026-09-01（周一）

- 每日完整批次统一为 10:55；已订阅盘口窗口收窄为今天刷新、明天补缺，详情只预拉今天和明天。
- 删除「早间盘口刷新」及默认 / 密刷两套时刻表，只保留「开启密刷」。
- 密刷改为每小时 25 / 55 分全天循环；10:55 在完整批次后顺序执行同刻轻刷。
- 已订阅但关闭密刷时采用 07:00 / 08:05 / 10:55 / 22:00 稀疏时刻表。
- 运维按钮与文案统一为「同步数据 / 更新盘口 / 更新赛果」。
- 「我的」二级页卡片统一分段样式；「我的方案」PC / 手机共用同一张滚动卡。
- 修复详情补包丢失冻结初盘 / 中盘 / 临场：`_collect_prematch_package` 拉取完成后从本地行回填三档。回归 `CollectPackageFrozenBoardTests`。
- 详情单场更新盘口只重算本场分析，不重排日推；日推只在批量盘口后重算。
- AH 候选改为只保留同一主盘中条件命中率较高的一侧；同价交回排序决胜。回归 `test_shallow_board_never_buys_the_lower_probability_side`。
- 分析器让球方向改读 AH 主盘去水概率，删除 1X2 强制翻边路径；盘口解释同步展示两侧概率。
- 陈旧让平自动记录改由 `is_stale_ah_push_row` 同时检查 `auto_lean` 与 `auto_handicap_lean`。
- 详情预测卡标题统一为「赛前结果预测」，胜平负百分比明确标注为主盘去水市场定价。
- AH 模型新增时间留出门禁：仅 log-loss 与 Brier 同时优于盘口基线才可部署；合格模型只修正盘口与模型偏差的一半。
- 删除 AH 日推层重复收缩及无引用的旧多因子函数，`model-status` 区分 artifact 就绪与可部署。
- 胜平负「弱热门」判定增加 `m_gap < _SINGLE_PICK_GAP`，明确热门即使不足五成也走单选。回归 `test_clear_favorite_below_half_still_gets_a_single_pick`。
- 回测否决扩展 AH 档位，分析器和日推继续只取主盘。
- 运维「更新盘口」说明收敛为更新范围与更新结果，并明确不重训模型。
- 联赛默认勾选改为热门 ∪ 当日有可见 `[荐]` 的联赛，避免未勾热门目录联赛隐藏推荐。
- 每比赛日推荐恒定最多 4 场；`MIN_MATCHES_FOR_FULL_QUOTA = 6` 只决定少推是否告警，不放宽上限。
- 日推不足告警改为按 `match_day` 分别统计。
- 未订阅时「立即同步」「更新赛果」「更新盘口」全部禁用，后端接口同步拒绝。
- 记录深盘概率贴近五成的待查问题；09-20 起逐步由死区、深盘可表达性与统一决策链处理。

## 2026-09-20（周日）

- 新增 `ah_market_structure.py` 与水位差死区；死区内盘口只展示、不进日推。
- 曾新增动态让球方水位中位数控制独赢；该路径后于 09-21 确认无调用并删除。
- 曾让分析器 1X2 跟随 AH 穿盘方向；该短路于 09-21 回滚。
- 删除「观望」输出；缺 1X2 时按让球 → 大小 → 双进逐级给出仍有报价的预测。
- 明确每次重挑只展示未开赛 Top 4，开赛后允许补位；已冻结快照保留，所以当日累计可超过 4 注。
- 日推增加大小球、双进降级层与四玩法一致性校验。真源 `recommendation.pipeline`。
- 深盘 AH 曾临时改为取与本场结果同侧的一边；随后收敛到共享的 `bettable_side`。
- 深盘不再产出 1X2 方向；受让侧低水不等于该队赢球。
- 分析器与日推共用 `bettable_side` / `bettable_token`，比分新增 `_align_score_with_handicap` 向真实让球行对齐。
- 删除让球链路中无效的 `score_hint` 参数。回归 `test_deep_board_is_not_a_1x2_direction`、`test_reference_score_never_contradicts_the_handicap_row`。

## 2026-09-21（周一）

- 回滚分析器 1X2 跟 AH 主盘短路：胜平负恢复只读去水 1X2，让球水位仅用于胶着盘裁决。回归 `test_ah_board_never_overrides_the_1x2_board`。
- 新增 `replay_prediction_leans.py`，用市场热门基准线区分代码回归与比赛日爆冷。
- 明确比分是胜平负 × 大小球 × 双进的推导值，不作为独立模型问题调参。
- 大小球方向改为只要有价差就跟低水侧，完全同价才回退启发式。真源 `_resolve_ou_side`，回归 `test_ou_side_follows_a_thin_market_gap`。
- 准确率日期过滤和分桶统一改读持久化 `fixtures.match_day`。回归 `test_accuracy_groups_by_persisted_match_day_not_utc_kickoff_day`。
- 赛果页「每日推荐」改名「当日累计推荐」，明确统计当天所有冻结注数而非屏幕同时显示的 4 场。
- 图表标签与颜色表收敛到 `resultsPageState.RESULTS_HIT_OPTIONS` / `ACCURACY_COLOR_BY_HIT_KEY`。
- AH 门槛曾从 50% 提到 53%，随后由时间留出检验否决并在同日恢复 50%。
- 新增 `audit_sample_power.py`，确认日推样本远少于分析器样本，禁止再以样本内扫阈值作为调参依据。
- 新增 `backtest_ah_confidence.py`，否决改用 AH 盘去水概率替代现行浅盘口径。
- 排序由赔率加权分改为纯校准命中概率，赔率只计算 EV 供审计与同分决胜；删除 `PAYOUT_EXPONENT`。
- 删除无引用的 `allow_moneyline`、动态让球方水位中位数及相关阈值输出。
- 曾给四玩法增加 `EV > 0` 门槛；同日确认市场去水概率下 EV 恒为负并回滚。
- 保留盘口方向闸：同庄家四阶段与同档概率共振形成强 / 弱方向；强逆向淘汰，弱逆向降权并标记。
- 候选与快照新增市场方向、强度、一致性等审计字段。
- 热门联赛球队译名补齐并执行 `audit-team-names` / 回填；修复 `backfill-team-names` 命令注册。
- 订正 Villarreal、Al-Wasl、Shabab Al Ahli Dubai、Neftchi 四支球队译名并补风格回归。
- 补译新热门亚运、墨西哥联、哥伦甲球队，以及热门友谊赛中的青年国家队和俱乐部；热门范围未翻译数归零。
- 回滚 `EV > 0` 后恢复 AH 50%、其余玩法 40% 门槛；5 条相关回归改为禁止 EV 准入。

### 推荐链路整体重构

- 新增 `recommendation_candidate_snapshots`，冻结所有玩法、方向的盘口概率、模型影子概率、版本、赔率、结算分布、EV、方向修正与跳过原因。
- `pre_match_data` 新增每场参考字段，`auto_pick_snapshots` 补齐概率来源、模型 / 校准器版本与方向一致性。
- 删除旧 `recommendation.strategy/calibration/features/feedback`、历史 EMA、联赛软权重与旧候选生成器；`auto_favorites.py` 收敛为统一管线入口。
- 每场参考与星级收敛到 `RecommendationStrength.vue` 同一槽位，明细进入悬停说明。
- 建立双轨概率：线上按玩法门禁选择 `market` / `model`，未过门禁的模型仍输出并冻结影子概率。
- 新增 `shadow_probabilities`、`shadow_cover_probability` 与 `predict_goals(ignore_deployable=True)`，解除“模型不可部署→无训练样本”的反馈自锁。
- 校准器按 `玩法:概率来源` 分键；没有通过验证的键原样透传，不再作为候选准入条件。
- 日推恢复概率与赔率、最低置信度、方向一致性三道闸；按层级和 `校准概率 − 方向惩罚` 排序，EV 不排序、不设门槛。
- 星级改为命中概率绝对分档，恢复 `MIN_MATCHES_FOR_FULL_QUOTA = 6` 告警语义。
- 回放确认市场轨优于强制模型影子轨；当前四玩法继续使用市场基线。
- Top-N 前恢复三件套一致性：AH 以实际投注侧重建胜负方向和比分，无法自洽时降级；非 AH 注的深盘伴随让球行可隐藏。
- `chosen_as_daily_pick` 改按 `(fixture_id, market, direction)` 写入。
- 深盘受让侧设为 `tellable=False`、`skip_reason=deep_board_receiving_side`，继续冻结供审计但不对外推荐。
- 深盘阈值收敛为 `DEEP_AH_LINE`；拆出 `side_speaks_for_result` 与 `outright_win_settles` 两个具名规则，删除重复阈值和 `AhBoardStance.is_deep`。
- 参考比分补齐双进对齐；让球降级后比分不得演示已放弃的穿盘。抽出 `_swap_score_within_shape`。
- 删除遗留调试脚本 `backend/_probe.py`。
- 后端完整测试与前端构建通过；核心回归覆盖双轨隔离、负 EV 仍可推荐、纯概率排序、深盘可表达性与三件套一致性。

## 2026-09-22（周二）

- AH 日推门槛改用 `ranking_score`（校准概率 − 方向惩罚）过 50%；不过闸降到大小球 / 双进同层竞争。
- 大小球与双进在 `MARKET_FALLBACK_TIER` 合为同一层并按调整后概率排序；独赢只在无 AH 盘时兜底。
- 新增回归 `test_direction_penalty_can_demote_a_barely_qualified_ah`、`test_pipeline_falls_from_penalized_ah_to_best_secondary_market`、`test_board_free_match_keeps_1x2_as_the_last_fallback`。
- 盘口快照表新增双进赔率行（`是/赔率`、`否/赔率`），大小球标注为 `大/赔率`、`小/赔率`。
- `hasOddsMarkets` 认可只有双进报价的盘口包。
- 删除遗留调试脚本 `backend/_btts_probe.py`。
- 热门联赛补译英锦联、亚运 U23 与友谊赛青年队共 54 支，并回写 `teams.name`。
