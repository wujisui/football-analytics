<script setup lang="ts">
import { ref } from 'vue'
import type { FormInst, FormRules } from 'naive-ui'
import { useMessage } from 'naive-ui'

import { useAuthSession } from '@/composables/useAuthSession'

const { loginModalShow, closeLogin, login } = useAuthSession()
const message = useMessage()
const formRef = ref<FormInst | null>(null)
const submitting = ref(false)
const model = ref({
  username: 'admin',
  password: 'admin',
})

const rules: FormRules = {
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
}

function resetForm() {
  model.value = { username: '', password: '' }
  formRef.value?.restoreValidation()
}

function onAfterLeave() {
  resetForm()
  submitting.value = false
}

async function onSubmit(e?: Event) {
  e?.preventDefault()
  try {
    await formRef.value?.validate()
  } catch {
    return
  }
  submitting.value = true
  try {
    // Local session stub until backend /auth is available.
    if (!login(model.value.username)) {
      message.error('登录失败')
      return
    }
    message.success('登录成功')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <n-modal
    v-model:show="loginModalShow"
    preset="card"
    title="登录"
    to="body"
    :mask-closable="true"
    :closable="true"
    display-directive="if"
    :style="{ width: 'min(400px, calc(100vw - 32px))' }"
    :segmented="{ content: true, footer: true }"
    @after-leave="onAfterLeave"
    @update:show="(open) => !open && closeLogin()"
  >
    <n-alert type="info" :bordered="false" style="margin-bottom: 12px;">
      账号体系尚未对接后端，当前为浏览器本地会话（演示登录）。
    </n-alert>
    <n-form
      ref="formRef"
      :model="model"
      :rules="rules"
      label-placement="left"
      label-width="56"
      size="medium"
      @submit.prevent="onSubmit"
    >
      <n-form-item path="username" label="账号">
        <n-input
          v-model:value="model.username"
          placeholder="账号"
          maxlength="64"
          clearable
          autocomplete="username"
        />
      </n-form-item>
      <n-form-item path="password" label="密码">
        <n-input
          v-model:value="model.password"
          type="password"
          show-password-on="click"
          placeholder="密码"
          maxlength="64"
          autocomplete="current-password"
          @keydown.enter="onSubmit"
        />
      </n-form-item>
    </n-form>
    <template #footer>
      <n-space justify="end">
        <n-button @click="closeLogin">取消</n-button>
        <n-button type="primary" :loading="submitting" @click="onSubmit">
          登录
        </n-button>
      </n-space>
    </template>
  </n-modal>
</template>
