<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

const current = ref(null)
const history = ref([])
const summary = ref(null)
const analysis = ref(null)
const appConfig = ref(null)
const details = ref({
  info: null,
  cpu: null,
  memory: null,
  disks: [],
  network: [],
  processes: []
})

const activePage = ref('overview')
const selectedHistoryLimit = ref(50)
const isOptimizedView = ref(true)
const isComparisonMode = ref(false)
const error = ref('')
const detailsError = ref('')
const isLoading = ref(true)
const isDetailsLoading = ref(false)
let overviewTimerId = null
let detailsTimerId = null
let currentOverviewIntervalMs = 3000

const apiBase = import.meta.env.VITE_API_BASE || ''
const historyLimitOptions = [20, 50, 100, 200]
const targetChartPoints = 60

const metricHints = {
  cpu: {
    title: 'CPU',
    description: 'Показывает загрузку процессора в процентах.',
    reasons: 'Высокая нагрузка часто возникает из-за тяжелых программ, фоновых обновлений или большого числа процессов.',
    advice: 'Проверьте топ процессов и закройте лишние приложения.'
  },
  ram: {
    title: 'RAM',
    description: 'Показывает долю используемой оперативной памяти.',
    reasons: 'Рост RAM связан с браузером, IDE, виртуальными машинами или утечками памяти.',
    advice: 'Проверьте процессы по RAM и перезапустите подозрительные приложения.'
  },
  disk: {
    title: 'Disk',
    description: 'Показывает заполненность основного диска.',
    reasons: 'Высокое значение появляется при нехватке свободного места, временных файлах или больших архивах.',
    advice: 'Очистите временные файлы и проверьте самые крупные папки.'
  },
  network: {
    title: 'Network',
    description: 'Показывает текущую скорость приема и передачи данных.',
    reasons: 'Скачивания, синхронизация облака и обновления могут резко увеличить трафик.',
    advice: 'Проверьте активные приложения и сетевые интерфейсы.'
  }
}

const warnings = computed(() => {
  const result = []
  if ((current.value?.cpu_percent || 0) > 85) {
    result.push('CPU выше 85%. Проверьте процессы с высокой загрузкой.')
  }
  if ((current.value?.ram_percent || 0) > 90) {
    result.push('RAM выше 90%. Возможно, системе не хватает оперативной памяти.')
  }
  if ((current.value?.disk_percent || 0) > 95) {
    result.push('Disk выше 95%. Освободите место на системном диске.')
  }
  return result
})

const displayedHistory = computed(() => (
  isOptimizedView.value ? optimizedHistory.value : history.value
))

const optimizedHistory = computed(() => downsampleMetrics(history.value, targetChartPoints))

const pointsReductionPercent = computed(() => {
  if (!history.value.length) {
    return 0
  }
  return Math.max(0, Math.round((1 - displayedHistory.value.length / history.value.length) * 100))
})

const refreshIntervalMs = computed(() => (
  (analysis.value?.current_refresh_interval
    || appConfig.value?.frontend_refresh_interval_seconds
    || 3) * 1000
))

const lastUpdated = computed(() => {
  if (!current.value?.timestamp) {
    return 'нет данных'
  }
  return new Date(current.value.timestamp).toLocaleTimeString('ru-RU')
})

function downsampleMetrics(data, targetCount) {
  if (!Array.isArray(data) || data.length <= targetCount) {
    return data
  }

  const result = [data[0]]
  const middleCount = targetCount - 2
  const step = (data.length - 2) / middleCount

  for (let index = 1; index <= middleCount; index += 1) {
    const sourceIndex = Math.round(index * step)
    result.push(data[sourceIndex])
  }

  result.push(data[data.length - 1])
  return result
}

const formatPercent = (value) => `${Number(value || 0).toFixed(1)}%`

const formatBytes = (value) => {
  const units = ['Б', 'КБ', 'МБ', 'ГБ', 'ТБ']
  let size = Number(value || 0)
  let unitIndex = 0

  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024
    unitIndex += 1
  }

  return `${size.toFixed(size >= 10 ? 0 : 1)} ${units[unitIndex]}`
}

const formatSpeed = (value) => `${formatBytes(value)}/с`

const chartPointsFor = (items, field) => {
  if (items.length === 0) {
    return ''
  }

  return items
    .map((item, index) => {
      const x = items.length === 1
        ? 100
        : (index / (items.length - 1)) * 100
      const y = 100 - Number(item[field] || 0)
      return `${x},${y}`
    })
    .join(' ')
}

const chartPoints = (field) => chartPointsFor(displayedHistory.value, field)

function trendLabel(metricName) {
  const trend = analysis.value?.trends?.[metricName] || 'stable'
  if (trend === 'growing') {
    return '↑ растет'
  }
  if (trend === 'falling') {
    return '↓ снижается'
  }
  return '→ стабильно'
}

function trendClass(metricName) {
  return `trend-${analysis.value?.trends?.[metricName] || 'stable'}`
}

