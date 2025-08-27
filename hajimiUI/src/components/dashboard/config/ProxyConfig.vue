<script setup>
import { useDashboardStore } from '../../../stores/dashboard'
import { ref, reactive, watch } from 'vue'

const dashboardStore = useDashboardStore()

const localConfig = reactive({
  proxySocks5Enabled: false,
  proxySocks5Host: '',
  proxySocks5Port: 0,
  proxySocks5Username: '',
  proxySocks5Password: '' // 单独输入，不从后端读取
})

const populatedFromStore = ref(false)

watch(
  () => ({
    enabled: dashboardStore.config.proxySocks5Enabled,
    host: dashboardStore.config.proxySocks5Host,
    port: dashboardStore.config.proxySocks5Port,
    username: dashboardStore.config.proxySocks5Username,
    passwordSet: dashboardStore.config.proxySocks5PasswordSet,
    loaded: dashboardStore.isConfigLoaded
  }),
  (v) => {
    if (v.loaded && !populatedFromStore.value) {
      localConfig.proxySocks5Enabled = !!v.enabled
      localConfig.proxySocks5Host = v.host || ''
      localConfig.proxySocks5Port = v.port || 0
      localConfig.proxySocks5Username = v.username || ''
      // 密码不回显，保持空
      populatedFromStore.value = true
    }
  },
  { immediate: true }
)

async function saveComponentConfigs(passwordFromParent) {
  if (!passwordFromParent) {
    return { success: false, message: '代理配置: 密码未提供' }
  }

  let allSucceeded = true
  const messages = []

  // 先更新主机、端口、用户名，最后再启用
  const fieldsBeforeEnable = [
    ['proxySocks5Host', localConfig.proxySocks5Host],
    ['proxySocks5Port', localConfig.proxySocks5Port],
    ['proxySocks5Username', localConfig.proxySocks5Username]
  ]

  for (const [key, val] of fieldsBeforeEnable) {
    if (val !== dashboardStore.config[key]) {
      try {
        await dashboardStore.updateConfig(key, val, passwordFromParent)
        dashboardStore.config[key] = val
        messages.push(`${key} 保存成功`)
      } catch (e) {
        allSucceeded = false
        messages.push(`${key} 保存失败: ${e.message || '未知错误'}`)
      }
    }
  }

  // 密码：仅当用户填写或明确清空时才提交
  if (localConfig.proxySocks5Password !== '') {
    try {
      await dashboardStore.updateConfig('proxySocks5Password', localConfig.proxySocks5Password, passwordFromParent)
      // 置空本地密码框，标记已设置
      localConfig.proxySocks5Password = ''
      dashboardStore.config.proxySocks5PasswordSet = true
      messages.push('代理密码 保存成功')
    } catch (e) {
      allSucceeded = false
      messages.push(`代理密码 保存失败: ${e.message || '未知错误'}`)
    }
  }

  // 最后处理启用/禁用（启用时后端会进行连通性测试）
  if (localConfig.proxySocks5Enabled !== dashboardStore.config.proxySocks5Enabled) {
    try {
      await dashboardStore.updateConfig('proxySocks5Enabled', localConfig.proxySocks5Enabled, passwordFromParent)
      dashboardStore.config.proxySocks5Enabled = localConfig.proxySocks5Enabled
      messages.push(`proxySocks5Enabled 保存成功`)
    } catch (e) {
      allSucceeded = false
      messages.push(`proxySocks5Enabled 保存失败: ${e.message || '未知错误'}`)
    }
  }

  if (allSucceeded && messages.length === 0) {
    return { success: true, message: '代理配置: 无更改需要保存' }
  }

  return { success: allSucceeded, message: `代理配置: ${messages.join('; ')}` }
}

defineExpose({ saveComponentConfigs, localConfig })
</script>

<template>
  <div class="proxy-config">
    <h3 class="section-title">网络代理（SOCKS5）</h3>

    <div class="config-form">
      <div class="config-row">
        <div class="config-group">
          <label class="config-label">启用代理</label>
          <div class="toggle-wrapper">
            <input type="checkbox" class="toggle" id="proxySocks5Enabled" v-model="localConfig.proxySocks5Enabled">
            <label for="proxySocks5Enabled" class="toggle-label">
              <span class="toggle-text">{{ localConfig.proxySocks5Enabled ? '启用' : '禁用' }}</span>
            </label>
          </div>
        </div>
        <div class="config-group">
          <label class="config-label">IP / 主机</label>
          <input type="text" class="config-input" v-model="localConfig.proxySocks5Host" placeholder="例如 127.0.0.1">
        </div>
        <div class="config-group">
          <label class="config-label">端口</label>
          <input type="number" class="config-input" v-model.number="localConfig.proxySocks5Port" min="0" max="65535">
        </div>
      </div>

      <div class="config-row">
        <div class="config-group">
          <label class="config-label">账号（可选）</label>
          <input type="text" class="config-input" v-model="localConfig.proxySocks5Username" placeholder="代理用户名">
        </div>
        <div class="config-group">
          <label class="config-label">密码（不回显）</label>
          <input type="password" class="config-input" v-model="localConfig.proxySocks5Password" placeholder="留空表示不修改">
          <div class="hint" v-if="dashboardStore.config.proxySocks5PasswordSet">已设置密码</div>
        </div>
        <div class="config-group"></div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.section-title {
  color: var(--color-heading);
  border-bottom: 1px solid var(--color-border);
  padding-bottom: 10px;
  margin-bottom: 20px;
  transition: all 0.3s ease;
  position: relative;
  font-weight: 600;
}
.section-title::after {
  content: '';
  position: absolute;
  bottom: -1px;
  left: 0;
  width: 50px;
  height: 2px;
  background: var(--gradient-primary);
}
.config-form { background-color: var(--stats-item-bg); border-radius: var(--radius-lg); padding: 20px; box-shadow: var(--shadow-sm); border: 1px solid var(--card-border); }
.config-row { display: flex; gap: 15px; margin-bottom: 15px; flex-wrap: wrap; }
.config-group { flex: 1; min-width: 160px; }
.config-label { display: block; font-size: 14px; margin-bottom: 5px; color: var(--color-text); font-weight: 500; }
.config-input { width: 100%; padding: 8px 12px; border: 1px solid var(--color-border); border-radius: var(--radius-md); background-color: var(--color-background); color: var(--color-text); font-size: 14px; transition: all 0.3s ease; }
.config-input:focus { outline: none; border-color: var(--button-primary); box-shadow: 0 0 0 2px rgba(79, 70, 229, 0.2); }
.toggle-wrapper { display: flex; align-items: center; gap: 8px; }
.toggle { display: none; }
.toggle-label { cursor: pointer; padding: 6px 12px; border: 1px solid var(--color-border); border-radius: var(--radius-full); background: var(--card-background); }
.toggle-text { font-size: 0.9rem; }
.hint { margin-top: 6px; font-size: 12px; color: var(--color-muted); }
@media (max-width: 768px) { .config-group { min-width: 120px; } }
@media (max-width: 480px) { .config-row { flex-direction: column; } }
</style>
