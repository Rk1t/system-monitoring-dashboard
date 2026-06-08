<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

const nodes = ref([])
const selectedNode = ref(null)
const selectedNodeId = ref(null)
const current = ref(null)
const history = ref([])
const summary = ref(null)
const analysis = ref(null)
const diagnostics = ref(null)
const hardware = ref(null)
const processSnapshot = ref(null)
const appConfig = ref(null)
const authUser = ref(null)
const enrollmentKeys = ref([])
const createdEnrollmentKey = ref(null)
const keysError = ref('')
const keysMessage = ref('')
const manualCopyKey = ref('')
const organizationMembers = ref([])
const membersError = ref('')
const isMembersLoading = ref(false)
const isCreatingMember = ref(false)
const newMemberForm = ref({
  username: '',
  password: '',
  role: 'viewer'
})
const isDownloadModalOpen = ref(false)
const isDownloadingAgent = ref(false)
const downloadError = ref('')
const downloadForm = ref({
  platform_type: 'windows_desktop',
  enrollment_key_id: '',
  enrollment_key: ''
})
const downloadPlatformOptions = [
  {
    type: 'windows_desktop',
    title: 'Windows',
    description: 'Обычный пользовательский Windows-ПК. Один exe-файл, запуск двойным кликом.',
    package: 'agent-windows.exe',
    command: 'agent-windows.exe'
  },
  {
    type: 'windows_server',
    title: 'Windows Server',
    description: 'Серверный Windows-вариант. Отдельный exe для дальнейшей установки как служба.',
    package: 'agent-windows-server.exe',
    command: 'agent-windows-server.exe'
  },
  {
    type: 'linux_gui',
    title: 'Linux GUI',
    description: 'Обычный Linux с рабочим окружением. Один исполняемый файл в консольном режиме.',
    package: 'agent-linux-gui',
    command: './agent-linux-gui'
  },
  {
    type: 'linux_server',
    title: 'Linux Server',
    description: 'Серверный Linux без графического интерфейса. Отдельный исполняемый файл для серверного сценария.',
    package: 'agent-linux-server',
    command: './agent-linux-server'
  }
]
const editNode = ref(null)
const editNodeForm = ref({ name: '', description: '' })
const isKeysLoading = ref(false)
const isCreatingKey = ref(false)
const includeArchived = ref(false)
const isRedfishModalOpen = ref(false)
const redfishForm = ref({
  name: '',
  source_type: 'idrac',
  management_ip: '',
  username: 'root',
  password: 'password',
  use_mock: true
})
const newKeyForm = ref({
  name: 'Windows-серверы',
  max_uses: 10,
  expires_days: 30
})
const loginForm = ref({
  username: 'admin',
  password: 'admin123'
})
const details = ref({
  info: null,
  cpu: null,
  memory: null,
  disks: [],
  network: [],
  processes: []
})

const activePage = ref('systems')
const selectedHistoryLimit = ref(50)
const isOptimizedView = ref(true)
const isComparisonMode = ref(false)
const error = ref('')
const nodesError = ref('')
const refreshError = ref('')
const detailsError = ref('')
const diagnosticsError = ref('')
const hardwareError = ref('')
const processSnapshotError = ref('')
const loginError = ref('')
const isAddingSource = ref(false)
const isLoading = ref(false)
const isInitialLoading = ref(false)
const isBackgroundRefreshing = ref(false)
const isNodesLoading = ref(true)
const isDetailsLoading = ref(false)
const isLoginLoading = ref(false)
let nodesTimerId = null
let overviewTimerId = null
let detailsTimerId = null
let currentOverviewIntervalMs = 3000

let apiBase = ''
if (import.meta.env.VITE_API_BASE) {
  apiBase = import.meta.env.VITE_API_BASE
}
const tokenStorageKey = 'system-monitor-access-token'
const enrollmentKeyStorageKey = 'system-monitor-open-enrollment-keys'
let savedToken = ''
const tokenFromStorage = localStorage.getItem(tokenStorageKey)
if (tokenFromStorage) {
  savedToken = tokenFromStorage
}
const accessToken = ref(savedToken)
const revealedEnrollmentKeys = ref({})
const historyLimitOptions = [20, 50, 100, 200]
const sourceHistoryLimit = 200

const sourceTypeLabels = {
  local: 'Локальная система',
  agent: 'Агент мониторинга',
  ilo: 'HPE iLO',
  idrac: 'Dell iDRAC'
}

const roleLabels = {
  owner: 'владелец',
  admin: 'администратор',
  viewer: 'наблюдатель'
}

const statusLabels = {
  online: 'в сети',
  offline: 'не в сети',
  archived: 'архив',
  alert: 'тревога',
  warning: 'предупреждение',
  critical: 'критично'
}

const bottleneckLabels = {
  cpu: 'CPU',
  ram: 'RAM',
  disk: 'Диск',
  network: 'Сеть',
  combined: 'несколько компонентов',
  none: 'не выявлено',
  hardware: 'аппаратная часть',
  temperature: 'температура',
  fans: 'вентиляторы',
  power: 'питание'
}

const metricHints = {
  cpu: {
    title: 'CPU',
    description: 'Показывает загрузку процессора в процентах.',
    reasons: 'Высокая нагрузка часто возникает из-за тяжелых программ, фоновых обновлений или большого числа процессов.',
    advice: 'Проверьте список процессов и закройте лишние приложения.'
  },
  ram: {
    title: 'RAM',
    description: 'Показывает долю используемой оперативной памяти.',
    reasons: 'Рост RAM связан с браузером, IDE, виртуальными машинами или утечками памяти.',
    advice: 'Проверьте процессы по RAM и перезапустите подозрительные приложения.'
  },
  disk: {
    title: 'Диск',
    description: 'Показывает заполненность основного диска.',
    reasons: 'Высокое значение появляется при нехватке свободного места, временных файлах или больших архивах.',
    advice: 'Очистите временные файлы и проверьте самые крупные папки.'
  },
  network: {
    title: 'Сеть',
    description: 'Показывает текущую скорость приема и передачи данных.',
    reasons: 'Скачивания, синхронизация облака и обновления могут резко увеличить трафик.',
    advice: 'Проверьте активные приложения и сетевые интерфейсы.'
  }
}

const selectedNodeSourceLabel = computed(() => {
  if (!selectedNode.value) {
    return sourceTypeLabel('')
  }
  return sourceTypeLabel(selectedNode.value.source_type)
})

const isHardwareSource = computed(() => {
  if (!selectedNode.value) {
    return false
  }
  if (selectedNode.value.source_type === 'ilo') {
    return true
  }
  if (selectedNode.value.source_type === 'idrac') {
    return true
  }
  return false
})

const isLocalNode = computed(() => {
  if (!selectedNode.value) {
    return false
  }
  return selectedNode.value.source_type === 'local'
})

const selectedOrganization = computed(() => {
  if (!authUser.value) {
    return null
  }
  if (!authUser.value.organizations) {
    return null
  }
  if (authUser.value.organizations.length === 0) {
    return null
  }
  return authUser.value.organizations[0]
})

const canManageNodes = computed(() => {
  if (!selectedOrganization.value) {
    return false
  }
  if (selectedOrganization.value.role === 'owner') {
    return true
  }
  if (selectedOrganization.value.role === 'admin') {
    return true
  }
  return false
})

const canManageUsers = computed(() => {
  if (!selectedOrganization.value) {
    return false
  }
  if (selectedOrganization.value.role === 'owner') {
    return true
  }
  if (selectedOrganization.value.role === 'admin') {
    return true
  }
  return false
})

const isOwner = computed(() => {
  if (!selectedOrganization.value) {
    return false
  }
  return selectedOrganization.value.role === 'owner'
})

const activeEnrollmentKeys = computed(() => {
  const result = []
  for (const key of enrollmentKeys.value) {
    if (key.is_active) {
      result.push(key)
    }
  }
  return result
})
const statusMessage = computed(() => {
  if (error.value) {
    return error.value
  }
  if (nodesError.value) {
    return nodesError.value
  }
  if (refreshError.value) {
    return refreshError.value
  }
  if (isBackgroundRefreshing.value) {
    return 'Фоновое обновление...'
  }
  if (activePage.value === 'keys') {
    return 'Мониторинг активен'
  }
  if (activePage.value === 'users') {
    return 'Мониторинг активен'
  }
  return `Обновлено: ${lastUpdated.value}`
})

const pageTitle = computed(() => {
  if (!authUser.value) {
    return 'Вход в систему'
  }
  if (activePage.value === 'systems') {
    return 'Контролируемые системы'
  }
  if (activePage.value === 'details') {
    return 'Подробные метрики'
  }
  if (activePage.value === 'keys') {
    return 'Ключи подключения'
  }
  if (activePage.value === 'users') {
    return 'Пользователи'
  }
  return 'Мониторинг узла'
})

const warnings = computed(() => {
  const result = []
  let cpuValue = 0
  let ramValue = 0
  let diskValue = 0
  if (current.value) {
    cpuValue = Number(current.value.cpu_percent)
    ramValue = Number(current.value.ram_percent)
    diskValue = Number(current.value.disk_percent)
  }

  if (cpuValue > 85) {
    result.push('CPU выше 85%. Проверьте процессы с высокой загрузкой.')
  }
  if (ramValue > 90) {
    result.push('RAM выше 90%. Возможно, системе не хватает оперативной памяти.')
  }
  if (diskValue > 95) {
    result.push('Диск выше 95%. Освободите место на системном диске.')
  }
  return result
})

const cpuOptimizedHistory = computed(() => downsampleMetrics(history.value, selectedHistoryLimit.value))
const ramOptimizedHistory = computed(() => downsampleMetrics(history.value, selectedHistoryLimit.value))
const cpuDisplayedHistory = computed(() => {
  if (isOptimizedView.value) {
    return cpuOptimizedHistory.value
  }
  return history.value
})

const ramDisplayedHistory = computed(() => {
  if (isOptimizedView.value) {
    return ramOptimizedHistory.value
  }
  return history.value
})

const pointsReductionPercent = computed(() => {
  if (!history.value.length) {
    return 0
  }
  let displayedCount = cpuDisplayedHistory.value.length
  if (ramDisplayedHistory.value.length > displayedCount) {
    displayedCount = ramDisplayedHistory.value.length
  }

  const percent = Math.round((1 - displayedCount / history.value.length) * 100)
  if (percent < 0) {
    return 0
  }
  return percent
})

const displayedPointsCount = computed(() => {
  if (cpuDisplayedHistory.value.length > ramDisplayedHistory.value.length) {
    return cpuDisplayedHistory.value.length
  }
  return ramDisplayedHistory.value.length
})

const refreshIntervalMs = computed(() => {
  let seconds = 3
  if (appConfig.value) {
    if (appConfig.value.frontend_refresh_interval_seconds) {
      seconds = appConfig.value.frontend_refresh_interval_seconds
    }
  }
  if (analysis.value) {
    if (analysis.value.current_refresh_interval) {
      seconds = analysis.value.current_refresh_interval
    }
  }
  return seconds * 1000
})

const lastUpdated = computed(() => {
  if (activePage.value === 'systems') {
    if (nodesError.value) {
      return 'ошибка подключения'
    }
    return 'список систем'
  }
  if (activePage.value === 'keys') {
    return 'служебный раздел'
  }
  if (activePage.value === 'users') {
    return 'служебный раздел'
  }
  if (!current.value) {
    return 'нет данных'
  }
  if (!current.value.timestamp) {
    return 'нет данных'
  }
  return new Date(current.value.timestamp).toLocaleTimeString('ru-RU')
})

