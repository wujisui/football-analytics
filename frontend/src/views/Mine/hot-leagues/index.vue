<script setup lang="ts">
import { useMessage, useModal } from 'naive-ui'
import { computed, onMounted, reactive, ref, watch } from 'vue'

import { useIsPhone } from '@/composables/useMediaQuery'
import {
  createCatalogLeague,
  createLeagueCategory,
  deleteCatalogLeague,
  deleteLeagueCategory,
  fetchHotLeaguesSetting,
  lookupOfficialLeague,
  previewCatalogLeagueDelete,
  updateCatalogLeague,
  updateCatalogLeagueCategory,
  updateHotLeaguesSetting,
  type CatalogLeagueDeleteReport,
  type HotLeagueCategory,
  type HotLeagueItem,
  type HotLeaguesSetting,
  type OfficialLeagueLookup,
} from '@/api/admin'

defineOptions({ name: 'MineHotLeagues' })

const message = useMessage()
const modal = useModal()
const isPhone = useIsPhone()
const loading = ref(false)
const reloading = ref(false)
const saving = ref(false)
const catalogBusy = ref(false)
const leagues = ref<HotLeagueItem[]>([])
const categories = ref<HotLeagueCategory[]>([])
const selectedIds = ref<number[]>([])
const defaultIds = ref<number[]>([])
const movingLeagueId = ref<number | null>(null)
const selectedLeagueId = ref<number | null>(null)

const addLeagueShow = ref(false)
const addLookupBusy = ref(false)
const addLookup = ref<OfficialLeagueLookup | null>(null)
const editLeagueShow = ref(false)
const editLookupBusy = ref(false)
const editLookup = ref<OfficialLeagueLookup | null>(null)
const addCategoryShow = ref(false)
const addCategoryName = ref('')
const addLeague = reactive({
  league_id: null as number | null,
  league_name: '',
  country: '',
  category_id: null as number | null,
  selected: false,
})
const editLeague = reactive({
  league_id: null as number | null,
  league_name: '',
  country: '',
  category_id: null as number | null,
  protected: false,
})

watch(
  () => addLeague.league_id,
  () => {
    addLookup.value = null
    addLeague.league_name = ''
    addLeague.country = ''
  },
)

watch(
  () => editLeague.league_id,
  () => {
    if (!editLeagueShow.value) return
    editLookup.value = null
  },
)

const deleteModalShow = ref(false)
const deletePreviewLoading = ref(false)
const deleteSubmitting = ref(false)
const deletePassword = ref('')
const deleteTarget = ref<HotLeagueItem | null>(null)
const deletePreview = ref<CatalogLeagueDeleteReport | null>(null)
const deletePreviewRequestId = ref(0)

const selectedCount = computed(() => selectedIds.value.length)
const busy = computed(
  () =>
    loading.value ||
    reloading.value ||
    saving.value ||
    catalogBusy.value ||
    movingLeagueId.value != null,
)

const categoryOptions = computed(() =>
  categories.value.map((category) => ({
    label: category.category_name,
    value: category.category_id,
  })),
)
const selectedLeague = computed(
  () => leagues.value.find((item) => item.league_id === selectedLeagueId.value) ?? null,
)
const categoryDropdownOptions = computed(() =>
  categories.value.map((category) => ({
    label: category.category_name,
    key: category.category_id,
    disabled: category.category_id === selectedLeague.value?.category_id,
  })),
)

const leagueGroups = computed(() => {
  const selectedSet = new Set(selectedIds.value.map(Number))
  return categories.value.map((category) => ({
    ...category,
    selected: category.leagues.filter((item) => selectedSet.has(item.league_id)).length,
  }))
})

const deleteSummary = computed(() => {
  const report = deletePreview.value
  if (!report) return ''
  return [
    `比赛 ${report.fixtures}`,
    `赛前包 ${report.pre_match_data}`,
    `特征 ${report.match_features}`,
    `日推 ${report.auto_pick_snapshots}`,
    `关注 ${report.favorite_fixtures}`,
    `积分榜 ${report.league_standings}`,
    `快照 ${report.api_snapshots}`,
    `孤立球队 ${report.orphan_teams}`,
  ].join(' · ')
})

const allSelected = computed(
  () => leagues.value.length > 0 && selectedCount.value === leagues.value.length,
)
const toggleSelectLabel = computed(() => (allSelected.value ? '反选' : '全选'))
const toggleSelectType = computed(() => (allSelected.value ? 'warning' : 'info'))

