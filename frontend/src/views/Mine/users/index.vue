<script setup lang="ts">
import type { DataTableColumns, FormInst, FormRules } from 'naive-ui'
import { useMessage, useModal } from 'naive-ui'
import { computed, h, onMounted, ref } from 'vue'

import { USER_ROLE_LABEL, type UserRole } from '@/api/auth'
import {
  deleteAdminUser,
  fetchAdminUsers,
  updateAdminUser,
  type AdminUserRow,
} from '@/api/admin'
import { formatLocalDateMinute } from '@/utils/format'
import { useAuthSession } from '@/composables/useAuthSession'
import MineSectionBody from '@/views/Mine/components/MineSectionBody.vue'

defineOptions({ name: 'MineUsers' })

const ASSIGNABLE_ROLES: Exclude<UserRole, 'system_admin'>[] = [
  'ops_admin',
  'vip',
  'user',
]

const message = useMessage()
const modal = useModal()
const { isSystemAdmin } = useAuthSession()
const loading = ref(false)
const users = ref<AdminUserRow[]>([])
const editTarget = ref<AdminUserRow | null>(null)
const editFormRef = ref<FormInst | null>(null)
const editModel = ref({
  role: 'user' as Exclude<UserRole, 'system_admin'>,
  password: '',
  confirm: '',
})
const editSaving = ref(false)
const deletingId = ref<string | null>(null)

const roleOptions = ASSIGNABLE_ROLES.map((role) => ({
  label: USER_ROLE_LABEL[role],
  value: role,
}))

const editRules: FormRules = {
  password: [
    {
      validator: (_rule, value: string) =>
        !value || value.length >= 6 ? true : new Error('密码至少 6 位'),
      trigger: ['blur', 'input'],
    },
  ],
  confirm: [
    {
      validator: (_rule, value: string) => {
        if (!editModel.value.password && !value) return true
        return value === editModel.value.password
          ? true
          : new Error('两次输入的密码不一致')
      },
      trigger: ['blur', 'input'],
    },
  ],
}

const columns = computed<DataTableColumns<AdminUserRow>>(() => [
  { title: '账号', key: 'username', ellipsis: { tooltip: true } },
  {
    title: '角色',
    key: 'role',
    width: 120,
    render: (row) => USER_ROLE_LABEL[row.role] ?? row.role,
  },
  {
    title: '注册时间',
    key: 'created_at',
    width: 150,
    render: (row) => formatLocalDateMinute(row.created_at),
  },
  {
    title: '最近登录时间',
    key: 'last_login_at',
    width: 150,
    render: (row) =>
      row.last_login_at ? formatLocalDateMinute(row.last_login_at) : '尚未登录',
  },
  ...(isSystemAdmin.value
    ? [
        {
          title: '操作',
          key: 'actions',
          width: 120,
          render: (row: AdminUserRow) => {
            const locked = row.role === 'system_admin'
            return h('div', { class: 'user-actions' }, [
              h(
                'button',
                {
                  type: 'button',
                  class: 'user-action',
                  disabled: editSaving.value,
                  onClick: () => openEdit(row),
                },
                '编辑',
              ),
              h(
                'button',
                {
                  type: 'button',
                  class: 'user-action user-action--danger',
                  disabled: locked || deletingId.value === row.id,
                  onClick: () => removeUser(row),
                },
                '删除',
              ),
            ])
          },
        } satisfies DataTableColumns<AdminUserRow>[number],
      ]
    : []),
])

async function loadUsers() {
  loading.value = true
  try {
    users.value = await fetchAdminUsers()
  } catch (err) {
    message.error(err instanceof Error ? err.message : '用户列表加载失败')
  } finally {
    loading.value = false
  }
}

function openEdit(row: AdminUserRow) {
  editTarget.value = row
  editModel.value = {
    role: ASSIGNABLE_ROLES.includes(row.role as Exclude<UserRole, 'system_admin'>)
      ? (row.role as Exclude<UserRole, 'system_admin'>)
      : 'user',
    password: '',
    confirm: '',
  }
}