function sourceTypeLabel(sourceType) {
  if (sourceTypeLabels[sourceType]) {
    return sourceTypeLabels[sourceType]
  }
  if (sourceType) {
    return sourceType
  }
  return 'Неизвестно'
}

function roleLabel(role) {
  if (roleLabels[role]) {
    return roleLabels[role]
  }
  if (role) {
    return role
  }
  return 'роль не задана'
}

function statusLabel(status) {
  let statusText = ''
  if (status) {
    statusText = String(status).toLowerCase()
  }
  if (statusLabels[statusText]) {
    return statusLabels[statusText]
  }
  if (status) {
    return status
  }
  return 'нет статуса'
}

function bottleneckLabel(component) {
  if (bottleneckLabels[component]) {
    return bottleneckLabels[component]
  }
  if (component) {
    return component
  }
  return 'нет данных'
}

function analysisBottleneckTitle(bottleneck) {
  if (!bottleneck) {
    return 'Анализ выполняется'
  }
  if (bottleneck.metric === 'none') {
    return 'Узкое место не выявлено'
  }
  let metric = ''
  if (bottleneck.metric) {
    metric = String(bottleneck.metric).toLowerCase()
  }
  return `Предполагаемое узкое место: ${bottleneckLabel(metric)}`
}

function formatDateTime(value) {
  if (!value) {
    return 'нет данных'
  }
  return new Date(value).toLocaleString('ru-RU')
}

function statusBadgeClass(status) {
  let value = 'offline'
  if (status) {
    value = String(status).toLowerCase()
  }
  if (value.includes('archive')) {
    return 'archived'
  }
  if (value.includes('critical')) {
    return 'critical'
  }
  if (value.includes('alert')) {
    return 'critical'
  }
  if (value.includes('warning')) {
    return 'warning'
  }
  if (value.includes('online')) {
    return 'online'
  }
  return 'offline'
}

function nodeHealthText(node) {
  if (node.is_archived) {
    return 'Узел архивирован, новые данные скрыты из основного списка.'
  }
  let score = 0
  if (node.health_score) {
    score = Number(node.health_score)
  }
  if (score >= 85) {
    return 'Состояние стабильное, критичных признаков нет.'
  }
  if (score >= 60) {
    return 'Есть признаки нагрузки, стоит наблюдать за динамикой.'
  }
  return 'Требуется внимание: индекс состояния снижен.'
}

function severityClass(value) {
  if (value) {
    return `severity-${value}`
  }
  return 'severity-normal'
}

function getStoredEnrollmentKeys() {
  try {
    const rawValue = localStorage.getItem(enrollmentKeyStorageKey)
    if (!rawValue) {
      return {}
    }
    return JSON.parse(rawValue)
  } catch (storageError) {
    return {}
  }
}

function storeOpenEnrollmentKey(keyData) {
  const storedKeys = getStoredEnrollmentKeys()
  storedKeys[keyData.id] = keyData.key
  localStorage.setItem(enrollmentKeyStorageKey, JSON.stringify(storedKeys))

  const newRevealState = {}
  for (const keyId in revealedEnrollmentKeys.value) {
    newRevealState[keyId] = revealedEnrollmentKeys.value[keyId]
  }
  newRevealState[keyData.id] = true
  revealedEnrollmentKeys.value = newRevealState
}

function getOpenEnrollmentKey(keyId) {
  const storedKeys = getStoredEnrollmentKeys()
  if (storedKeys[keyId]) {
    return storedKeys[keyId]
  }
  return ''
}

function forgetOpenEnrollmentKey(keyId) {
  const storedKeys = getStoredEnrollmentKeys()
  delete storedKeys[keyId]
  localStorage.setItem(enrollmentKeyStorageKey, JSON.stringify(storedKeys))

  const newRevealState = {}
  for (const revealKeyId in revealedEnrollmentKeys.value) {
    if (Number(revealKeyId) !== Number(keyId)) {
      newRevealState[revealKeyId] = revealedEnrollmentKeys.value[revealKeyId]
    }
  }
  revealedEnrollmentKeys.value = newRevealState
}

function maskedEnrollmentKey(key) {
  const storedKey = getOpenEnrollmentKey(key.id)
  if (revealedEnrollmentKeys.value[key.id] && storedKey) {
    return storedKey
  }
  let prefix = 'smk_enroll'
  if (key.prefix) {
    prefix = key.prefix
  }
  return `${prefix}_********`
}

function revealEnrollmentKey(key) {
  if (!getOpenEnrollmentKey(key.id)) {
    keysError.value = 'Открытый ключ недоступен в этом браузере. Создайте новый ключ подключения.'
    keysMessage.value = ''
    return
  }
  keysError.value = ''
  keysMessage.value = ''
  const newRevealState = {}
  for (const keyId in revealedEnrollmentKeys.value) {
    newRevealState[keyId] = revealedEnrollmentKeys.value[keyId]
  }
  newRevealState[key.id] = !revealedEnrollmentKeys.value[key.id]
  revealedEnrollmentKeys.value = newRevealState
}

async function copyEnrollmentKey(key) {
  const storedKey = getOpenEnrollmentKey(key.id)
  if (!storedKey) {
    keysError.value = 'Открытый ключ недоступен в этом браузере. Создайте новый ключ подключения.'
    keysMessage.value = ''
    manualCopyKey.value = ''
    return
  }

  try {
    copyTextFallback(storedKey)
    keysError.value = ''
    keysMessage.value = 'Ключ подключения скопирован в буфер обмена.'
    manualCopyKey.value = ''
  } catch {
    try {
      await navigator.clipboard.writeText(storedKey)
      keysError.value = ''
      keysMessage.value = 'Ключ подключения скопирован в буфер обмена.'
      manualCopyKey.value = ''
    } catch {
      keysMessage.value = ''
      manualCopyKey.value = storedKey
      const newRevealState = {}
      for (const keyId in revealedEnrollmentKeys.value) {
        newRevealState[keyId] = revealedEnrollmentKeys.value[keyId]
      }
      newRevealState[key.id] = true
      revealedEnrollmentKeys.value = newRevealState
      keysError.value = 'Браузер заблокировал автокопирование. Выделите ключ ниже и нажмите Ctrl+C.'
    }
  }
}

function copyTextFallback(text) {
  const textarea = document.createElement('textarea')
  textarea.value = text
  textarea.setAttribute('readonly', '')
  textarea.style.position = 'fixed'
  textarea.style.left = '-9999px'
  textarea.style.top = '0'
  document.body.appendChild(textarea)
  textarea.focus()
  textarea.select()
  const copied = document.execCommand('copy')
  document.body.removeChild(textarea)
  if (!copied) {
    throw new Error('copy failed')
  }
}

function mergeMetricHistory(currentItems, incomingItems, limit) {
  if (!Array.isArray(incomingItems)) {
    return currentItems
  }
  if (incomingItems.length === 0) {
    return currentItems
  }
  if (!Array.isArray(currentItems)) {
    return takeLastItems(incomingItems, limit)
  }
  if (currentItems.length === 0) {
    return takeLastItems(incomingItems, limit)
  }

  const knownTimestamps = {}
  for (const item of currentItems) {
    knownTimestamps[item.timestamp] = true
  }

  const merged = []
  for (const item of currentItems) {
    merged.push(item)
  }

  for (const item of incomingItems) {
    if (!knownTimestamps[item.timestamp]) {
      merged.push(item)
      knownTimestamps[item.timestamp] = true
    }
  }

  merged.sort(compareMetricTime)
  return takeLastItems(merged, limit)
}

function takeLastItems(items, limit) {
  const result = []
  let startIndex = items.length - limit
  if (startIndex < 0) {
    startIndex = 0
  }
  for (let index = startIndex; index < items.length; index += 1) {
    result.push(items[index])
  }
  return result
}

function compareMetricTime(left, right) {
  const leftTime = new Date(left.timestamp).getTime()
  const rightTime = new Date(right.timestamp).getTime()
  return leftTime - rightTime
}

function downsampleMetrics(data, targetCount) {
  if (!Array.isArray(data)) {
    return []
  }
  if (data.length <= targetCount) {
    const result = []
    for (let index = 0; index < data.length; index += 1) {
      const item = {}
      for (const key in data[index]) {
        item[key] = data[index][key]
      }
      item._chartIndex = index
      result.push(item)
    }
    return result
  }

  const result = []
  const lastIndex = data.length - 1
  const step = lastIndex / (targetCount - 1)

  for (let pointNumber = 0; pointNumber < targetCount; pointNumber += 1) {
    let sourceIndex = Math.round(pointNumber * step)

    if (pointNumber === 0) {
      sourceIndex = 0
    }
    if (pointNumber === targetCount - 1) {
      sourceIndex = lastIndex
    }

    const item = {}
    for (const key in data[sourceIndex]) {
      item[key] = data[sourceIndex][key]
    }
    item._chartIndex = sourceIndex
    result.push(item)
  }

  return result
}

function formatPercent(value) {
  let numberValue = 0
  if (value) {
    numberValue = Number(value)
  }
  return `${numberValue.toFixed(1)}%`
}

function formatBytes(value) {
  const units = ['Б', 'КБ', 'МБ', 'ГБ', 'ТБ']
  let size = 0
  if (value) {
    size = Number(value)
  }
  let unitIndex = 0

  while (size >= 1024) {
    if (unitIndex >= units.length - 1) {
      break
    }
    size /= 1024
    unitIndex += 1
  }

  let fixedSize = size.toFixed(1)
  if (size >= 10) {
    fixedSize = size.toFixed(0)
  }
  return `${fixedSize} ${units[unitIndex]}`
}

function formatSpeed(value) {
  return `${formatBytes(value)}/с`
}

function chartPointsFor(items, field, fixedWindow = false) {
  if (items.length === 0) {
    return ''
  }

  const points = []
  for (let index = 0; index < items.length; index += 1) {
    const item = items[index]
    let chartIndex = index
    if (item._chartIndex !== undefined) {
      chartIndex = item._chartIndex
    }

    let x = 100
    if (fixedWindow) {
      let divider = sourceHistoryLimit - 1
      if (divider < 1) {
        divider = 1
      }
      x = (chartIndex / divider) * 100
    } else if (items.length > 1) {
      x = (index / (items.length - 1)) * 100
    }

    let metricValue = 0
    if (item[field]) {
      metricValue = Number(item[field])
    }
    const y = 100 - metricValue
    points.push(`${x},${y}`)
  }

  return points.join(' ')
}

function chartPoints(field) {
  let items = cpuDisplayedHistory.value
  if (field === 'ram_percent') {
    items = ramDisplayedHistory.value
  }
  return chartPointsFor(items, field, true)
}

async function apiFetch(url, options = {}) {
  const headers = {}
  if (options.headers) {
    for (const key in options.headers) {
      headers[key] = options.headers[key]
    }
  }

  if (accessToken.value) {
    headers.Authorization = `Bearer ${accessToken.value}`
  }

  const requestOptions = {}
  for (const key in options) {
    requestOptions[key] = options[key]
  }
  requestOptions.headers = headers

  const response = await fetch(url, requestOptions)

  if (response.status === 401) {
    logout()
    throw new Error('Требуется авторизация')
  }

  return response
}