function applySetting(data: HotLeaguesSetting, keepSelection = false) {
  const prevSelected = new Set(selectedIds.value.map(Number))
  const prevLeagueIds = new Set(leagues.value.map((item) => item.league_id))
  leagues.value = data.leagues
  categories.value = data.categories
  if (
    selectedLeagueId.value != null &&
    !data.leagues.some((item) => item.league_id === selectedLeagueId.value)
  ) {
    selectedLeagueId.value = null
  }
  defaultIds.value = [...data.default_league_ids]
  if (!keepSelection) {
    selectedIds.value = [...data.league_ids]
    return
  }
  selectedIds.value = data.leagues
    .filter(
      (item) =>
        prevSelected.has(item.league_id) ||
        (!prevLeagueIds.has(item.league_id) && item.selected),
    )
    .map((item) => item.league_id)
}

async function loadSetting() {
  loading.value = true
  try {
    applySetting(await fetchHotLeaguesSetting())
  } catch (err) {
    message.error(err instanceof Error ? err.message : '读取热门联赛失败')
  } finally {
    loading.value = false
  }
}

async function restoreLastSaved() {
  reloading.value = true
  try {
    applySetting(await fetchHotLeaguesSetting())
  } catch (err) {
    message.error(err instanceof Error ? err.message : '读取热门联赛失败')
  } finally {
    reloading.value = false
  }
}

function restoreDefault() {
  selectedIds.value = [...defaultIds.value]
}

function toggleSelect() {
  if (allSelected.value) invertSelection()
  else selectAll()
}

function selectAll() {
  selectedIds.value = leagues.value.map((item) => item.league_id)
}

function invertSelection() {
  const selected = new Set(selectedIds.value.map(Number))
  selectedIds.value = leagues.value
    .map((item) => item.league_id)
    .filter((id) => !selected.has(id))
}

async function save() {
  saving.value = true
  try {
    applySetting(await updateHotLeaguesSetting(selectedIds.value.map(Number)))
    message.success(
      selectedIds.value.length
        ? `已保存 ${selectedIds.value.length} 项热门，下次定时同步按此拉取盘口`
        : '已保存：热门为空，定时任务将不再拉取赛前盘口',
    )
  } catch (err) {
    message.error(err instanceof Error ? err.message : '保存热门联赛失败')
  } finally {
    saving.value = false
  }
}

function openAddCategory() {
  if (isPhone.value) return
  addCategoryName.value = ''
  addCategoryShow.value = true
}

function closeAddCategory() {
  if (catalogBusy.value) return
  addCategoryShow.value = false
  addCategoryName.value = ''
}

async function submitAddCategory() {
  if (isPhone.value) return
  const name = addCategoryName.value.trim()
  if (!name) {
    message.warning('请填写分类名称')
    return
  }
  catalogBusy.value = true
  try {
    applySetting(await createLeagueCategory(name), true)
    addCategoryShow.value = false
    addCategoryName.value = ''
    message.success('已新增分类')
  } catch (err) {
    message.error(err instanceof Error ? err.message : '新增分类失败')
  } finally {
    catalogBusy.value = false
  }
}

async function confirmRemoveCategory(category: HotLeagueCategory) {
  if (isPhone.value || category.leagues.length) return
  catalogBusy.value = true
  try {
    applySetting(await deleteLeagueCategory(category.category_id), true)
    message.success('已删除空分类')
  } catch (err) {
    message.error(err instanceof Error ? err.message : '删除分类失败')
  } finally {
    catalogBusy.value = false
  }
}

function removeCategory(category: HotLeagueCategory) {
  if (isPhone.value || category.leagues.length || busy.value) return
  modal.create({
    preset: 'dialog',
    title: '确认删除分类？',
    type: 'warning',
    content: `将删除空分类「${category.category_name}」，此操作不可恢复。`,
    positiveText: '确认删除',
    negativeText: '取消',
    autoFocus: false,
    onPositiveClick: () => void confirmRemoveCategory(category),
  })
}

function openAddLeague() {
  if (isPhone.value) return
  addLeague.league_id = null
  addLeague.league_name = ''
  addLeague.country = ''
  addLeague.category_id = categories.value[0]?.category_id ?? null
  addLeague.selected = false
  addLookup.value = null
  addLeagueShow.value = true
}

function closeAddLeague() {
  if (catalogBusy.value || addLookupBusy.value) return
  addLeagueShow.value = false
}