async function saveEdit() {
  const target = editTarget.value
  if (!target) return
  try {
    await editFormRef.value?.validate()
  } catch {
    return
  }
  const password = editModel.value.password.trim()
  const roleChanged = target.role !== 'system_admin' && editModel.value.role !== target.role
  if (!password && !roleChanged) {
    message.info('没有要保存的修改')
    return
  }
  editSaving.value = true
  try {
    const updated = await updateAdminUser(target.id, {
      ...(roleChanged ? { role: editModel.value.role } : {}),
      ...(password ? { password } : {}),
    })
    users.value = users.value.map((row) => (row.id === updated.id ? updated : row))
    message.success(`已更新 ${updated.username}`)
    editTarget.value = null
  } catch (err) {
    message.error(err instanceof Error ? err.message : '保存失败')
  } finally {
    editSaving.value = false
  }
}

function removeUser(row: AdminUserRow) {
  if (row.role === 'system_admin' || deletingId.value) return
  modal.create({
    preset: 'dialog',
    title: '确认删除账号？',
    type: 'warning',
    content: `删除 ${row.username} 后，该账号的登录、收藏和方案会一并删除。`,
    positiveText: '删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      deletingId.value = row.id
      try {
        await deleteAdminUser(row.id)
        users.value = users.value.filter((item) => item.id !== row.id)
        message.success(`已删除 ${row.username}`)
      } catch (err) {
        message.error(err instanceof Error ? err.message : '删除失败')
      } finally {
        deletingId.value = null
      }
    },
  })
}

onMounted(() => {
  void loadUsers()
})
</script>

<template>
  <MineSectionBody>
    <n-data-table
      :columns="columns"
      :data="users"
      :loading="loading"
      :row-key="(row: AdminUserRow) => row.id"
      :scroll-x="760"
      size="small"
    />

    <n-modal
      :show="editTarget != null"
      preset="card"
      title="编辑账号"
      style="width: min(420px, calc(100vw - 32px));"
      :mask-closable="!editSaving"
      @update:show="(show: boolean) => { if (!show) editTarget = null }"
    >
      <n-form
        ref="editFormRef"
        :model="editModel"
        :rules="editRules"
        label-placement="top"
      >
        <n-form-item label="账号">
          <n-input :value="editTarget?.username ?? ''" disabled />
        </n-form-item>
        <n-form-item label="角色">
          <n-input
            v-if="editTarget?.role === 'system_admin'"
            value="系统管理员"
            disabled
          />
          <n-select
            v-else
            v-model:value="editModel.role"
            :options="roleOptions"
          />
        </n-form-item>
        <n-form-item label="新密码" path="password">
          <n-input
            v-model:value="editModel.password"
            type="password"
            show-password-on="click"
            placeholder="留空则不修改"
          />
        </n-form-item>
        <n-form-item label="确认密码" path="confirm">
          <n-input
            v-model:value="editModel.confirm"
            type="password"
            show-password-on="click"
            placeholder="留空则不修改"
          />
        </n-form-item>
      </n-form>
      <template #footer>
        <n-flex justify="end">
          <n-button :disabled="editSaving" @click="editTarget = null">取消</n-button>
          <n-button type="primary" :loading="editSaving" @click="saveEdit">
            保存
          </n-button>
        </n-flex>
      </template>
    </n-modal>
  </MineSectionBody>
</template>

<style scoped>
:deep(.user-actions) {
  display: flex;
  gap: 8px;
}

:deep(.user-action) {
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--n-primary-color, #18a058);
  cursor: pointer;
  font: inherit;
}

:deep(.user-action:disabled) {
  color: var(--n-text-color-disabled, #c2c2c2);
  cursor: not-allowed;
}

:deep(.user-action--danger) {
  color: var(--n-error-color, #d03050);
}
</style>