function startDataTimers() {
  window.clearInterval(nodesTimerId)
  window.clearInterval(detailsTimerId)
  nodesTimerId = window.setInterval(loadNodes, 7000)
  detailsTimerId = window.setInterval(function () {
    if (activePage.value !== 'details') {
      return
    }
    if (!isLocalNode.value) {
      return
    }
    loadDetails()
  }, 5000)
}

function stopDataTimers() {
  window.clearInterval(nodesTimerId)
  window.clearInterval(overviewTimerId)
  window.clearInterval(detailsTimerId)
}

async function login() {
  isLoginLoading.value = true
  loginError.value = ''
  try {
    const response = await fetch(`${apiBase}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(loginForm.value)
    })
    if (!response.ok) {
      throw new Error('Неверный логин или пароль')
    }

    const data = await response.json()
    accessToken.value = data.access_token
    authUser.value = data.user
    localStorage.setItem(tokenStorageKey, data.access_token)
    setAppState({ page: 'systems' }, true)
    isNodesLoading.value = true
    await loadNodes()
    window.removeEventListener('popstate', handlePopState)
    window.addEventListener('popstate', handlePopState)
    startDataTimers()
  } catch (requestError) {
    loginError.value = 'Не удалось войти. Проверьте логин и пароль.'
  } finally {
    isLoginLoading.value = false
  }
}

async function loadCurrentUser() {
  if (!accessToken.value) {
    return
  }

  try {
    const response = await apiFetch(`${apiBase}/api/auth/me`)
    if (!response.ok) {
      throw new Error('Не удалось получить пользователя')
    }
    authUser.value = await response.json()
  } catch (requestError) {
    logout()
  }
}

function logout() {
  stopDataTimers()
  localStorage.removeItem(tokenStorageKey)
  accessToken.value = ''
  authUser.value = null
  nodes.value = []
  goToSystems(false)
  isNodesLoading.value = false
}

function trendLabel(metricName) {
  let trend = 'stable'
  if (analysis.value) {
    if (analysis.value.trends) {
      if (analysis.value.trends[metricName]) {
        trend = analysis.value.trends[metricName]
      }
    }
  }

  if (trend === 'growing') {
    return '↑ растет'
  }
  if (trend === 'falling') {
    return '↓ снижается'
  }
  return '→ стабильно'
}

function trendClass(metricName) {
  let trend = 'stable'
  if (analysis.value) {
    if (analysis.value.trends) {
      if (analysis.value.trends[metricName]) {
        trend = analysis.value.trends[metricName]
      }
    }
  }
  return `trend-${trend}`
}

function hasAnomaly(metricName) {
  const names = {
    cpu: 'CPU',
    ram: 'RAM',
    network: 'Network'
  }

  if (!analysis.value) {
    return false
  }
  if (!analysis.value.anomalies) {
    return false
  }

  for (const item of analysis.value.anomalies) {
    if (item.metric === names[metricName]) {
      return true
    }
  }
  return false
}

function metricClass(metricName) {
  let isWarning = false
  if (metricName === 'cpu') {
    if (current.value) {
      if (current.value.cpu_percent > 85) {
        isWarning = true
      }
    }
  }
  if (metricName === 'ram') {
    if (current.value) {
      if (current.value.ram_percent > 90) {
        isWarning = true
      }
    }
  }
  if (metricName === 'disk') {
    if (current.value) {
      if (current.value.disk_percent > 95) {
        isWarning = true
      }
    }
  }

  return {
    warning: isWarning,
    anomaly: hasAnomaly(metricName)
  }
}

function stateLabel(value) {
  const labels = {
    normal: 'норма',
    warning: 'предупреждение',
    critical: 'критическое состояние',
    unstable: 'нестабильно',
    degraded: 'устойчивая нагрузка',
    recovery: 'восстановление'
  }
  if (labels[value]) {
    return labels[value]
  }
  if (value) {
    return value
  }
  return 'нет данных'
}

function scenarioLabel(value) {
  const labels = {
    idle: 'спокойный режим',
    cpu_bound: 'нагрузка на CPU',
    memory_pressure: 'давление на память',
    disk_pressure: 'нагрузка на диск',
    network_activity: 'сетевая активность',
    hardware_monitoring: 'аппаратный мониторинг',
    mixed_overload: 'смешанная нагрузка'
  }
  if (labels[value]) {
    return labels[value]
  }
  if (value) {
    return value
  }
  return 'нет данных'
}

function healthStatusLabel(value) {
  const labels = {
    good: 'хорошее',
    moderate: 'умеренная нагрузка',
    problem: 'проблемное состояние',
    warning: 'предупреждение',
    critical: 'критично',
    normal: 'норма'
  }
  if (labels[value]) {
    return labels[value]
  }
  if (value) {
    return value
  }
  return 'нет данных'
}

function translateTelemetryText(text) {
  if (!text) {
    return ''
  }
  return String(text)
    .replaceAll('Network', 'Сеть')
    .replaceAll('Disk', 'Диск')
    .replaceAll('combined', 'несколько компонентов')
    .replaceAll('hardware', 'аппаратная часть')
    .replaceAll('temperature', 'температура')
    .replaceAll('fans', 'вентиляторы')
    .replaceAll('power', 'питание')
}

function hardwareValueLabel(value) {
  const labels = {
    On: 'включено',
    Off: 'выключено',
    OK: 'норма',
    Warning: 'предупреждение',
    Critical: 'критично'
  }
  if (labels[value]) {
    return labels[value]
  }
  if (value) {
    return value
  }
  return '...'
}

function processReasonLabel(value) {
  const labels = {
    cpu_high: 'высокая загрузка CPU',
    ram_high: 'высокая загрузка RAM',
    combined_high: 'высокая загрузка CPU и RAM'
  }
  if (labels[value]) {
    return labels[value]
  }
  if (value) {
    return value
  }
  return 'нет данных'
}

function findNodeById(nodeId) {
  for (const node of nodes.value) {
    if (node.id === nodeId) {
      return node
    }
  }
  return null
}

async function loadConfig() {
  const response = await fetch(`${apiBase}/api/app/config`)
  if (response.ok) {
    appConfig.value = await response.json()
  }
}

async function loadNodes() {
  if (!authUser.value) {
    return
  }

  try {
    const response = await apiFetch(`${apiBase}/api/nodes?include_archived=${includeArchived.value}`)
    if (!response.ok) {
      throw new Error('Сервер вернул ошибку')
    }

    nodes.value = await response.json()
    nodesError.value = ''

    if (selectedNodeId.value) {
      const freshNode = findNodeById(selectedNodeId.value)
      if (!freshNode) {
        goToSystems()
        nodesError.value = 'Выбранный узел не найден. Выполнен возврат к списку систем.'
      } else {
        selectedNode.value = freshNode
      }
    }
  } catch (requestError) {
    nodesError.value = 'Не удалось загрузить список подключенных систем'
  } finally {
    isNodesLoading.value = false
  }
}

function setAppState(state, replace = false) {
  if (state.page === 'node') {
    if (state.activePage) {
      activePage.value = state.activePage
    } else {
      activePage.value = 'overview'
    }
    selectedNodeId.value = state.nodeId
    const node = findNodeById(state.nodeId)
    if (node) {
      selectedNode.value = node
    }
  } else {
    if (state.page) {
      activePage.value = state.page
    } else {
      activePage.value = 'systems'
    }
    selectedNode.value = null
    selectedNodeId.value = null
  }

  let browserPage = activePage.value
  if (state.page) {
    browserPage = state.page
  }
  const browserState = {
    page: browserPage,
    activePage: activePage.value,
    nodeId: selectedNodeId.value
  }

  let url = '#systems'
  if (browserState.page === 'node') {
    if (browserState.nodeId) {
      url = `#node-${browserState.nodeId}`
    }
  } else {
    if (browserState.page) {
      url = `#${browserState.page}`
    }
  }

  if (replace) {
    window.history.replaceState(browserState, '', url)
  } else {
    window.history.pushState(browserState, '', url)
  }
}

async function loadEnrollmentKeys() {
  if (!authUser.value) {
    return
  }
  isKeysLoading.value = true
  try {
    const response = await apiFetch(`${apiBase}/api/enrollment-keys`)
    if (!response.ok) {
      throw new Error('Не удалось загрузить ключи')
    }
    enrollmentKeys.value = await response.json()
    keysError.value = ''
    keysMessage.value = ''
    manualCopyKey.value = ''
  } catch (requestError) {
    keysError.value = 'Не удалось загрузить ключи подключения'
    keysMessage.value = ''
    manualCopyKey.value = ''
  } finally {
    isKeysLoading.value = false
  }
}

async function createEnrollmentKey() {
  isCreatingKey.value = true
  try {
    const response = await apiFetch(`${apiBase}/api/enrollment-keys`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(newKeyForm.value)
    })
    if (!response.ok) {
      throw new Error('Не удалось создать ключ')
    }
    createdEnrollmentKey.value = await response.json()
    storeOpenEnrollmentKey(createdEnrollmentKey.value)
    await loadEnrollmentKeys()
    keysError.value = ''
    keysMessage.value = 'Ключ подключения создан и сохранен локально в этом браузере.'
    manualCopyKey.value = ''
  } catch (requestError) {
    keysError.value = 'Не удалось создать ключ подключения'
    keysMessage.value = ''
    manualCopyKey.value = ''
  } finally {
    isCreatingKey.value = false
  }
}

async function revokeEnrollmentKey(keyId) {
  try {
    const response = await apiFetch(`${apiBase}/api/enrollment-keys/${keyId}/revoke`, {
      method: 'POST'
    })
    if (!response.ok) {
      throw new Error('Не удалось отозвать ключ')
    }
    await loadEnrollmentKeys()
    keysMessage.value = 'Ключ подключения отозван.'
    manualCopyKey.value = ''
  } catch (requestError) {
    keysError.value = 'Не удалось отозвать ключ'
    keysMessage.value = ''
    manualCopyKey.value = ''
  }
}

async function deleteEnrollmentKey(key) {
  const confirmed = window.confirm(`Удалить ключ "${key.name}"? Эта запись исчезнет из списка.`)
  if (!confirmed) {
    return
  }

  try {
    const response = await apiFetch(`${apiBase}/api/enrollment-keys/${key.id}`, {
      method: 'DELETE'
    })
    if (!response.ok) {
      throw new Error('Не удалось удалить ключ')
    }
    forgetOpenEnrollmentKey(key.id)
    if (createdEnrollmentKey.value && createdEnrollmentKey.value.id === key.id) {
      createdEnrollmentKey.value = null
    }
    await loadEnrollmentKeys()
    keysMessage.value = 'Ключ подключения удален.'
    keysError.value = ''
    manualCopyKey.value = ''
  } catch (requestError) {
    keysError.value = 'Не удалось удалить ключ подключения'
    keysMessage.value = ''
    manualCopyKey.value = ''
  }
}

async function loadOrganizationMembers() {
  if (!authUser.value) {
    return
  }
  if (!canManageUsers.value) {
    return
  }
  isMembersLoading.value = true
  try {
    const response = await apiFetch(`${apiBase}/api/organization/members`)
    if (!response.ok) {
      throw new Error('Не удалось загрузить участников')
    }
    organizationMembers.value = await response.json()
    membersError.value = ''
  } catch (requestError) {
    membersError.value = 'Не удалось загрузить участников организации'
  } finally {
    isMembersLoading.value = false
  }
}