async function lookupAddLeague() {
  if (isPhone.value) return
  const leagueId = addLeague.league_id
  if (!Number.isInteger(leagueId) || leagueId == null || leagueId < 1) {
    message.warning('请填写正整数官方联赛 ID')
    return
  }
  addLookupBusy.value = true
  try {
    const found = await lookupOfficialLeague(leagueId)
    addLookup.value = found
    addLeague.league_name = found.suggested_name
    addLeague.country = found.country
    if (found.in_catalog) {
      message.warning(`ID ${found.league_id} 已在目录中：${found.suggested_name}`)
    } else {
      message.success(
        found.from_cache
          ? `已核对 ${found.official_name}（读自缓存，未消耗配额）`
          : `已核对 ${found.official_name}（本次消耗 1 次官方请求）`,
      )
    }
  } catch (err) {
    addLookup.value = null
    message.error(err instanceof Error ? err.message : '核对官方联赛失败')
  } finally {
    addLookupBusy.value = false
  }
}

function openEditLeague() {
  if (isPhone.value) return
  const item = selectedLeague.value
  if (!item) {
    message.warning('请先点击选中要修改的联赛')
    return
  }
  editLookup.value = null
  editLeague.league_id = item.league_id
  editLeague.league_name = item.league_name
  editLeague.country = item.country ?? ''
  editLeague.category_id = item.category_id
  editLeague.protected = item.protected
  editLeagueShow.value = true
}

function closeEditLeague() {
  if (catalogBusy.value || editLookupBusy.value) return
  editLeagueShow.value = false
}

function editIdChanged(): boolean {
  const item = selectedLeague.value
  return item != null && editLeague.league_id !== item.league_id
}

function editLookupBlocksSave(): boolean {
  if (!editIdChanged()) return false
  const nextId = editLeague.league_id
  const found = editLookup.value
  if (found == null || found.league_id !== nextId) return true
  return found.in_catalog && found.league_id !== selectedLeague.value?.league_id
}

async function lookupEditLeague() {
  if (isPhone.value) return
  const item = selectedLeague.value
  const leagueId = editLeague.league_id
  if (editLeague.protected) return
  if (!Number.isInteger(leagueId) || leagueId == null || leagueId < 1) {
    message.warning('请填写正整数官方联赛 ID')
    return
  }
  editLookupBusy.value = true
  try {
    const found = await lookupOfficialLeague(leagueId)
    editLookup.value = found
    if (item != null && found.league_id !== item.league_id) {
      editLeague.league_name = found.suggested_name
      editLeague.country = found.country
    } else if (!editLeague.country.trim()) {
      editLeague.country = found.country
    }
    if (found.in_catalog && found.league_id !== item?.league_id) {
      message.warning(`ID ${found.league_id} 已在目录中：${found.suggested_name}`)
    } else {
      message.success(
        found.from_cache
          ? `已核对 ${found.official_name}（读自缓存，未消耗配额）`
          : `已核对 ${found.official_name}（本次消耗 1 次官方请求）`,
      )
    }
  } catch (err) {
    editLookup.value = null
    message.error(err instanceof Error ? err.message : '核对官方联赛失败')
  } finally {
    editLookupBusy.value = false
  }
}

async function submitEditLeague() {
  if (isPhone.value) return
  const item = selectedLeague.value
  const nextLeagueId = editLeague.league_id
  const leagueName = editLeague.league_name.trim()
  const country = editLeague.country.trim()
  const categoryId = editLeague.category_id
  if (!item) return
  if (!Number.isInteger(nextLeagueId) || nextLeagueId == null || nextLeagueId < 1) {
    message.warning('请填写正整数官方联赛 ID')
    return
  }
  if (item.protected && nextLeagueId !== item.league_id) {
    message.warning('系统保护联赛不可修改官方 ID')
    return
  }
  if (editIdChanged()) {
    if (editLookup.value?.league_id !== nextLeagueId) {
      message.warning('改官方 ID 请先核对')
      return
    }
    if (editLookup.value.in_catalog && editLookup.value.league_id !== item.league_id) {
      message.warning('该官方联赛 ID 已在目录中')
      return
    }
  }
  if (!leagueName) {
    message.warning('请填写中文名')
    return
  }
  if (!country) {
    message.warning('请填写国家')
    return
  }
  if (categoryId == null) {
    message.warning('请选择分类')
    return
  }
  if (
    nextLeagueId === item.league_id &&
    leagueName === item.league_name &&
    country === (item.country ?? '') &&
    categoryId === item.category_id
  ) {
    editLeagueShow.value = false
    return
  }
  const keepHot = selectedIds.value.includes(item.league_id)
  catalogBusy.value = true
  try {
    applySetting(
      await updateCatalogLeague(item.league_id, {
        league_id: nextLeagueId,
        league_name: leagueName,
        country,
        category_id: categoryId,
      }),
      true,
    )
    if (nextLeagueId !== item.league_id) {
      selectedLeagueId.value = nextLeagueId
      selectedIds.value = selectedIds.value.filter((id) => id !== item.league_id)
      if (keepHot && !selectedIds.value.includes(nextLeagueId)) {
        selectedIds.value = [...selectedIds.value, nextLeagueId]
      }
    }
    editLeagueShow.value = false
    message.success(`已修改「${leagueName}」`)
  } catch (err) {
    message.error(err instanceof Error ? err.message : '修改联赛失败')
  } finally {
    catalogBusy.value = false
  }
}