function hasAnomaly(metricName) {
  const names = {
    cpu: 'CPU',
    ram: 'RAM',
    network: 'Network'
  }
  return (analysis.value?.anomalies || []).some((item) => item.metric === names[metricName])
}

function metricClass(metricName) {
  return {
    warning: metricName === 'cpu' && (current.value?.cpu_percent || 0) > 85
      || metricName === 'ram' && (current.value?.ram_percent || 0) > 90
      || metricName === 'disk' && (current.value?.disk_percent || 0) > 95,
    anomaly: hasAnomaly(metricName)
  }
}

async function loadConfig() {
  const response = await fetch(`${apiBase}/api/app/config`)
  if (response.ok) {
    appConfig.value = await response.json()
  }
}

async function loadOverview() {
  try {
    const limit = selectedHistoryLimit.value
    const [currentResponse, historyResponse, summaryResponse, analysisResponse] = await Promise.all([
      fetch(`${apiBase}/api/metrics/current`),
      fetch(`${apiBase}/api/metrics/history?limit=${limit}`),
      fetch(`${apiBase}/api/metrics/summary?limit=${limit}`),
      fetch(`${apiBase}/api/analysis/summary?limit=${limit}`)
    ])

    if (!currentResponse.ok || !historyResponse.ok || !summaryResponse.ok || !analysisResponse.ok) {
      throw new Error('Сервер вернул ошибку')
    }

    current.value = await currentResponse.json()
    history.value = await historyResponse.json()
    summary.value = await summaryResponse.json()
    analysis.value = await analysisResponse.json()
    applyAdaptiveRefreshInterval()
    error.value = ''
  } catch (requestError) {
    error.value = 'Нет подключения к локальному серверу мониторинга'
  } finally {
    isLoading.value = false
  }
}