async function createOrganizationMember() {
  isCreatingMember.value = true
  try {
    const response = await apiFetch(`${apiBase}/api/organization/members`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(newMemberForm.value)
    })
    if (!response.ok) {
      throw new Error('Не удалось добавить пользователя')
    }
    newMemberForm.value = { username: '', password: '', role: 'viewer' }
    await loadOrganizationMembers()
    membersError.value = ''
  } catch (requestError) {
    membersError.value = 'Не удалось добавить пользователя. Проверьте username, пароль и роль.'
  } finally {
    isCreatingMember.value = false
  }
}

async function updateOrganizationMemberRole(member, role) {
  try {
    const response = await apiFetch(`${apiBase}/api/organization/members/${member.user_id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ role })
    })
    if (!response.ok) {
      throw new Error('Не удалось изменить роль')
    }
    await loadOrganizationMembers()
    membersError.value = ''
  } catch (requestError) {
    membersError.value = 'Не удалось изменить роль участника'
  }
}

async function deleteOrganizationMember(member) {
  if (!window.confirm('Участник будет удален из организации, но аккаунт пользователя останется. Продолжить?')) {
    return
  }
  try {
    const response = await apiFetch(`${apiBase}/api/organization/members/${member.user_id}`, {
      method: 'DELETE'
    })
    if (!response.ok) {
      throw new Error('Не удалось удалить участника')
    }
    await loadOrganizationMembers()
    membersError.value = ''
  } catch (requestError) {
    membersError.value = 'Не удалось удалить участника организации'
  }
}

async function transferOwnership(member) {
  const confirmText = `Передать роль владельца пользователю ${member.username}? Текущий владелец станет администратором.`
  if (!window.confirm(confirmText)) {
    return
  }
  try {
    const response = await apiFetch(`${apiBase}/api/organization/transfer-ownership`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: member.user_id })
    })
    if (!response.ok) {
      throw new Error('Не удалось передать владение')
    }
    organizationMembers.value = await response.json()
    await loadCurrentUser()
    membersError.value = ''
  } catch (requestError) {
    membersError.value = 'Не удалось передать владение организацией'
  }
}

async function openDownloadModal() {
  downloadError.value = ''
  downloadForm.value = {
    platform_type: 'windows_desktop',
    enrollment_key_id: '',
    enrollment_key: ''
  }
  isDownloadModalOpen.value = true
  await loadEnrollmentKeys()
  if (activeEnrollmentKeys.value.length) {
    downloadForm.value.enrollment_key_id = activeEnrollmentKeys.value[0].id
    downloadForm.value.enrollment_key = getOpenEnrollmentKey(activeEnrollmentKeys.value[0].id)
  }
}

function closeDownloadModal() {
  isDownloadModalOpen.value = false
  downloadError.value = ''
  downloadForm.value.enrollment_key = ''
}

function fillDownloadKeyFromStorage() {
  downloadForm.value.enrollment_key = getOpenEnrollmentKey(downloadForm.value.enrollment_key_id)
}

async function downloadAgentPackage() {
  if (!downloadForm.value.enrollment_key_id) {
    downloadError.value = 'Выберите запись ключа подключения.'
    return
  }

  const openKey = downloadForm.value.enrollment_key.trim()
  if (!openKey) {
    downloadError.value = 'Выберите запись ключа и вставьте открытый ключ подключения.'
    return
  }

  isDownloadingAgent.value = true
  downloadError.value = ''
  try {
    const endpoint = '/api/downloads/agent'
    const response = await apiFetch(`${apiBase}${endpoint}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        platform_type: downloadForm.value.platform_type,
        enrollment_key_id: Number(downloadForm.value.enrollment_key_id),
        enrollment_key: openKey
      })
    })
    if (!response.ok) {
      let message = 'Не удалось скачать агент'
      try {
        const data = await response.json()
        if (data.detail) {
          message = data.detail
        }
      } catch {
        const text = await response.text()
        if (text) {
          message = text
        }
      }
      throw new Error(message)
    }

    const blob = await response.blob()
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    let disposition = ''
    const dispositionHeader = response.headers.get('Content-Disposition')
    if (dispositionHeader) {
      disposition = dispositionHeader
    }
    link.href = url
    let downloadFileName = `MonitoringAgent-${downloadForm.value.platform_type}.zip`
    const fileNameStart = disposition.indexOf('filename="')
    if (fileNameStart >= 0) {
      let fileName = disposition.substring(fileNameStart + 10)
      const fileNameEnd = fileName.indexOf('"')
      if (fileNameEnd >= 0) {
        fileName = fileName.substring(0, fileNameEnd)
      }
      if (fileName) {
        downloadFileName = fileName
      }
    }
    link.download = downloadFileName
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(url)
    closeDownloadModal()
  } catch (requestError) {
    if (requestError.message) {
      downloadError.value = requestError.message
    } else {
      downloadError.value = 'Не удалось скачать файл агента. Проверьте выбранный ключ и наличие собранного файла агента.'
    }
  } finally {
    isDownloadingAgent.value = false
  }
}

function startEditNode(node) {
  let name = ''
  let description = ''
  if (node.name) {
    name = node.name
  }
  if (node.description) {
    description = node.description
  }
  editNode.value = node
  editNodeForm.value = {
    name,
    description
  }
}

function closeEditNode() {
  editNode.value = null
  editNodeForm.value = { name: '', description: '' }
}