async function submitAddLeague() {
  if (isPhone.value) return
  const leagueId = addLeague.league_id
  const leagueName = addLeague.league_name.trim()
  const country = addLeague.country.trim()
  const categoryId = addLeague.category_id
  if (!Number.isInteger(leagueId) || leagueId == null || leagueId < 1) {
    message.warning('请填写正整数官方联赛 ID')
    return
  }
  if (addLookup.value?.league_id !== leagueId) {
    message.warning('请先核对官方联赛')
    return
  }
  if (addLookup.value.in_catalog) {
    message.warning('该官方联赛 ID 已在目录中')
    return
  }
  if (!leagueName) {
    message.warning('请填写中文名')
    return
  }
  if (!country) {
    message.warning('请填写国家')
    return
  }
  if (categoryId == null) {
    message.warning('请选择分类')
    return
  }
  catalogBusy.value = true
  try {
    applySetting(
      await createCatalogLeague({
        league_id: leagueId,
        league_name: leagueName,
        country,
        category_id: categoryId,
        selected: addLeague.selected,
      }),
      true,
    )
    addLeagueShow.value = false
    message.success(`已新增「${leagueName}」`)
  } catch (err) {
    message.error(err instanceof Error ? err.message : '新增联赛失败')
  } finally {
    catalogBusy.value = false
  }
}

function selectLeague(item: HotLeagueItem) {
  if (isPhone.value || busy.value) return
  selectedLeagueId.value = item.league_id
}

async function changeSelectedLeagueCategory(categoryId: string | number) {
  const item = selectedLeague.value
  if (!item || isPhone.value || busy.value) return
  const nextCategoryId = Number(categoryId)
  if (!Number.isInteger(nextCategoryId)) return
  if (nextCategoryId === item.category_id) return
  movingLeagueId.value = item.league_id
  try {
    applySetting(await updateCatalogLeagueCategory(item.league_id, nextCategoryId), true)
    message.success(`已调整「${item.league_name}」的分类`)
  } catch (err) {
    message.error(err instanceof Error ? err.message : '调整分类失败')
  } finally {
    movingLeagueId.value = null
  }
}

async function openDeleteLeague(item: HotLeagueItem) {
  if (isPhone.value || item.protected) return
  const requestId = ++deletePreviewRequestId.value
  deleteTarget.value = item
  deletePassword.value = ''
  deletePreview.value = null
  deleteModalShow.value = true
  deletePreviewLoading.value = true
  try {
    const preview = await previewCatalogLeagueDelete(item.league_id)
    if (
      requestId === deletePreviewRequestId.value &&
      deleteTarget.value?.league_id === item.league_id
    ) {
      deletePreview.value = preview
    }
  } catch (err) {
    if (requestId !== deletePreviewRequestId.value) return
    message.error(err instanceof Error ? err.message : '读取删除预览失败')
    deleteModalShow.value = false
    deleteTarget.value = null
  } finally {
    if (requestId === deletePreviewRequestId.value) {
      deletePreviewLoading.value = false
    }
  }
}

function closeDeleteLeague() {
  if (deleteSubmitting.value) return
  deletePreviewRequestId.value += 1
  deleteModalShow.value = false
  deletePassword.value = ''
  deleteTarget.value = null
  deletePreview.value = null
}

async function confirmDeleteLeague() {
  if (isPhone.value) return
  const item = deleteTarget.value
  const password = deletePassword.value.trim()
  if (!item) return
  if (deletePreviewLoading.value || !deletePreview.value) return
  if (!password) {
    message.warning('请输入管理员登录密码')
    return
  }
  deleteSubmitting.value = true
  try {
    const report = await deleteCatalogLeague({
      leagueId: item.league_id,
      password,
      apply: true,
    })
    deletePreview.value = report
    deleteModalShow.value = false
    deletePassword.value = ''
    deleteTarget.value = null
    selectedIds.value = selectedIds.value.filter((id) => id !== item.league_id)
    leagues.value = leagues.value.filter((league) => league.league_id !== item.league_id)
    categories.value = categories.value.map((category) => ({
      ...category,
      leagues: category.leagues.filter((league) => league.league_id !== item.league_id),
    }))
    message.success(`已删除「${report.league_name}」及其关联数据`)
    try {
      applySetting(await fetchHotLeaguesSetting(), true)
    } catch (err) {
      message.warning(err instanceof Error ? err.message : '联赛已删除，目录刷新失败')
    }
  } catch (err) {
    message.error(err instanceof Error ? err.message : '删除联赛失败')
  } finally {
    deleteSubmitting.value = false
  }
}