async function loadDetails() {
  isDetailsLoading.value = true
  try {
    const [info, cpu, memory, disks, network, processes] = await Promise.all([
      fetch(`${apiBase}/api/system/info`),
      fetch(`${apiBase}/api/system/cpu`),
      fetch(`${apiBase}/api/system/memory`),
      fetch(`${apiBase}/api/system/disks`),
      fetch(`${apiBase}/api/system/network`),
      fetch(`${apiBase}/api/system/processes?limit=10&sort=cpu`)
    ])

    if (![info, cpu, memory, disks, network, processes].every((response) => response.ok)) {
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

function restartOverviewTimer() {
  window.clearInterval(overviewTimerId)
  overviewTimerId = window.setInterval(loadOverview, refreshIntervalMs.value)
  currentOverviewIntervalMs = refreshIntervalMs.value
}

function applyAdaptiveRefreshInterval() {
  if (refreshIntervalMs.value !== currentOverviewIntervalMs) {
    restartOverviewTimer()
  }
}

function switchPage(pageName) {
  activePage.value = pageName
  if (pageName === 'details') {
    loadDetails()
  }
}

onMounted(async () => {
  try {
    await loadConfig()
  } catch (configError) {
    appConfig.value = { frontend_refresh_interval_seconds: 3 }
  }

  loadOverview()
  restartOverviewTimer()
  detailsTimerId = window.setInterval(() => {
    if (activePage.value === 'details') {
      loadDetails()
    }
  }, 5000)
})

onBeforeUnmount(() => {
  window.clearInterval(overviewTimerId)
  window.clearInterval(detailsTimerId)
})
</script>

<template>
  <main class="page">
    <section class="topbar">
      <div>
        <p class="eyebrow">Локальный мониторинг</p>
        <h1>{{ activePage === 'overview' ? 'Состояние компьютера' : 'Подробные метрики' }}</h1>
      </div>
      <div class="status" :class="{ offline: error }">
        <span class="status-dot"></span>
        <span>{{ error ? 'Сервер недоступен' : 'Обновлено: ' + lastUpdated }}</span>
      </div>
    </section>

    <nav class="tabs" aria-label="Разделы мониторинга">
      <button :class="{ active: activePage === 'overview' }" @click="switchPage('overview')">Обзор</button>
      <button :class="{ active: activePage === 'details' }" @click="switchPage('details')">Подробные метрики</button>
    </nav>

    <div v-if="error" class="alert">
      {{ error }}. Проверьте, что FastAPI запущен на порту 8000.
    </div>

    <template v-if="activePage === 'overview'">
      <section class="metric-grid" aria-label="Текущие системные показатели">
        <article class="metric-card has-tooltip" :class="metricClass('cpu')">
          <span>CPU</span>
          <strong>{{ isLoading ? '...' : formatPercent(current?.cpu_percent) }}</strong>
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
          <strong>{{ isLoading ? '...' : formatPercent(current?.ram_percent) }}</strong>
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
          <strong>{{ isLoading ? '...' : formatPercent(current?.disk_percent) }}</strong>
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
          <strong>{{ isLoading ? '...' : formatSpeed(current?.network_recv_per_sec) }}</strong>
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
          <span>System Health Score</span>
          <strong>{{ analysis?.health_score ?? '...' }}</strong>
          <p>{{ analysis?.health_status || 'нет данных' }}</p>
          <div class="health-scale">
            <i :style="{ width: `${analysis?.health_score || 0}%` }"></i>
          </div>
          <small>Интервал обновления: {{ (refreshIntervalMs / 1000).toFixed(0) }} сек.</small>
        </article>

        <article class="bottleneck-card">
          <span>Предполагаемое узкое место системы</span>
          <strong>{{ analysis?.bottleneck?.title || '...' }}</strong>
          <p>{{ analysis?.bottleneck?.reason || 'Анализ выполняется после накопления истории.' }}</p>
          <small>{{ analysis?.bottleneck?.recommendation || '' }}</small>
        </article>
      </section>

      <section v-if="analysis?.anomalies?.length" class="warnings anomalies" aria-label="Аномалии">
        <h2>Обнаруженные аномалии</h2>
        <p v-for="item in analysis.anomalies" :key="item.metric">
          {{ item.message }}
        </p>
      </section>

      <section class="summary-panel" aria-label="Сводка системных показателей">
        <div class="panel-heading">
          <div>
            <h2>Сводка</h2>
            <span>по последним {{ selectedHistoryLimit }} точкам</span>
          </div>

          <div class="controls">
            <label class="history-limit">
              <span>Точек</span>
              <select v-model.number="selectedHistoryLimit" @change="loadOverview">
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
          получено {{ history.length }}, отображено {{ displayedHistory.length }},
          сокращение {{ pointsReductionPercent }}%.
        </p>

        <div class="summary-grid">
          <article>
            <span>Средний CPU</span>
            <strong>{{ isLoading ? '...' : formatPercent(summary?.avg_cpu_percent) }}</strong>
          </article>
          <article>
            <span>Максимальный CPU</span>
            <strong>{{ isLoading ? '...' : formatPercent(summary?.max_cpu_percent) }}</strong>
          </article>
          <article>
            <span>Средняя RAM</span>
            <strong>{{ isLoading ? '...' : formatPercent(summary?.avg_ram_percent) }}</strong>
          </article>
          <article>
            <span>Максимальная RAM</span>
            <strong>{{ isLoading ? '...' : formatPercent(summary?.max_ram_percent) }}</strong>
          </article>
        </div>
      </section>

      <section v-if="!isComparisonMode" class="charts">
        <article class="chart-panel">
          <div class="panel-heading">
            <div>
              <h2>CPU</h2>
              <span>получено {{ history.length }}, отображено {{ displayedHistory.length }}, сокращение {{ pointsReductionPercent }}%</span>
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
              <span>получено {{ history.length }}, отображено {{ displayedHistory.length }}, сокращение {{ pointsReductionPercent }}%</span>
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
          <h2>CPU: optimized</h2>
          <span>{{ optimizedHistory.length }} точек</span>
          <svg viewBox="0 0 100 100" preserveAspectRatio="none" role="img" aria-label="CPU оптимизированный график">
            <polyline :points="chartPointsFor(optimizedHistory, 'cpu_percent')" />
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
          <h2>RAM: optimized</h2>
          <span>{{ optimizedHistory.length }} точек</span>
          <svg viewBox="0 0 100 100" preserveAspectRatio="none" role="img" aria-label="RAM оптимизированный график">
            <polyline class="ram-line" :points="chartPointsFor(optimizedHistory, 'ram_percent')" />
          </svg>
        </article>
      </section>
    </template>

    <template v-else>
      <div v-if="detailsError" class="alert">{{ detailsError }}</div>
      <div v-if="isDetailsLoading" class="loading">Загрузка подробных метрик...</div>

      <section class="details-grid">
        <article class="details-panel">
          <h2>System info</h2>
          <dl>
            <dt>Имя компьютера</dt><dd>{{ details.info?.computer_name || '...' }}</dd>
            <dt>ОС</dt><dd>{{ details.info?.os || '...' }}</dd>
            <dt>Версия ОС</dt><dd>{{ details.info?.os_version || '...' }}</dd>
            <dt>Архитектура</dt><dd>{{ details.info?.architecture || '...' }}</dd>
            <dt>Uptime</dt><dd>{{ details.info?.uptime || '...' }}</dd>
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
              <span>Core {{ index + 1 }}</span>
              <div class="meter"><i :style="{ width: `${core}%` }"></i></div>
              <b>{{ formatPercent(core) }}</b>
            </div>
          </div>
        </article>

        <article class="details-panel">
          <h2>Memory</h2>
          <dl>
            <dt>Всего</dt><dd>{{ formatBytes(details.memory?.total) }}</dd>
            <dt>Используется</dt><dd>{{ formatBytes(details.memory?.used) }}</dd>
            <dt>Свободно</dt><dd>{{ formatBytes(details.memory?.free) }}</dd>
            <dt>Доступно</dt><dd>{{ formatBytes(details.memory?.available) }}</dd>
            <dt>Использование</dt><dd>{{ formatPercent(details.memory?.percent) }}</dd>
          </dl>
        </article>

        <article class="details-panel">
          <h2>Network</h2>
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
        <h2>Disks</h2>
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
        <h2>Processes</h2>
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
  </main>
</template>
