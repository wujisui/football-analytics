<script setup lang="ts">
import { ref, watch } from 'vue'
import type { FormInst, FormRules } from 'naive-ui'
import { useMessage } from 'naive-ui'

import { useAuthSession } from '@/composables/useAuthSession'

const REMEMBER_ACCOUNT_KEY = 'fa-remember-account'

function readRememberedAccount(): string {
  try {
    return localStorage.getItem(REMEMBER_ACCOUNT_KEY)?.trim() || ''
  } catch {
    return ''
  }
}

function writeRememberedAccount(username: string) {
  try {
    const value = username.trim()
    if (value) localStorage.setItem(REMEMBER_ACCOUNT_KEY, value)
    else localStorage.removeItem(REMEMBER_ACCOUNT_KEY)
  } catch {
    /* private mode / quota */
  }
}

function clearRememberedAccount() {
  try {
    localStorage.removeItem(REMEMBER_ACCOUNT_KEY)
  } catch {
    /* ignore */
  }
}

const { loginModalShow, closeLogin, login, register } = useAuthSession()
const message = useMessage()
const formRef = ref<FormInst | null>(null)
const submitting = ref(false)
const mode = ref<'login' | 'register'>('login')
const rememberAccount = ref(!!readRememberedAccount())
const model = ref({
  username: '',
  password: '',
  password2: '',
})

const rules = ref<FormRules>({
  username: {
    required: true,
    message: '请输入账号',
    trigger: ['blur', 'input'],
  },
  password: {
    required: true,
    message: '请输入密码',
    trigger: ['blur', 'input'],
  },
  password2: [
    {
      required: true,
      message: '请再次输入密码',
      trigger: ['blur', 'input'],
    },
    {
      validator: (_rule, value: string) => {
        if (mode.value !== 'register') return true
        return value === model.value.password
      },
      message: '两次密码不一致',
      trigger: ['blur', 'input'],
    },
  ],
})

function resetForm(keepUsername = false) {
  const remembered = keepUsername ? model.value.username || readRememberedAccount() : ''
  model.value = {
    username: keepUsername ? remembered : '',
    password: '',
    password2: '',
  }
  formRef.value?.restoreValidation()
}

function hydrateRememberedAccount() {
  const remembered = readRememberedAccount()
  rememberAccount.value = !!remembered
  if (remembered) model.value.username = remembered
}

watch(loginModalShow, (open) => {
  if (open) hydrateRememberedAccount()
})

function onAfterLeave() {
  resetForm(false)
  submitting.value = false
  mode.value = 'login'
  rememberAccount.value = !!readRememberedAccount()
}

function switchMode(next: 'login' | 'register') {
  mode.value = next
  model.value.password2 = ''
  formRef.value?.restoreValidation()
}

function claimedHint(claimed: {
  favorites: number
  plans: number
}): string {
  const parts: string[] = []
  if (claimed.favorites > 0) parts.push(`${claimed.favorites} 场收藏`)
  if (claimed.plans > 0) parts.push(`${claimed.plans} 个方案`)
  if (!parts.length) return ''
  return `，已迁入本机游客数据（${parts.join('、')}）`
}

async function onSubmit(e?: Event) {
  e?.preventDefault()
  if (submitting.value) return
  try {
    await formRef.value?.validate()
  } catch {
    return
  }
  // login/register closes the modal before its private-cache refresh resolves.
  // Capture fields first: after-leave clears the form while that await is pending.
  const submittedAccount = model.value.username.trim()
  const submittedMode = mode.value
  submitting.value = true
  try {
    const result =
      submittedMode === 'register'
        ? await register(submittedAccount, model.value.password)
        : await login(submittedAccount, model.value.password)
    if (!result.ok) {
      message.error(result.error)
      return
    }
    if (submittedMode === 'register' || rememberAccount.value) {
      writeRememberedAccount(submittedAccount)
      rememberAccount.value = true
    } else {
      clearRememberedAccount()
    }
    const verb = submittedMode === 'register' ? '注册并登录成功' : '登录成功'
    message.success(`${verb}${claimedHint(result.claimed)}`)
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <n-modal
    v-model:show="loginModalShow"
    preset="card"
    :title="mode === 'register' ? '注册' : '登录'"
    to="body"
    :mask-closable="true"
    :closable="true"
    :auto-focus="false"
    :style="{ width: 'min(440px, calc(100vw - 32px))' }"
    :segmented="{ content: true, footer: true }"
    @after-leave="onAfterLeave"
    @update:show="(open) => !open && closeLogin()"
  >
    <n-form
      ref="formRef"
      :model="model"
      :rules="rules"
      label-placement="left"
      label-width="80"
      size="medium"
      @submit.prevent="onSubmit"
    >
      <n-form-item path="username" label="账号">
        <n-input
          v-model:value="model.username"
          placeholder="用户名或邮箱"
          maxlength="128"
          clearable
          autocomplete="username"
        />
      </n-form-item>
      <n-form-item path="password" label="密码">
        <n-input
          v-model:value="model.password"
          type="password"
          show-password-on="click"
          placeholder="至少 6 位"
          maxlength="64"
          autocomplete="current-password"
        />
      </n-form-item>
      <n-form-item v-if="mode === 'register'" path="password2" label="确认密码">
        <n-input
          v-model:value="model.password2"
          type="password"
          show-password-on="click"
          placeholder="再次输入密码"
          maxlength="64"
          autocomplete="new-password"
        />
      </n-form-item>
      <n-form-item v-if="mode === 'login'" :show-label="false" :show-feedback="false">
        <n-checkbox v-model:checked="rememberAccount">记住账号</n-checkbox>
      </n-form-item>
      <!-- Keep submit control inside the form so Enter works from any input. -->
      <button type="submit" hidden tabindex="-1" aria-hidden="true" />
    </n-form>
    <template #footer>
      <n-space justify="space-between" style="width: 100%;">
        <n-button
          quaternary
          type="primary"
          @click="switchMode(mode === 'login' ? 'register' : 'login')"
        >
          {{ mode === 'login' ? '没有账号？注册' : '已有账号？登录' }}
        </n-button>
        <n-space>
          <n-button @click="closeLogin">取消</n-button>
          <n-button type="primary" :loading="submitting" @click="onSubmit">
            {{ mode === 'register' ? '注册' : '登录' }}
          </n-button>
        </n-space>
      </n-space>
    </template>
  </n-modal>
</template>