onMounted(() => {
  void loadSetting()
})
</script>

<template>
  <div class="hot-leagues-panel">
    <n-card
      size="small"
      :bordered="false"
      class="hot-leagues-card"
      content-style="padding: 0; flex: 1; min-height: 0; display: flex; flex-direction: column;"
    >
      <template #header>
        <n-flex :size="8" align="baseline">
          <span>拉盘联赛</span>
          <n-text depth="3" class="hot-league-total">
            {{ selectedCount }}/{{ leagues.length }}
          </n-text>
        </n-flex>
      </template>
      <template #header-extra>
        <n-flex :size="8" :wrap="true">
          <n-button
            v-if="!isPhone"
            size="small"
            secondary
            :disabled="busy || !categories.length"
            @click="openAddLeague"
          >
            新增联赛
          </n-button>
          <n-button
            v-if="!isPhone"
            size="small"
            secondary
            :disabled="busy"
            @click="openAddCategory"
          >
            新增分类
          </n-button>
          <n-button
            v-if="!isPhone"
            size="small"
            secondary
            :disabled="busy || !selectedLeague"
            @click="openEditLeague"
          >
            修改联赛
          </n-button>
          <n-dropdown
            v-if="!isPhone"
            trigger="click"
            :options="categoryDropdownOptions"
            :disabled="busy || !selectedLeague"
            @select="changeSelectedLeagueCategory"
          >
            <n-button
              size="small"
              secondary
              :disabled="busy || !selectedLeague"
              :loading="movingLeagueId != null"
            >
              修改分类
            </n-button>
          </n-dropdown>
          <n-button
            size="small"
            secondary
            :type="toggleSelectType"
            :disabled="busy || !leagues.length"
            @click="toggleSelect"
          >
            {{ toggleSelectLabel }}
          </n-button>
          <n-button
            size="small"
            secondary
            type="success"
            :disabled="busy || !leagues.length"
            :loading="reloading"
            @click="restoreLastSaved"
          >
            恢复
          </n-button>
          <n-button size="small" tertiary :disabled="busy" @click="restoreDefault">
            默认
          </n-button>
          <n-button
            size="small"
            type="primary"
            :disabled="busy"
            :loading="saving"
            @click="save"
          >
            保存
          </n-button>
        </n-flex>
      </template>
      <n-spin :show="loading" class="hot-league-spin">
        <n-scrollbar class="hot-league-scroll" trigger="hover">
          <div class="hot-league-scroll-inner">
            <n-checkbox-group v-model:value="selectedIds">
              <div class="hot-league-groups">
                <section
                  v-for="group in leagueGroups"
                  :key="group.category_id"
                  class="hot-league-group"
                >
                  <div class="hot-league-group-head">
                    <div class="hot-league-group-head-left">
                      <h3 class="hot-league-group-title">
                        {{ group.category_name }}
                        <span class="hot-league-group-count">
                          {{ group.selected }}/{{ group.leagues.length }}
                        </span>
                      </h3>
                      <n-button
                        v-if="!isPhone && !group.leagues.length"
                        size="tiny"
                        tertiary
                        type="error"
                        class="hot-league-delete-btn"
                        :disabled="busy"
                        @click="removeCategory(group)"
                      >
                        删除分类
                      </n-button>
                    </div>
                  </div>
                  <div v-if="group.leagues.length" class="hot-league-grid">
                    <div
                      v-for="item in group.leagues"
                      :key="item.league_id"
                      class="hot-league-item"
                      :class="{
                        'hot-league-item--selected':
                          !isPhone && selectedLeagueId === item.league_id,
                        'hot-league-item--selectable': !isPhone,
                      }"
                      @click="selectLeague(item)"
                    >
                      <n-checkbox
                        :value="item.league_id"
                        :aria-label="`切换 ${item.league_name} 热门状态`"
                        size="large"
                        @click.stop
                      />
                      <n-ellipsis class="hot-league-name">
                        {{ item.league_name }}
                      </n-ellipsis>
                      <n-button
                        v-if="!isPhone && !item.protected"
                        size="tiny"
                        tertiary
                        type="error"
                        class="hot-league-delete-btn"
                        :disabled="busy"
                        @click.stop="openDeleteLeague(item)"
                      >
                        删除
                      </n-button>
                    </div>
                  </div>
                </section>
              </div>
            </n-checkbox-group>
            <n-empty
              v-if="!loading && !categories.length"
              description="目录为空"
              style="padding: 16px 0;"
            />
          </div>
        </n-scrollbar>
      </n-spin>
    </n-card>

    <n-modal
      v-model:show="addCategoryShow"
      preset="card"
      title="新增分类"
      :mask-closable="!catalogBusy"
      :close-on-esc="!catalogBusy"
      style="width: min(400px, 92vw)"
      @update:show="(show: boolean) => !show && closeAddCategory()"
    >
      <n-form-item label="名称" :show-feedback="false">
        <n-input
          v-model:value="addCategoryName"
          maxlength="40"
          show-count
          placeholder="分类名称"
          :disabled="catalogBusy"
          @keyup.enter="submitAddCategory"
        />
      </n-form-item>
      <template #footer>
        <div class="hot-league-modal-footer">
          <n-button :disabled="catalogBusy" @click="closeAddCategory">取消</n-button>
          <n-button
            type="primary"
            :disabled="catalogBusy || !addCategoryName.trim()"
            :loading="catalogBusy"
            @click="submitAddCategory"
          >
            确定
          </n-button>
        </div>
      </template>
    </n-modal>

    <n-modal
      v-model:show="addLeagueShow"
      preset="card"
      title="新增联赛"
      :mask-closable="!catalogBusy && !addLookupBusy"
      :close-on-esc="!catalogBusy && !addLookupBusy"
      style="width: min(440px, 92vw)"
      @update:show="(show: boolean) => !show && closeAddLeague()"
    >
      <n-alert type="info" :bordered="false" style="margin-bottom: 12px">
        填入官方 ID 后先核对：每次未命中缓存消耗 1 次 `GET /leagues?id=`。核对通过后再确认添加。
      </n-alert>
      <n-form-item label="官方 ID" :show-feedback="false">
        <div class="hot-league-id-row">
          <n-input-number
            v-model:value="addLeague.league_id"
            :min="1"
            :precision="0"
            :show-button="false"
            placeholder="正整数"
            class="hot-league-full-input"
            :disabled="catalogBusy || addLookupBusy"
            @keyup.enter="lookupAddLeague"
          />
          <n-button
            :disabled="catalogBusy || addLookupBusy || addLeague.league_id == null"
            :loading="addLookupBusy"
            @click="lookupAddLeague"
          >
            {{ addLookupBusy ? '核对中' : '核对' }}
          </n-button>
        </div>
      </n-form-item>
      <n-alert
        v-if="addLookup"
        :type="addLookup.in_catalog ? 'warning' : 'success'"
        :bordered="false"
        style="margin: 8px 0 12px"
      >
        官方：{{ addLookup.official_name }}（{{ addLookup.country }}
        <template v-if="addLookup.league_type"> · {{ addLookup.league_type }}</template>
        <template v-if="addLookup.season"> · {{ addLookup.season }}</template>
        ）
        {{ addLookup.from_cache ? '已用缓存' : '本次消耗 1 次配额' }}
        <template v-if="addLookup.in_catalog">；该 ID 已在目录中</template>
      </n-alert>
      <n-form-item label="中文名" :show-feedback="false" style="margin-top: 8px">
        <n-input
          v-model:value="addLeague.league_name"
          maxlength="80"
          placeholder="核对后自动填入，可改中文名"
          :disabled="catalogBusy || addLookupBusy || !addLookup"
        />
      </n-form-item>
      <n-form-item label="国家" :show-feedback="false" style="margin-top: 8px">
        <n-input
          v-model:value="addLeague.country"
          maxlength="80"
          placeholder="核对后写入官方国家"
          :disabled="catalogBusy || addLookupBusy || !addLookup"
        />
      </n-form-item>
      <n-form-item label="分类" :show-feedback="false" style="margin-top: 8px">
        <n-select
          v-model:value="addLeague.category_id"
          :options="categoryOptions"
          placeholder="选择分类"
          :disabled="catalogBusy || addLookupBusy || !categoryOptions.length"
        />
      </n-form-item>
      <n-form-item :show-feedback="false" style="margin-top: 8px">
        <n-checkbox v-model:checked="addLeague.selected" :disabled="catalogBusy || addLookupBusy">
          同时设为热门
        </n-checkbox>
      </n-form-item>
      <template #footer>
        <div class="hot-league-modal-footer">
          <n-button :disabled="catalogBusy || addLookupBusy" @click="closeAddLeague">取消</n-button>
          <n-button
            type="primary"
            :disabled="
              catalogBusy ||
              addLookupBusy ||
              !addLookup ||
              addLookup.in_catalog ||
              addLookup.league_id !== addLeague.league_id
            "
            :loading="catalogBusy"
            @click="submitAddLeague"
          >
            确认添加
          </n-button>
        </div>
      </template>
    </n-modal>

    <n-modal
      v-model:show="editLeagueShow"
      preset="card"
      title="修改联赛"
      :mask-closable="!catalogBusy && !editLookupBusy"
      :close-on-esc="!catalogBusy && !editLookupBusy"
      style="width: min(440px, 92vw)"
      @update:show="(show: boolean) => !show && closeEditLeague()"
    >
      <n-alert type="info" :bordered="false" style="margin-bottom: 12px">
        {{
          editLeague.protected
            ? '种子联赛不可改官方 ID。中文名与国家写入数据库目录，同步时不会被官方英文名覆盖。'
            : '改官方 ID 须先核对：未命中缓存消耗 1 次 GET /leagues?id=。改 ID 会丢弃错误 ID 下已拉到的赛程；目标 ID 上已有赛程会保留。'
        }}
      </n-alert>
      <n-form-item label="官方 ID" :show-feedback="false">
        <div class="hot-league-id-row">
          <n-input-number
            v-model:value="editLeague.league_id"
            :min="1"
            :precision="0"
            :show-button="false"
            placeholder="正整数"
            class="hot-league-full-input"
            :disabled="catalogBusy || editLookupBusy || editLeague.protected"
            @keyup.enter="lookupEditLeague"
          />
          <n-button
            v-if="!editLeague.protected"
            :disabled="catalogBusy || editLookupBusy || editLeague.league_id == null"
            :loading="editLookupBusy"
            @click="lookupEditLeague"
          >
            {{ editLookupBusy ? '核对中' : '核对' }}
          </n-button>
        </div>
      </n-form-item>
      <n-alert
        v-if="editLookup"
        :type="
          editLookup.in_catalog && editLookup.league_id !== selectedLeague?.league_id
            ? 'warning'
            : 'success'
        "
        :bordered="false"
        style="margin: 8px 0 12px"
      >
        官方：{{ editLookup.official_name }}（{{ editLookup.country }}
        <template v-if="editLookup.league_type"> · {{ editLookup.league_type }}</template>
        <template v-if="editLookup.season"> · {{ editLookup.season }}</template>
        ）
        {{ editLookup.from_cache ? '已用缓存' : '本次消耗 1 次配额' }}
        <template
          v-if="editLookup.in_catalog && editLookup.league_id !== selectedLeague?.league_id"
        >
          ；该 ID 已在目录中
        </template>
      </n-alert>
      <n-form-item label="中文名" :show-feedback="false" style="margin-top: 8px">
        <n-input
          v-model:value="editLeague.league_name"
          maxlength="80"
          placeholder="联赛中文名"
          :disabled="catalogBusy || editLookupBusy"
        />
      </n-form-item>
      <n-form-item label="国家" :show-feedback="false" style="margin-top: 8px">
        <n-input
          v-model:value="editLeague.country"
          maxlength="80"
          placeholder="官方国家字符串，如 England / World"
          :disabled="catalogBusy || editLookupBusy"
        />
      </n-form-item>
      <n-form-item label="分类" :show-feedback="false" style="margin-top: 8px">
        <n-select
          v-model:value="editLeague.category_id"
          :options="categoryOptions"
          placeholder="选择分类"
          :disabled="catalogBusy || editLookupBusy || !categoryOptions.length"
        />
      </n-form-item>
      <template #footer>
        <div class="hot-league-modal-footer">
          <n-button :disabled="catalogBusy || editLookupBusy" @click="closeEditLeague">取消</n-button>
          <n-button
            type="primary"
            :disabled="catalogBusy || editLookupBusy || editLookupBlocksSave()"
            :loading="catalogBusy"
            @click="submitEditLeague"
          >
            确定
          </n-button>
        </div>
      </template>
    </n-modal>

    <n-modal
      v-model:show="deleteModalShow"
      preset="card"
      title="确认删除联赛？"
      :mask-closable="!deleteSubmitting"
      :close-on-esc="!deleteSubmitting"
      style="width: min(440px, 92vw)"
      @update:show="(show: boolean) => !show && closeDeleteLeague()"
    >
      <n-spin :show="deletePreviewLoading">
        <n-alert type="warning" :bordered="false" style="margin-bottom: 12px">
          不可恢复。将从目录移除该联赛，并删除其赛程、盘口、特征、日推、关注、积分榜与相关快照；已有模型会在下次训练后排除这些样本。
        </n-alert>
        <p
          v-if="deleteTarget"
          style="margin: 0 0 12px; font-size: 13px; line-height: 1.5"
        >
          {{ deleteTarget.league_name }}（ID {{ deleteTarget.league_id }}）
        </p>
        <p v-if="deleteSummary" style="margin: 0 0 12px; font-size: 13px; line-height: 1.5">
          将删除：{{ deleteSummary }}
        </p>
        <n-form-item label="管理员登录密码" :show-feedback="false">
          <n-input
            v-model:value="deletePassword"
            type="password"
            show-password-on="click"
            placeholder="当前登录管理员的密码"
            autocomplete="current-password"
            :disabled="deleteSubmitting || deletePreviewLoading || !deletePreview"
            @keyup.enter="confirmDeleteLeague"
          />
        </n-form-item>
      </n-spin>
      <template #footer>
        <div class="hot-league-modal-footer">
          <n-button :disabled="deleteSubmitting" @click="closeDeleteLeague">取消</n-button>
          <n-button
            type="error"
            :loading="deleteSubmitting"
            :disabled="deletePreviewLoading || !deletePreview || !deletePassword.trim()"
            @click="confirmDeleteLeague"
          >
            确认删除
          </n-button>
        </div>
      </template>
    </n-modal>
  </div>