async function saveNodeEdit() {
  if (!editNode.value) {
    return
  }
  try {
    const response = await apiFetch(`${apiBase}/api/nodes/${editNode.value.id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(editNodeForm.value)
    })
    if (!response.ok) {
      if (response.status === 403) {
        throw new Error('Недостаточно прав')
      }
      throw new Error('Не удалось обновить узел')
    }
    const updatedNode = await response.json()
    if (selectedNodeId.value === updatedNode.id) {
      selectedNode.value = updatedNode
    }
    await loadNodes()
    closeEditNode()
  } catch (requestError) {
    if (requestError.message) {
      nodesError.value = requestError.message
    } else {
      nodesError.value = 'Не удалось обновить узел'
    }
  }
}

async function archiveNode(node) {
  if (!window.confirm('Узел будет скрыт из основного списка, история сохранится. Продолжить?')) {
    return
  }
  await postNodeAction(node, 'archive')
}

async function restoreNode(node) {
  const restoredNode = await postNodeAction(node, 'restore')
  if (restoredNode) {
    if (selectedNodeId.value === restoredNode.id) {
      selectedNode.value = restoredNode
    }
  }
}

async function refreshNode(node) {
  const refreshResult = await postNodeAction(node, 'refresh')
  if (!refreshResult) {
    return
  }
  if (selectedNodeId.value === node.id) {
    if (isHardwareSource.value) {
      await loadHardwareStatus()
    } else {
      await loadOverview({ initial: false })
    }
  }
}

async function clearNodeHistory(node) {
  if (!window.confirm('Будут удалены метрики и snapshots выбранного узла. Узел останется. Продолжить?')) {
    return
  }
  await postNodeAction(node, 'clear-history')
  if (selectedNodeId.value === node.id) {
    clearSelectedMetrics()
    if (isHardwareSource.value) {
      hardware.value = null
      diagnostics.value = null
    }
  }
}

async function postNodeAction(node, action) {
  try {
    const response = await apiFetch(`${apiBase}/api/nodes/${node.id}/${action}`, {
      method: 'POST'
    })
    if (!response.ok) {
      if (response.status === 403) {
        throw new Error('Недостаточно прав')
      }
      throw new Error('Операция не выполнена')
    }
    const payload = await response.json()
    await loadNodes()
    if (action === 'archive') {
      if (selectedNodeId.value === node.id) {
        const archivedNode = {}
        for (const key in selectedNode.value) {
          archivedNode[key] = selectedNode.value[key]
        }
        archivedNode.is_archived = true
        archivedNode.status = 'archived'
        selectedNode.value = archivedNode
      }
    }
    return payload
  } catch (requestError) {
    if (requestError.message) {
      nodesError.value = requestError.message
    } else {
      nodesError.value = 'Операция не выполнена'
    }
    return null
  }
}

async function loadHardwareStatus() {
  if (!selectedNodeId.value) {
    return
  }
  if (!isHardwareSource.value) {
    return
  }

  try {
    const limit = sourceHistoryLimit
    const hardwareResponse = await apiFetch(`${apiBase}/api/nodes/${selectedNodeId.value}/hardware/latest`)
    const diagnosticsResponse = await apiFetch(`${apiBase}/api/nodes/${selectedNodeId.value}/diagnostics?limit=${limit}`)

    if (!hardwareResponse.ok) {
      throw new Error('Аппаратные метрики недоступны')
    }

    hardware.value = await hardwareResponse.json()
    if (diagnosticsResponse.ok) {
      diagnostics.value = await diagnosticsResponse.json()
      diagnosticsError.value = ''
    } else {
      diagnosticsError.value = 'Диагностика временно недоступна'
    }
    hardwareError.value = ''
  } catch (requestError) {
    hardwareError.value = 'Аппаратное состояние временно недоступно'
  }
}

async function pollRedfishNode() {
  if (!selectedNodeId.value) {
    return
  }
  if (!isHardwareSource.value) {
    return
  }

  try {
    const response = await apiFetch(`${apiBase}/api/nodes/${selectedNodeId.value}/poll-redfish`, {
      method: 'POST'
    })
    if (!response.ok) {
      throw new Error('Не удалось выполнить Redfish-опрос')
    }
    await loadHardwareStatus()
    await loadNodes()
  } catch (requestError) {
    hardwareError.value = 'Не удалось выполнить Redfish-опрос'
  }
}

function openRedfishModal(sourceType) {
  let name = 'HPE-SERVER-01'
  let managementIp = '192.168.1.101'
  let username = 'Administrator'

  if (sourceType === 'idrac') {
    name = 'DELL-SERVER-01'
    managementIp = '192.168.1.100'
    username = 'root'
  }

  redfishForm.value = {
    name,
    source_type: sourceType,
    management_ip: managementIp,
    username,
    password: 'password',
    use_mock: true
  }
  nodesError.value = ''
  isRedfishModalOpen.value = true
}

function closeRedfishModal() {
  isRedfishModalOpen.value = false
}

async function submitRedfishSource() {
  isAddingSource.value = true
  try {
    const response = await apiFetch(`${apiBase}/api/nodes/redfish`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(redfishForm.value)
    })
    if (!response.ok) {
      throw new Error('Не удалось добавить Redfish-источник')
    }
    await loadNodes()
    nodesError.value = ''
    closeRedfishModal()
  } catch (requestError) {
    nodesError.value = 'Не удалось добавить Redfish-источник'
  } finally {
    isAddingSource.value = false
  }
}

async function loadOverview(options = {}) {
  if (!selectedNodeId.value) {
    return
  }
  if (isHardwareSource.value) {
    return
  }

  let initial = false
  if (options.initial !== undefined) {
    initial = options.initial
  } else if (!current.value) {
    initial = true
  }

  isInitialLoading.value = initial
  isLoading.value = initial
  isBackgroundRefreshing.value = !initial
  refreshError.value = ''
  try {
    const limit = sourceHistoryLimit
    const nodeId = selectedNodeId.value
    const currentResponse = await apiFetch(`${apiBase}/api/nodes/${nodeId}/metrics/current`)
    const historyResponse = await apiFetch(`${apiBase}/api/nodes/${nodeId}/metrics/history?limit=${limit}`)
    const summaryResponse = await apiFetch(`${apiBase}/api/nodes/${nodeId}/metrics/summary?limit=${limit}`)
    const analysisResponse = await apiFetch(`${apiBase}/api/nodes/${nodeId}/analysis/summary?limit=${limit}`)
    const diagnosticsResponse = await apiFetch(`${apiBase}/api/nodes/${nodeId}/diagnostics?limit=${limit}`)
    const processSnapshotResponse = await apiFetch(`${apiBase}/api/nodes/${nodeId}/process-snapshots/latest`)

    let nodeNotFound = false
    if (currentResponse.status === 404) {
      nodeNotFound = true
    }
    if (historyResponse.status === 404) {
      nodeNotFound = true
    }

    if (nodeNotFound) {
      goToSystems()
      nodesError.value = 'Выбранный узел не найден или для него пока нет метрик.'
      return
    }

    let mainResponsesOk = true
    if (!currentResponse.ok) {
      mainResponsesOk = false
    }
    if (!historyResponse.ok) {
      mainResponsesOk = false
    }
    if (!summaryResponse.ok) {
      mainResponsesOk = false
    }
    if (!analysisResponse.ok) {
      mainResponsesOk = false
    }

    if (!mainResponsesOk) {
      throw new Error('Сервер вернул ошибку')
    }

    current.value = await currentResponse.json()
    const incomingHistory = await historyResponse.json()
    if (initial) {
      history.value = takeLastItems(incomingHistory, sourceHistoryLimit)
    } else {
      history.value = mergeMetricHistory(history.value, incomingHistory, sourceHistoryLimit)
    }

    summary.value = await summaryResponse.json()
    analysis.value = await analysisResponse.json()
    if (diagnosticsResponse.ok) {
      diagnostics.value = await diagnosticsResponse.json()
      diagnosticsError.value = ''
    } else if (!diagnostics.value) {
      diagnosticsError.value = 'Диагностика временно недоступна'
    }
    if (processSnapshotResponse.ok) {
      processSnapshot.value = await processSnapshotResponse.json()
      processSnapshotError.value = ''
    } else if (!processSnapshot.value) {
      processSnapshotError.value = 'Снимков процессов пока нет'
    }
    applyAdaptiveRefreshInterval()
    error.value = ''
  } catch (requestError) {
    if (initial) {
      refreshError.value = 'Нет подключения к центральному серверу мониторинга'
    } else {
      refreshError.value = 'Не удалось обновить данные, показаны последние значения'
    }

    if (initial) {
      error.value = refreshError.value
    }
  } finally {
    isLoading.value = false
    isInitialLoading.value = false
    isBackgroundRefreshing.value = false
  }
}

async function loadDetails() {
  if (!isLocalNode.value) {
    return
  }

  isDetailsLoading.value = true
  try {
    const info = await apiFetch(`${apiBase}/api/system/info`)
    const cpu = await apiFetch(`${apiBase}/api/system/cpu`)
    const memory = await apiFetch(`${apiBase}/api/system/memory`)
    const disks = await apiFetch(`${apiBase}/api/system/disks`)
    const network = await apiFetch(`${apiBase}/api/system/network`)
    const processes = await apiFetch(`${apiBase}/api/system/processes?limit=10&sort=cpu`)

    let allResponsesOk = true
    const responses = [info, cpu, memory, disks, network, processes]
    for (const response of responses) {
      if (!response.ok) {
        allResponsesOk = false
      }
    }

    if (!allResponsesOk) {
      throw new Error('Сервер вернул ошибку')
    }

    details.value = {
      info: await info.json(),
      cpu: await cpu.json(),
      memory: await memory.json(),
      disks: await disks.json(),
      network: await network.json(),
      processes: await processes.json()
    }
    detailsError.value = ''
  } catch (requestError) {
    detailsError.value = 'Не удалось загрузить подробные метрики'
  } finally {
    isDetailsLoading.value = false
  }
}

function clearSelectedMetrics() {
  current.value = null
  history.value = []
  summary.value = null
  analysis.value = null
  diagnostics.value = null
  hardware.value = null
  processSnapshot.value = null
  diagnosticsError.value = ''
  hardwareError.value = ''
  processSnapshotError.value = ''
  detailsError.value = ''
}

function restartOverviewTimer() {
  window.clearInterval(overviewTimerId)
  if (!selectedNodeId.value) {
    return
  }
  if (isHardwareSource.value) {
    return
  }
  overviewTimerId = window.setInterval(function () {
    loadOverview({ initial: false })
  }, refreshIntervalMs.value)
  currentOverviewIntervalMs = refreshIntervalMs.value
}

function applyAdaptiveRefreshInterval() {
  if (refreshIntervalMs.value !== currentOverviewIntervalMs) {
    restartOverviewTimer()
  }
}

function openNode(node, pushHistory = true) {
  selectedNode.value = node
  selectedNodeId.value = node.id
  activePage.value = 'overview'
  error.value = ''
  refreshError.value = ''
  clearSelectedMetrics()
  window.clearInterval(overviewTimerId)
  if (pushHistory) {
    setAppState({ page: 'node', nodeId: node.id, activePage: 'overview' })
  }

  let hardwareNode = false
  if (node.source_type === 'ilo') {
    hardwareNode = true
  }
  if (node.source_type === 'idrac') {
    hardwareNode = true
  }

  if (hardwareNode) {
    loadHardwareStatus()
  } else {
    loadOverview({ initial: true })
    restartOverviewTimer()
  }
}

function goToSystems(pushHistory = true) {
  activePage.value = 'systems'
  selectedNode.value = null
  selectedNodeId.value = null
  clearSelectedMetrics()
  window.clearInterval(overviewTimerId)
  if (pushHistory) {
    setAppState({ page: 'systems' })
  }
}

function switchPage(pageName, pushHistory = true) {
  activePage.value = pageName
  let nodePage = false
  if (pageName === 'overview') {
    nodePage = true
  }
  if (pageName === 'details') {
    nodePage = true
  }

  if (selectedNodeId.value) {
    if (!nodePage) {
      nodePage = false
    }
  }

  if (selectedNodeId.value && nodePage) {
    if (pushHistory) {
      setAppState({ page: 'node', nodeId: selectedNodeId.value, activePage: pageName })
    }
  } else if (pushHistory) {
    setAppState({ page: pageName })
  }
  if (pageName === 'details') {
    loadDetails()
  }
  if (pageName === 'keys') {
    loadEnrollmentKeys()
  }
  if (pageName === 'users') {
    loadOrganizationMembers()
  }
}

async function handlePopState(event) {
  if (!authUser.value) {
    return
  }
  let state = event.state
  if (!state) {
    state = { page: 'systems' }
  }

  if (state.page === 'node') {
    if (!state.nodeId) {
      goToSystems(false)
      return
    }
    let node = findNodeById(state.nodeId)
    if (!node) {
      await loadNodes()
      node = findNodeById(state.nodeId)
    }
    if (node) {
      openNode(node, false)
      if (state.activePage === 'details') {
        switchPage('details', false)
      }
      return
    }
  }
  if (state.page === 'keys') {
    switchPage('keys', false)
    return
  }
  if (state.page === 'users') {
    switchPage('users', false)
    return
  }
  goToSystems(false)
}

onMounted(async () => {
  try {
    await loadConfig()
  } catch (configError) {
    appConfig.value = { frontend_refresh_interval_seconds: 3 }
  }

  await loadCurrentUser()
  if (authUser.value) {
    await loadNodes()
    window.history.replaceState({ page: 'systems' }, '', '#systems')
    window.addEventListener('popstate', handlePopState)
    startDataTimers()
  } else {
    isNodesLoading.value = false
  }
})

onBeforeUnmount(() => {
  stopDataTimers()
  window.removeEventListener('popstate', handlePopState)
})
</script>

<template>
  <main class="page">
    <section class="topbar">
      <div class="topbar-title">
        <p class="eyebrow">Централизованный мониторинг</p>
        <h1>{{ pageTitle }}</h1>
      </div>
      <div v-if="authUser" class="topbar-workspace">
        <nav class="topbar-nav" aria-label="Основная навигация">
          <button type="button" :class="{ active: activePage === 'systems' }" @click="goToSystems">Системы</button>
          <button v-if="canManageNodes" type="button" :class="{ active: activePage === 'keys' }" @click="switchPage('keys')">Ключи</button>
          <button v-if="canManageUsers" type="button" :class="{ active: activePage === 'users' }" @click="switchPage('users')">Пользователи</button>
        </nav>

        <div class="topbar-actions">
          <button v-if="canManageNodes" type="button" @click="openDownloadModal">Скачать агент</button>
          <button type="button">Инструкция</button>
        </div>

        <div class="topbar-user">
          <div class="status" :class="{ offline: error || nodesError || refreshError, refreshing: isBackgroundRefreshing }">
            <span class="status-dot"></span>
            <span>{{ statusMessage }}</span>
          </div>
          <div class="user-card">
            <strong>{{ authUser.username }}</strong>
            <span>{{ selectedOrganization?.name || 'организация не выбрана' }} · {{ roleLabel(selectedOrganization?.role) }}</span>
          </div>
          <button type="button" class="logout-button" @click="logout">Выйти</button>
        </div>
      </div>
    </section>

    <section v-if="authUser && isDownloadModalOpen" class="modal-backdrop" aria-label="Центр скачивания агента">
      <div class="modal-panel">
        <div class="panel-heading">
          <div>
            <h2>Скачать агент</h2>
            <span>Скачивается готовый файл агента. Если файл не собран, сервер покажет понятную ошибку.</span>
          </div>
          <button type="button" class="back-button" @click="closeDownloadModal">Закрыть</button>
        </div>

        <div v-if="downloadError" class="alert compact-alert">{{ downloadError }}</div>

        <div v-if="!activeEnrollmentKeys.length" class="empty-panel compact-empty">
          <p>Сначала создайте ключ подключения.</p>
          <button type="button" @click="switchPage('keys'); closeDownloadModal()">Перейти к ключам</button>
        </div>

        <form v-else class="download-form" @submit.prevent="downloadAgentPackage">
          <div class="download-platform-grid">
            <label
              v-for="option in downloadPlatformOptions"
              :key="option.type"
              class="download-platform-card"
              :class="{ selected: downloadForm.platform_type === option.type }"
            >
              <input v-model="downloadForm.platform_type" type="radio" :value="option.type" />
              <span class="download-card-title">{{ option.title }}</span>
              <span class="download-card-description">{{ option.description }}</span>
              <span><strong>Скачивается:</strong> {{ option.package }}</span>
              <code>{{ option.command }}</code>
            </label>
          </div>

          <label>
            <span>Запись ключа подключения</span>
            <select v-model="downloadForm.enrollment_key_id" @change="fillDownloadKeyFromStorage">
              <option v-for="key in activeEnrollmentKeys" :key="key.id" :value="key.id">
                {{ key.name }} · {{ key.prefix }} · {{ key.used_count }} / {{ key.max_uses || '∞' }}
              </option>
            </select>
          </label>

          <label>
            <span>Открытый ключ подключения</span>
            <input
              v-model="downloadForm.enrollment_key"
              placeholder="smk_enroll_xxxxx"
              autocomplete="off"
            />
          </label>

          <p class="visual-note">
            Открытый ключ нужен для проверки права скачивания. Сам файл агента при первом запуске читает config.json, переменные окружения или запрашивает адрес сервера и ключ подключения.
          </p>

          <button type="submit" :disabled="isDownloadingAgent">
            {{ isDownloadingAgent ? 'Подготовка...' : 'Скачать файл' }}
          </button>
        </form>
      </div>
    </section>

    <section v-if="authUser && isRedfishModalOpen" class="modal-backdrop" aria-label="Добавление Redfish-источника">
      <div class="modal-panel">
        <div class="panel-heading">
          <div>
            <h2>Добавить аппаратный источник</h2>
            <span>Подключение iLO/iDRAC через Redfish API</span>
          </div>
          <button type="button" class="back-button" @click="closeRedfishModal">Закрыть</button>
        </div>

        <form class="download-form" @submit.prevent="submitRedfishSource">
          <label>
            <span>Тип источника</span>
            <select v-model="redfishForm.source_type">
              <option value="idrac">Dell iDRAC</option>
              <option value="ilo">HPE iLO</option>
            </select>
          </label>
          <label>
            <span>Название</span>
            <input v-model="redfishForm.name" />
          </label>
          <label>
            <span>IP-адрес управления</span>
            <input v-model="redfishForm.management_ip" />
          </label>
          <label>
            <span>Имя пользователя</span>
            <input v-model="redfishForm.username" />
          </label>
          <label>
            <span>Пароль</span>
            <input v-model="redfishForm.password" type="password" />
          </label>
          <button type="submit" :disabled="isAddingSource">
            {{ isAddingSource ? 'Добавление...' : 'Добавить источник' }}
          </button>
        </form>
      </div>
    </section>

    <section v-if="!authUser" class="login-panel">
      <div>
        <h2>Авторизация администратора</h2>
        <p>Введите учетные данные для доступа к центральному web-хабу мониторинга.</p>
      </div>

      <form @submit.prevent="login">
        <label>
          <span>Логин</span>
          <input v-model="loginForm.username" autocomplete="username" />
        </label>
        <label>
          <span>Пароль</span>
          <input v-model="loginForm.password" type="password" autocomplete="current-password" />
        </label>
        <button type="submit" :disabled="isLoginLoading">
          {{ isLoginLoading ? 'Вход...' : 'Войти' }}
        </button>
      </form>

      <div v-if="loginError" class="alert compact-alert">{{ loginError }}</div>
    </section>

    <template v-else-if="activePage === 'keys'">
      <section class="keys-panel">
        <div class="panel-heading">
          <div>
            <h2>Ключи подключения агентов</h2>
            <span>ключ подключения показывается только один раз при создании</span>
          </div>
          <button type="button" class="back-button" @click="goToSystems">Назад к системам</button>
        </div>

        <div v-if="keysError" class="alert compact-alert">{{ keysError }}</div>
        <div v-if="keysMessage" class="success-message compact-alert">{{ keysMessage }}</div>
        <div v-if="manualCopyKey" class="manual-copy compact-alert">
          <span>Ключ подключения для ручного копирования</span>
          <input :value="manualCopyKey" readonly @focus="$event.target.select()" />
        </div>

        <form class="key-form" @submit.prevent="createEnrollmentKey">
          <label>
            <span>Название</span>
            <input v-model="newKeyForm.name" />
          </label>
          <label>
            <span>Максимум использований</span>
            <input v-model.number="newKeyForm.max_uses" type="number" min="1" />
          </label>
          <label>
            <span>Срок действия, дней</span>
            <input v-model.number="newKeyForm.expires_days" type="number" min="1" />
          </label>
          <button type="submit" :disabled="isCreatingKey">
            {{ isCreatingKey ? 'Создание...' : 'Создать ключ' }}
          </button>
        </form>

        <section v-if="createdEnrollmentKey" class="created-key">
          <h3>Сохраните ключ, повторно он показан не будет</h3>
          <code>{{ createdEnrollmentKey.key }}</code>
          <p>Ключ сохранён локально в этом браузере для показа и копирования. Сервер по-прежнему хранит только хэш.</p>
          <button type="button" @click="createdEnrollmentKey = null">Закрыть</button>
        </section>

        <div v-if="isKeysLoading" class="loading">Загрузка ключей...</div>
        <div v-else-if="!enrollmentKeys.length" class="empty-panel compact-empty">Ключей подключения пока нет</div>

        <div v-else class="table-wrap">
          <table>
            <thead>
              <tr><th>Название</th><th>Ключ подключения</th><th>Использования</th><th>Действует до</th><th>Статус</th><th></th></tr>
            </thead>
            <tbody>
              <tr v-for="key in enrollmentKeys" :key="key.id">
                <td>{{ key.name }}</td>
                <td>
                  <code class="masked-key" :class="{ revealed: revealedEnrollmentKeys[key.id] }">
                    {{ maskedEnrollmentKey(key) }}
                  </code>
                </td>
                <td>{{ key.used_count }} / {{ key.max_uses || '∞' }}</td>
                <td>{{ formatDateTime(key.expires_at) }}</td>
                <td><span class="status-badge" :class="key.is_active ? 'online' : 'archived'">{{ key.is_active ? 'активен' : 'отозван' }}</span></td>
                <td class="table-actions">
                  <button type="button" class="table-button" @click="revealEnrollmentKey(key)">
                    {{ revealedEnrollmentKeys[key.id] ? 'Скрыть' : 'Показать' }}
                  </button>
                  <button type="button" class="table-button" @click="copyEnrollmentKey(key)">
                    Копировать
                  </button>
                  <button
                    type="button"
                    class="table-button"
                    :disabled="!key.is_active"
                    @click="revokeEnrollmentKey(key.id)"
                  >
                    Отозвать
                  </button>
                  <button type="button" class="table-button danger-button" @click="deleteEnrollmentKey(key)">
                    Удалить
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>

    <template v-else-if="activePage === 'users'">
      <section class="keys-panel">
        <div class="panel-heading">
          <div>
            <h2>Пользователи организации</h2>
            <span>Участники текущей организации и их роли</span>
          </div>
          <button type="button" class="back-button" @click="goToSystems">Назад к системам</button>
        </div>

        <div v-if="membersError" class="alert compact-alert">{{ membersError }}</div>

        <form class="key-form" @submit.prevent="createOrganizationMember">
          <label>
            <span>Имя пользователя</span>
            <input v-model="newMemberForm.username" autocomplete="off" />
          </label>
          <label>
            <span>Временный пароль</span>
            <input v-model="newMemberForm.password" type="password" autocomplete="new-password" />
          </label>
          <label>
            <span>Роль</span>
            <select v-model="newMemberForm.role">
              <option value="viewer">наблюдатель</option>
              <option value="admin">администратор</option>
            </select>
          </label>
          <button type="submit" :disabled="isCreatingMember">
            {{ isCreatingMember ? 'Добавление...' : 'Добавить пользователя' }}
          </button>
        </form>

        <div v-if="isMembersLoading" class="loading">Загрузка участников...</div>
        <div v-else-if="!organizationMembers.length" class="empty-panel compact-empty">Участников пока нет</div>

        <div v-else class="table-wrap">
          <table>
            <thead>
              <tr><th>Имя пользователя</th><th>Роль</th><th>Создан</th><th>В организации с</th><th>Действия</th></tr>
            </thead>
            <tbody>
              <tr v-for="member in organizationMembers" :key="member.user_id">
                <td>{{ member.username }}</td>
                <td>
                  <select
                    :value="member.role"
                    :disabled="member.role === 'owner'"
                    @change="updateOrganizationMemberRole(member, $event.target.value)"
                  >
                    <option value="owner" disabled>владелец</option>
                    <option value="admin">администратор</option>
                    <option value="viewer">наблюдатель</option>
                  </select>
                </td>
                <td>{{ formatDateTime(member.user_created_at) }}</td>
                <td>{{ formatDateTime(member.member_created_at) }}</td>
                <td class="table-actions">
                  <button
                    v-if="isOwner && member.role !== 'owner'"
                    type="button"
                    class="table-button"
                    @click="transferOwnership(member)"
                  >
                    Сделать владельцем
                  </button>
                  <button
                    type="button"
                    class="table-button"
                    :disabled="member.role === 'owner' || member.user_id === authUser.id"
                    @click="deleteOrganizationMember(member)"
                  >
                    Удалить
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>

    <template v-else-if="activePage === 'systems'">
      <div v-if="nodesError" class="alert">
        {{ nodesError }}. Проверьте, что FastAPI запущен на порту 8000.
      </div>

      <div v-if="isNodesLoading" class="loading">Загрузка списка систем...</div>

      <section class="source-actions" aria-label="Добавление источников">
        <div>
          <h2>Добавить источник</h2>
          <p>Подключайте аппаратные контроллеры HPE iLO и Dell iDRAC через Redfish API.</p>
        </div>
        <div class="source-buttons">
          <div v-if="canManageNodes" class="redfish-buttons">
            <button type="button" :disabled="isAddingSource" @click="openRedfishModal('idrac')">Добавить iDRAC</button>
            <button type="button" :disabled="isAddingSource" @click="openRedfishModal('ilo')">Добавить HPE iLO</button>
          </div>
        </div>
      </section>

      <div class="systems-filter-bar">
        <label class="archive-toggle">
          <input v-model="includeArchived" type="checkbox" @change="loadNodes" />
          <span>Показать архивные</span>
        </label>
      </div>

      <section v-if="editNode" class="edit-panel">
        <div class="panel-heading">
          <div>
            <h2>Редактирование узла</h2>
            <span>{{ editNode.hostname }}</span>
          </div>
          <button type="button" class="back-button" @click="closeEditNode">Закрыть</button>
        </div>
        <form class="edit-form" @submit.prevent="saveNodeEdit">
          <label>
            <span>Название</span>
            <input v-model="editNodeForm.name" />
          </label>
          <label>
            <span>Описание</span>
            <textarea v-model="editNodeForm.description"></textarea>
          </label>
          <button type="submit">Сохранить</button>
        </form>
      </section>

      <section v-if="!isNodesLoading && !nodes.length" class="empty-panel">
        Подключённые системы не найдены
      </section>

      <section v-else class="nodes-grid" aria-label="Список контролируемых систем">
        <article
          v-for="node in nodes"
          :key="node.id"
          class="node-card"
          :class="{ offline: node.status !== 'online', archived: node.is_archived }"
          @click="openNode(node)"
        >
          <div class="node-card-header">
            <div>
              <span class="source-pill">{{ sourceTypeLabel(node.source_type) }}</span>
              <h2>{{ node.name }}</h2>
            </div>
            <strong class="score-pill">{{ node.health_score }}</strong>
          </div>
          <div class="node-card-meta">
            <span class="status-badge" :class="statusBadgeClass(node.status)">{{ statusLabel(node.status) }}</span>
            <span v-if="node.is_archived" class="status-badge archived">архив</span>
          </div>
          <p class="node-summary">{{ nodeHealthText(node) }}</p>
          <dl>
            <dt>Имя хоста</dt><dd>{{ node.hostname }}</dd>
            <dt>Описание</dt><dd>{{ node.description || 'нет описания' }}</dd>
            <dt>Последняя связь</dt><dd>{{ formatDateTime(node.last_seen) }}</dd>
          </dl>
          <div class="node-actions">
            <button type="button" @click.stop="openNode(node)">Открыть</button>
            <button v-if="canManageNodes" type="button" @click.stop="startEditNode(node)">Переименовать</button>
            <button v-if="canManageNodes" type="button" @click.stop="refreshNode(node)">Обновить</button>
            <button v-if="canManageNodes" type="button" @click.stop="clearNodeHistory(node)">Очистить историю</button>
            <button v-if="canManageNodes && !node.is_archived" type="button" @click.stop="archiveNode(node)">Архивировать</button>
            <button v-if="canManageNodes && node.is_archived" type="button" @click.stop="restoreNode(node)">Восстановить</button>
          </div>
        </article>
      </section>
    </template>

    <template v-else>
      <section class="node-header">
        <div>
          <button type="button" class="back-button" @click="goToSystems">Назад к системам</button>
          <h2>{{ selectedNode?.name || 'Узел' }}</h2>
          <p>
            {{ selectedNode?.hostname || 'hostname неизвестен' }} ·
            {{ selectedNodeSourceLabel }} ·
            {{ statusLabel(selectedNode?.status) }} ·
            последняя связь {{ formatDateTime(selectedNode?.last_seen) }}
          </p>
          <p v-if="selectedNode?.description">{{ selectedNode.description }}</p>
          <p v-if="selectedNode?.is_archived" class="archive-note">Узел находится в архиве</p>
          <div v-if="canManageNodes" class="node-actions header-actions">
            <button type="button" @click="refreshNode(selectedNode)">Обновить</button>
            <button type="button" @click="startEditNode(selectedNode)">Редактировать</button>
            <button type="button" @click="clearNodeHistory(selectedNode)">Очистить историю</button>
            <button v-if="!selectedNode?.is_archived" type="button" @click="archiveNode(selectedNode)">Архивировать</button>
            <button v-else type="button" @click="restoreNode(selectedNode)">Восстановить</button>
          </div>
        </div>
      </section>

      <section v-if="editNode" class="edit-panel">
        <div class="panel-heading">
          <div>
            <h2>Редактирование узла</h2>
            <span>{{ editNode.hostname }}</span>
          </div>
          <button type="button" class="back-button" @click="closeEditNode">Закрыть</button>
        </div>
        <form class="edit-form" @submit.prevent="saveNodeEdit">
          <label>
            <span>Название</span>
            <input v-model="editNodeForm.name" />
          </label>
          <label>
            <span>Описание</span>
            <textarea v-model="editNodeForm.description"></textarea>
          </label>
          <button type="submit">Сохранить</button>
        </form>
      </section>

      <nav class="tabs" aria-label="Разделы мониторинга">
        <button :class="{ active: activePage === 'overview' }" @click="switchPage('overview')">Обзор</button>
        <button :class="{ active: activePage === 'details' }" @click="switchPage('details')">Подробные метрики</button>
      </nav>

      <div v-if="error" class="alert">
        {{ error }}. Проверьте, что FastAPI запущен на порту 8000.
      </div>

      <section v-if="isHardwareSource" class="hardware-layout">
        <section class="empty-panel">
          Для аппаратного источника отображается состояние серверного оборудования, полученное через Redfish API.
        </section>

        <div v-if="hardwareError" class="alert">{{ hardwareError }}</div>

        <section class="hardware-panel">
          <div class="panel-heading">
            <div>
              <h2>Аппаратное состояние</h2>
              <span>{{ selectedNodeSourceLabel }} · {{ selectedNode?.management_ip || selectedNode?.hostname }}</span>
            </div>
            <button type="button" class="back-button" @click="pollRedfishNode">Опросить Redfish</button>
          </div>

          <div class="hardware-grid">
            <article>
              <span>Питание</span>
              <strong>{{ hardwareValueLabel(hardware?.power_state) }}</strong>
            </article>
            <article>
              <span>Аппаратное состояние</span>
              <strong>{{ hardwareValueLabel(hardware?.hardware_health) }}</strong>
            </article>
            <article>
              <span>Температура</span>
              <strong>{{ hardware?.temperature_c ?? '...' }} °C</strong>
            </article>
            <article>
              <span>Вентиляторы</span>
              <strong>{{ hardwareValueLabel(hardware?.fans_health) }}</strong>
            </article>
            <article>
              <span>Блоки питания</span>
              <strong>{{ hardwareValueLabel(hardware?.power_supplies_health) }}</strong>
            </article>
          </div>

          <p class="diagnostics-summary">{{ translateTelemetryText(hardware?.summary) || 'Аппаратные данные будут показаны после первого Redfish-опроса.' }}</p>
        </section>

        <section class="diagnostics-panel" aria-label="Диагностика состояния">
          <div class="panel-heading">
            <div>
              <h2>Диагностика состояния</h2>
              <span>серверный вывод по аппаратным метрикам</span>
            </div>
            <div class="diagnostic-score">
              <strong>{{ diagnostics?.health_score ?? '...' }}</strong>
              <div class="health-scale compact"><i :style="{ width: `${diagnostics?.health_score || 0}%` }"></i></div>
            </div>
          </div>

          <div v-if="diagnosticsError" class="alert compact-alert">{{ diagnosticsError }}</div>

          <template v-else>
            <div class="diagnostics-grid">
              <article>
                <span>Состояние</span>
                <strong :class="severityClass(diagnostics?.system_state)">{{ stateLabel(diagnostics?.system_state) }}</strong>
              </article>
              <article>
                <span>Сценарий</span>
                <strong>{{ scenarioLabel(diagnostics?.scenario) }}</strong>
              </article>
              <article>
                <span>Узкое место</span>
                <strong><span class="status-badge warning">{{ bottleneckLabel(diagnostics?.bottleneck?.component) }}</span></strong>
              </article>
              <article>
                <span>Уверенность</span>
                <strong>{{ diagnostics?.confidence ? Math.round(diagnostics.confidence * 100) + '%' : '...' }}</strong>
              </article>
            </div>

            <p class="diagnostics-summary">{{ translateTelemetryText(diagnostics?.summary) || 'Диагностика выполняется после получения аппаратных метрик.' }}</p>
            <p class="visual-note">{{ translateTelemetryText(diagnostics?.bottleneck?.reason) || '' }}</p>

            <div class="diagnostics-lists">
              <div>
                <h3>Причины вывода</h3>
                <ul>
                  <li v-for="item in diagnostics?.evidence || []" :key="item">{{ translateTelemetryText(item) }}</li>
                </ul>
              </div>
              <div>
                <h3>Рекомендации</h3>
                <ul>
                  <li v-for="item in diagnostics?.recommendations || []" :key="item">{{ translateTelemetryText(item) }}</li>
                </ul>
              </div>
            </div>
          </template>
        </section>
      </section>

      <template v-else-if="activePage === 'overview'">
        <div v-if="isInitialLoading && !current" class="loading compact-refresh">Первичная загрузка данных узла...</div>
        <div v-else-if="isBackgroundRefreshing" class="loading compact-refresh">Фоновое обновление без сброса карточек...</div>

        <section class="metric-grid" aria-label="Текущие системные показатели">
          <article class="metric-card has-tooltip" :class="metricClass('cpu')">
            <span>CPU</span>
            <strong>{{ formatPercent(current?.cpu_percent) }}</strong>
            <small :class="['trend', trendClass('cpu')]">{{ trendLabel('cpu') }}</small>
            <div class="meter"><i :style="{ width: `${current?.cpu_percent || 0}%` }"></i></div>
            <div class="tooltip">
              <b>{{ metricHints.cpu.title }}</b>
              <p>{{ metricHints.cpu.description }}</p>
              <p>{{ metricHints.cpu.reasons }}</p>
              <p>{{ metricHints.cpu.advice }}</p>
            </div>
          </article>

          <article class="metric-card has-tooltip" :class="metricClass('ram')">
            <span>RAM</span>
            <strong>{{ formatPercent(current?.ram_percent) }}</strong>
            <small :class="['trend', trendClass('ram')]">{{ trendLabel('ram') }}</small>
            <div class="meter accent"><i :style="{ width: `${current?.ram_percent || 0}%` }"></i></div>
            <div class="tooltip">
              <b>{{ metricHints.ram.title }}</b>
              <p>{{ metricHints.ram.description }}</p>
              <p>{{ metricHints.ram.reasons }}</p>
              <p>{{ metricHints.ram.advice }}</p>
            </div>
          </article>

          <article class="metric-card has-tooltip" :class="metricClass('disk')">
            <span>Диск</span>
            <strong>{{ formatPercent(current?.disk_percent) }}</strong>
            <small :class="['trend', trendClass('disk')]">{{ trendLabel('disk') }}</small>
            <div class="meter disk"><i :style="{ width: `${current?.disk_percent || 0}%` }"></i></div>
            <div class="tooltip">
              <b>{{ metricHints.disk.title }}</b>
              <p>{{ metricHints.disk.description }}</p>
              <p>{{ metricHints.disk.reasons }}</p>
              <p>{{ metricHints.disk.advice }}</p>
            </div>
          </article>

          <article class="metric-card has-tooltip" :class="metricClass('network')">
            <span>Сеть</span>
            <strong>{{ formatSpeed(current?.network_recv_per_sec) }}</strong>
            <small>прием / {{ formatSpeed(current?.network_sent_per_sec) }} передача</small>
            <small :class="['trend', trendClass('network')]">{{ trendLabel('network') }}</small>
            <div class="tooltip">
              <b>{{ metricHints.network.title }}</b>
              <p>{{ metricHints.network.description }}</p>
              <p>{{ metricHints.network.reasons }}</p>
              <p>{{ metricHints.network.advice }}</p>
            </div>
          </article>
        </section>

        <section v-if="warnings.length" class="warnings" aria-label="Предупреждения">
          <h2>Предупреждения</h2>
          <p v-for="warning in warnings" :key="warning">{{ warning }}</p>
        </section>

        <section class="analysis-grid" aria-label="Аналитика состояния системы">
          <article class="health-card">
            <span>Индекс состояния системы</span>
            <strong>{{ analysis?.health_score ?? '...' }}</strong>
            <p>{{ healthStatusLabel(analysis?.health_status) }}</p>
            <div class="health-scale">
              <i :style="{ width: `${analysis?.health_score || 0}%` }"></i>
            </div>
            <small>Интервал обновления: {{ (refreshIntervalMs / 1000).toFixed(0) }} сек.</small>
          </article>

          <article class="bottleneck-card">
            <span>Предполагаемое узкое место системы</span>
            <strong>{{ analysisBottleneckTitle(analysis?.bottleneck) }}</strong>
            <p>{{ translateTelemetryText(analysis?.bottleneck?.reason) || 'Анализ выполняется после накопления истории.' }}</p>
            <small>{{ translateTelemetryText(analysis?.bottleneck?.recommendation) || '' }}</small>
          </article>
        </section>

        <section v-if="analysis?.anomalies?.length" class="warnings anomalies" aria-label="Аномалии">
          <h2>Обнаруженные аномалии</h2>
          <p v-for="item in analysis.anomalies" :key="item.metric">
            {{ translateTelemetryText(item.message) }}
          </p>
        </section>

        <section class="diagnostics-panel" aria-label="Диагностика состояния">
          <div class="panel-heading">
            <div>
              <h2>Диагностика состояния</h2>
              <span>автоматический серверный вывод по последним {{ sourceHistoryLimit }} точкам</span>
            </div>
            <div class="diagnostic-score">
              <strong>{{ diagnostics?.health_score ?? analysis?.health_score ?? '...' }}</strong>
              <div class="health-scale compact"><i :style="{ width: `${diagnostics?.health_score || analysis?.health_score || 0}%` }"></i></div>
            </div>
          </div>

          <div v-if="diagnosticsError" class="alert compact-alert">{{ diagnosticsError }}</div>

          <template v-else>
            <div class="diagnostics-grid">
              <article>
                <span>Состояние</span>
                <strong :class="severityClass(diagnostics?.system_state)">{{ stateLabel(diagnostics?.system_state) }}</strong>
              </article>
              <article>
                <span>Сценарий</span>
                <strong>{{ scenarioLabel(diagnostics?.scenario) }}</strong>
              </article>
              <article>
                <span>Узкое место</span>
                <strong><span class="status-badge warning">{{ bottleneckLabel(diagnostics?.bottleneck?.component) }}</span></strong>
              </article>
              <article>
                <span>Уверенность</span>
                <strong>{{ diagnostics?.confidence ? Math.round(diagnostics.confidence * 100) + '%' : '...' }}</strong>
              </article>
            </div>

            <p class="diagnostics-summary">{{ translateTelemetryText(diagnostics?.summary) || 'Диагностика выполняется после накопления истории.' }}</p>
            <p class="visual-note">{{ translateTelemetryText(diagnostics?.bottleneck?.reason) || '' }}</p>

            <div class="diagnostics-lists">
              <div>
                <h3>Причины вывода</h3>
                <ul>
                  <li v-for="item in diagnostics?.evidence || []" :key="item">{{ translateTelemetryText(item) }}</li>
                </ul>
              </div>
              <div>
                <h3>Рекомендации</h3>
                <ul>
                  <li v-for="item in diagnostics?.recommendations || []" :key="item">{{ translateTelemetryText(item) }}</li>
                </ul>
              </div>
            </div>
          </template>
        </section>

        <section class="process-panel" aria-label="Возможные процессы-причины">
          <div class="panel-heading">
            <div>
              <h2>Возможные процессы-причины</h2>
              <span>список процессов отправляется агентом только при высокой CPU/RAM нагрузке</span>
            </div>
          </div>

          <div v-if="!processSnapshot" class="empty-panel compact-empty">
            {{ processSnapshotError || 'Снимков процессов пока нет' }}
          </div>

          <template v-else>
            <p class="visual-note">
              Причина: {{ processReasonLabel(processSnapshot.reason) }} · время:
              {{ formatDateTime(processSnapshot.created_at) }}
            </p>
            <div class="table-wrap">
              <table>
                <thead>
                  <tr><th>PID</th><th>Имя процесса</th><th>CPU %</th><th>RAM %</th></tr>
                </thead>
                <tbody>
                  <tr v-for="item in processSnapshot.items" :key="item.id">
                    <td>{{ item.pid }}</td>
                    <td>{{ item.name }}</td>
                    <td>{{ formatPercent(item.cpu_percent) }}</td>
                    <td>{{ formatPercent(item.memory_percent) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </template>
        </section>

        <section class="summary-panel" aria-label="Сводка системных показателей">
          <div class="panel-heading">
            <div>
              <h2>Сводка</h2>
              <span>по последним {{ sourceHistoryLimit }} точкам узла #{{ selectedNodeId }}</span>
            </div>

            <div class="controls">
              <label class="history-limit">
                <span>Отображать</span>
                <select v-model.number="selectedHistoryLimit" @change="loadOverview({ initial: false })">
                  <option v-for="option in historyLimitOptions" :key="option" :value="option">
                    {{ option }}
                  </option>
                </select>
              </label>

              <label class="history-limit">
                <span>График</span>
                <select v-model="isOptimizedView">
                  <option :value="false">Все точки</option>
                  <option :value="true">Оптимизированное отображение</option>
                </select>
              </label>

              <label class="history-limit">
                <span>Сравнение</span>
                <select v-model="isComparisonMode">
                  <option :value="false">Обычный режим</option>
                  <option :value="true">Сравнение режимов</option>
                </select>
              </label>
            </div>
          </div>

          <p class="visual-note">
            Оптимизированное отображение уменьшает количество точек без потери общей формы графика:
            получено {{ history.length }}, отображено до {{ displayedPointsCount }},
            сокращение {{ pointsReductionPercent }}%.
          </p>

          <div class="summary-grid">
            <article>
              <span>Средний CPU</span>
              <strong>{{ formatPercent(summary?.avg_cpu_percent) }}</strong>
            </article>
            <article>
              <span>Максимальный CPU</span>
              <strong>{{ formatPercent(summary?.max_cpu_percent) }}</strong>
            </article>
            <article>
              <span>Средняя RAM</span>
              <strong>{{ formatPercent(summary?.avg_ram_percent) }}</strong>
            </article>
            <article>
              <span>Максимальная RAM</span>
              <strong>{{ formatPercent(summary?.max_ram_percent) }}</strong>
            </article>
          </div>
        </section>

        <section v-if="history.length < 2" class="empty-panel">
          Недостаточно данных для построения графика
        </section>

        <section v-else-if="!isComparisonMode" class="charts">
          <article class="chart-panel">
            <div class="panel-heading">
              <div>
                <h2>CPU</h2>
                <span>получено {{ history.length }}, отображено {{ cpuDisplayedHistory.length }}, сокращение {{ pointsReductionPercent }}%</span>
              </div>
            </div>
            <svg viewBox="0 0 100 100" preserveAspectRatio="none" role="img" aria-label="График загрузки CPU">
              <polyline :points="chartPoints('cpu_percent')" />
            </svg>
          </article>

          <article class="chart-panel">
            <div class="panel-heading">
              <div>
                <h2>RAM</h2>
                <span>получено {{ history.length }}, отображено {{ ramDisplayedHistory.length }}, сокращение {{ pointsReductionPercent }}%</span>
              </div>
            </div>
            <svg viewBox="0 0 100 100" preserveAspectRatio="none" role="img" aria-label="График использования RAM">
              <polyline class="ram-line" :points="chartPoints('ram_percent')" />
            </svg>
          </article>
        </section>

        <section v-else class="comparison-grid">
          <article class="chart-panel">
            <h2>CPU: все точки</h2>
            <span>{{ history.length }} точек</span>
            <svg viewBox="0 0 100 100" preserveAspectRatio="none" role="img" aria-label="CPU все точки">
              <polyline :points="chartPointsFor(history, 'cpu_percent')" />
            </svg>
          </article>
          <article class="chart-panel">
            <h2>CPU: оптимизировано</h2>
            <span>{{ cpuOptimizedHistory.length }} точек</span>
            <svg viewBox="0 0 100 100" preserveAspectRatio="none" role="img" aria-label="CPU оптимизированный график">
              <polyline :points="chartPointsFor(cpuOptimizedHistory, 'cpu_percent')" />
            </svg>
          </article>
          <article class="chart-panel">
            <h2>RAM: все точки</h2>
            <span>{{ history.length }} точек</span>
            <svg viewBox="0 0 100 100" preserveAspectRatio="none" role="img" aria-label="RAM все точки">
              <polyline class="ram-line" :points="chartPointsFor(history, 'ram_percent')" />
            </svg>
          </article>
          <article class="chart-panel">
            <h2>RAM: оптимизировано</h2>
            <span>{{ ramOptimizedHistory.length }} точек</span>
            <svg viewBox="0 0 100 100" preserveAspectRatio="none" role="img" aria-label="RAM оптимизированный график">
              <polyline class="ram-line" :points="chartPointsFor(ramOptimizedHistory, 'ram_percent')" />
            </svg>
          </article>
        </section>
      </template>

      <template v-else>
        <section v-if="!isLocalNode" class="empty-panel">
          Подробные live-метрики сейчас доступны для локальной системы. Для узлов с агентом используется история телеметрии, карточки, графики и анализ на странице "Обзор".
        </section>

        <template v-else>
          <div v-if="detailsError" class="alert">{{ detailsError }}</div>
          <div v-if="isDetailsLoading" class="loading">Загрузка подробных метрик...</div>

          <section class="details-grid">
            <article class="details-panel">
              <h2>Сведения о системе</h2>
              <dl>
                <dt>Имя компьютера</dt><dd>{{ details.info?.computer_name || '...' }}</dd>
                <dt>ОС</dt><dd>{{ details.info?.os || '...' }}</dd>
                <dt>Версия ОС</dt><dd>{{ details.info?.os_version || '...' }}</dd>
                <dt>Архитектура</dt><dd>{{ details.info?.architecture || '...' }}</dd>
                <dt>Время работы</dt><dd>{{ details.info?.uptime || '...' }}</dd>
              </dl>
            </article>

            <article class="details-panel">
              <h2>CPU</h2>
              <dl>
                <dt>Физические ядра</dt><dd>{{ details.cpu?.physical_cores ?? '...' }}</dd>
                <dt>Логические потоки</dt><dd>{{ details.cpu?.logical_threads ?? '...' }}</dd>
                <dt>Частота</dt><dd>{{ details.cpu?.current_frequency_mhz || 0 }} МГц</dd>
                <dt>Средняя загрузка</dt><dd>{{ formatPercent(details.cpu?.average_percent) }}</dd>
              </dl>
              <div class="core-list">
                <div v-for="(core, index) in details.cpu?.per_core_percent || []" :key="index">
                  <span>Ядро {{ index + 1 }}</span>
                  <div class="meter"><i :style="{ width: `${core}%` }"></i></div>
                  <b>{{ formatPercent(core) }}</b>
                </div>
              </div>
            </article>

            <article class="details-panel">
              <h2>Память</h2>
              <dl>
                <dt>Всего</dt><dd>{{ formatBytes(details.memory?.total) }}</dd>
                <dt>Используется</dt><dd>{{ formatBytes(details.memory?.used) }}</dd>
                <dt>Свободно</dt><dd>{{ formatBytes(details.memory?.free) }}</dd>
                <dt>Доступно</dt><dd>{{ formatBytes(details.memory?.available) }}</dd>
                <dt>Использование</dt><dd>{{ formatPercent(details.memory?.percent) }}</dd>
              </dl>
            </article>

            <article class="details-panel">
              <h2>Сеть</h2>
              <div class="table-wrap">
                <table>
                  <thead>
                    <tr><th>Интерфейс</th><th>Отправлено</th><th>Получено</th><th>Скорость</th></tr>
                  </thead>
                  <tbody>
                    <tr v-for="item in details.network" :key="item.name">
                      <td>{{ item.name }}</td>
                      <td>{{ formatBytes(item.bytes_sent) }}</td>
                      <td>{{ formatBytes(item.bytes_recv) }}</td>
                      <td>{{ formatSpeed(item.sent_per_sec) }} / {{ formatSpeed(item.recv_per_sec) }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </article>
          </section>

          <section class="wide-panel">
            <h2>Диски</h2>
            <div class="table-wrap">
              <table>
                <thead>
                  <tr><th>Диск</th><th>Точка</th><th>ФС</th><th>Всего</th><th>Занято</th><th>Свободно</th><th>%</th></tr>
                </thead>
                <tbody>
                  <tr v-for="disk in details.disks" :key="disk.device + disk.mountpoint">
                    <td>{{ disk.device }}</td>
                    <td>{{ disk.mountpoint }}</td>
                    <td>{{ disk.file_system }}</td>
                    <td>{{ formatBytes(disk.total) }}</td>
                    <td>{{ formatBytes(disk.used) }}</td>
                    <td>{{ formatBytes(disk.free) }}</td>
                    <td>{{ formatPercent(disk.percent) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>

          <section class="wide-panel">
            <h2>Процессы</h2>
            <div class="table-wrap">
              <table>
                <thead>
                  <tr><th>PID</th><th>Имя процесса</th><th>CPU %</th><th>RAM %</th></tr>
                </thead>
                <tbody>
                  <tr v-for="process in details.processes" :key="process.pid">
                    <td>{{ process.pid }}</td>
                    <td>{{ process.name }}</td>
                    <td>{{ formatPercent(process.cpu_percent) }}</td>
                    <td>{{ formatPercent(process.memory_percent) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>
        </template>
      </template>
    </template>
  </main>
</template>