</template>

<style scoped>
/* 卡片填满 mine-outlet 槽位；表头常驻，溢出只在卡片内容区滚动 */
.hot-leagues-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  padding: var(--fa-content-block-start) var(--fa-content-inline)
    var(--fa-content-block-end);
  box-sizing: border-box;
}

.hot-leagues-card {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
}

.hot-leagues-card :deep(.n-card-header) {
  flex-shrink: 0;
  flex-wrap: wrap;
  gap: 8px;
}

.hot-league-spin {
  flex: 1;
  min-height: 0;
}

.hot-league-spin :deep(.n-spin-content) {
  height: 100%;
}

.hot-league-scroll {
  height: 100%;
}

.hot-league-scroll-inner {
  padding: 4px 12px 12px;
}

.hot-league-total {
  font-size: 13px;
  font-weight: 400;
}

.hot-league-groups {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.hot-league-group-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 0 8px;
}

.hot-league-group-head-left {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.hot-league-group-title {
  margin: 0;
  font-size: 14px;
  font-weight: 500;
  opacity: 0.85;
}

.hot-league-group-count {
  margin-left: 8px;
  font-weight: 400;
  opacity: 0.65;
}

.hot-league-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px 12px;
}

@media (min-width: 768px) {
  .hot-league-grid {
    grid-template-columns: repeat(6, minmax(0, 1fr));
  }
}

.hot-league-item {
  display: flex;
  align-items: center;
  gap: 4px;
  min-width: 0;
  padding: 1px 3px;
  border: 1px solid transparent;
  border-radius: 6px;
}

.hot-league-item--selectable {
  cursor: pointer;
}

.hot-league-item--selectable:hover {
  background: color-mix(in srgb, var(--n-primary-color, #18a058) 8%, transparent);
}

.hot-league-item--selected {
  border-color: var(--n-primary-color, #18a058);
  background: color-mix(in srgb, var(--n-primary-color, #18a058) 14%, transparent);
}

.hot-league-item :deep(.n-checkbox) {
  flex-shrink: 0;
}

/* n-ellipsis root has no parent scope id — reach it through :deep. */
.hot-league-item :deep(.hot-league-name) {
  flex: 1 1 auto;
  min-width: 0;
  max-width: 100%;
}

.hot-league-delete-btn {
  flex-shrink: 0;
}

@media (hover: hover) {
  .hot-league-delete-btn {
    opacity: 0;
    pointer-events: none;
  }

  .hot-league-group-head:hover .hot-league-delete-btn,
  .hot-league-group-head:focus-within .hot-league-delete-btn,
  .hot-league-item:hover .hot-league-delete-btn,
  .hot-league-item:focus-within .hot-league-delete-btn {
    opacity: 1;
    pointer-events: auto;
  }
}

.hot-league-full-input {
  width: 100%;
}

.hot-league-id-row {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
}

.hot-league-id-row .hot-league-full-input {
  flex: 1;
  min-width: 0;
}

.hot-league-modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  flex-wrap: wrap;
}
</style>
