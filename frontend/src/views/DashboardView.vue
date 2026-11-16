<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { BarChart, LineChart, PieChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { init, use } from 'echarts/core'
import type { ECharts, EChartsOption } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { useRouter } from 'vue-router'

import { getDashboardSummary, type DashboardQuery } from '@/api/dashboard'
import type { DashboardSummary, DashboardFollowUp } from '@/types/api'

use([
  BarChart,
  LineChart,
  PieChart,
  GridComponent,
  LegendComponent,
  TooltipComponent,
  CanvasRenderer,
])

const router = useRouter()
const summary = ref<DashboardSummary | null>(null)
const loading = ref(false)
const loadError = ref('')
const selectedRange = ref<[string, string] | null>(null)

const sourceChartElement = ref<HTMLElement | null>(null)
const levelChartElement = ref<HTMLElement | null>(null)
const customerTrendChartElement = ref<HTMLElement | null>(null)
const followUpTrendChartElement = ref<HTMLElement | null>(null)

let sourceChart: ECharts | null = null
let levelChart: ECharts | null = null
let customerTrendChart: ECharts | null = null
let followUpTrendChart: ECharts | null = null

const methodLabels: Record<DashboardFollowUp['method'], string> = {
  phone: '电话',
  visit: '上门拜访',
  wechat: '微信',
  email: '邮件',
  other: '其他',
}

function getQuery(): DashboardQuery {
  if (!selectedRange.value) return {}
  return { start_date: selectedRange.value[0], end_date: selectedRange.value[1] }
}

async function loadSummary() {
  loading.value = true
  loadError.value = ''
  try {
    const response = await getDashboardSummary(getQuery())
    summary.value = response
    selectedRange.value = [response.range.start_date, response.range.end_date]
  } catch {
    loadError.value = '工作台统计加载失败，请重试。'
  } finally {
    loading.value = false
  }
}

function onRangeChange(value: [string, string] | null) {
  selectedRange.value = value
  void loadSummary()
}

function hasTrendData(values: { count: number }[]) {
  return values.some((item) => item.count > 0)
}

function disposeCharts() {
  sourceChart?.dispose()
  levelChart?.dispose()
  customerTrendChart?.dispose()
  followUpTrendChart?.dispose()
  sourceChart = null
  levelChart = null
  customerTrendChart = null
  followUpTrendChart = null
}

function createCharts() {
  const management = summary.value?.management
  if (!management) return
  disposeCharts()

  if (sourceChartElement.value) {
    sourceChart = init(sourceChartElement.value)
    const sourceOption: EChartsOption = {
      tooltip: { trigger: 'item' },
      legend: { bottom: 0, type: 'scroll' },
      series: [
        {
          type: 'pie',
          radius: ['42%', '68%'],
          center: ['50%', '44%'],
          label: { formatter: '{b}: {c}' },
          data: management.customer_source_distribution.map((item) => ({
            name: item.source ?? '未设置',
            value: item.count,
          })),
        },
      ],
    }
    sourceChart.setOption(sourceOption)
  }

  if (levelChartElement.value) {
    levelChart = init(levelChartElement.value)
    const levelOption: EChartsOption = {
      tooltip: { trigger: 'axis' },
      grid: { left: 36, right: 20, top: 18, bottom: 30, containLabel: true },
      xAxis: {
        type: 'category',
        data: management.customer_level_distribution.map((item) => item.level),
      },
      yAxis: { type: 'value', minInterval: 1 },
      series: [
        {
          type: 'bar',
          barMaxWidth: 42,
          itemStyle: { color: '#256b61', borderRadius: [4, 4, 0, 0] },
          data: management.customer_level_distribution.map((item) => item.count),
        },
      ],
    }
    levelChart.setOption(levelOption)
  }

  const buildTrendOption = (
    points: DashboardSummary['management']['customer_new_trend'],
    color: string,
  ): EChartsOption => ({
    tooltip: { trigger: 'axis' },
    grid: { left: 36, right: 20, top: 18, bottom: 38, containLabel: true },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: points.map((item) => item.date.slice(5)),
    },
    yAxis: { type: 'value', minInterval: 1 },
    series: [
      {
        type: 'line',
        smooth: true,
        showSymbol: false,
        lineStyle: { color, width: 3 },
        areaStyle: { color: `${color}1A` },
        data: points.map((item) => item.count),
      },
    ],
  })

  if (customerTrendChartElement.value) {
    customerTrendChart = init(customerTrendChartElement.value)
    customerTrendChart.setOption(buildTrendOption(management.customer_new_trend, '#256b61'))
  }
  if (followUpTrendChartElement.value) {
    followUpTrendChart = init(followUpTrendChartElement.value)
    followUpTrendChart.setOption(buildTrendOption(management.follow_up_trend, '#b7791f'))
  }
}

function resizeCharts() {
  sourceChart?.resize()
  levelChart?.resize()
  customerTrendChart?.resize()
  followUpTrendChart?.resize()
}

function openCustomer(customerId: string) {
  void router.push({ name: 'customer-detail', params: { customerId } })
}

watch(summary, async () => {
  await nextTick()
  createCharts()
})

onMounted(() => {
  window.addEventListener('resize', resizeCharts)
  void loadSummary()
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', resizeCharts)
  disposeCharts()
})
</script>

<template>
  <section class="page-view dashboard-page">
    <div class="page-heading dashboard-heading">
      <div>
        <p class="eyebrow">CRM / WORKBENCH</p>
        <h1>工作台</h1>
        <p class="page-description">个人待办和可见业务数据的实时汇总。</p>
      </div>
      <div class="dashboard-toolbar">
        <el-date-picker
          v-model="selectedRange"
          type="daterange"
          value-format="YYYY-MM-DD"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          :disabled-date="(date: Date) => date > new Date()"
          @change="onRangeChange"
        />
        <el-button :loading="loading" @click="loadSummary">刷新</el-button>
      </div>
    </div>

    <el-alert v-if="loadError" :title="loadError" type="error" show-icon :closable="false">
      <template #default
        ><el-button link type="primary" @click="loadSummary">重试</el-button></template
      >
    </el-alert>

    <template v-if="summary">
      <section class="dashboard-section">
        <div class="section-heading-row">
          <div>
            <h2>个人工作台</h2>
            <p>仅展示你的客户、跟进和提醒数据。</p>
          </div>
          <el-tag type="success" effect="plain"
            >{{ summary.range.start_date }} 至 {{ summary.range.end_date }}</el-tag
          >
        </div>
        <div class="dashboard-stat-grid">
          <el-card shadow="never" class="dashboard-stat-card"
            ><span>我的客户总数</span
            ><strong>{{ summary.personal.my_customer_total }}</strong></el-card
          >
          <el-card shadow="never" class="dashboard-stat-card"
            ><span>本月新增客户</span
            ><strong>{{ summary.personal.current_month_new_customers }}</strong></el-card
          >
          <el-card shadow="never" class="dashboard-stat-card"
            ><span>本月跟进次数</span
            ><strong>{{ summary.personal.current_month_follow_up_count }}</strong></el-card
          >
          <el-card shadow="never" class="dashboard-stat-card"
            ><span>今日待办</span
            ><strong>{{ summary.personal.today_pending_reminder_count }}</strong></el-card
          >
          <el-card shadow="never" class="dashboard-stat-card dashboard-stat-warning"
            ><span>已逾期提醒</span
            ><strong>{{ summary.personal.overdue_reminder_count }}</strong></el-card
          >
        </div>
        <el-card shadow="never" class="dashboard-panel">
          <template #header
            ><div class="panel-heading">
              <strong>最近跟进记录</strong><span>按可见客户范围展示</span>
            </div></template
          >
          <el-table
            :data="summary.personal.recent_follow_ups"
            row-key="id"
            class="data-table"
            size="small"
          >
            <el-table-column label="时间" min-width="170"
              ><template #default="scope">{{
                new Date(scope.row.followed_at).toLocaleString()
              }}</template></el-table-column
            >
            <el-table-column label="客户" min-width="160"
              ><template #default="scope"
                ><button
                  class="related-name-button"
                  type="button"
                  @click="openCustomer(scope.row.customer_id)"
                >
                  <strong>{{ scope.row.customer_name }}</strong>
                </button></template
              ></el-table-column
            >
            <el-table-column label="跟进人" width="120" prop="user_name" />
            <el-table-column label="方式" width="100"
              ><template #default="scope">{{
                methodLabels[scope.row.method]
              }}</template></el-table-column
            >
            <el-table-column label="内容" min-width="280" prop="content" show-overflow-tooltip />
            <template #empty><el-empty description="暂无跟进记录" /></template>
          </el-table>
        </el-card>
      </section>

      <section class="dashboard-section">
        <div class="section-heading-row">
          <div>
            <h2>管理工作台</h2>
            <p>统计结果已按当前账号的数据范围过滤。</p>
          </div>
        </div>
        <div class="dashboard-stat-grid management-stat-grid">
          <el-card shadow="never" class="dashboard-stat-card"
            ><span>可见客户总数</span
            ><strong>{{ summary.management.customer_total }}</strong></el-card
          >
          <el-card shadow="never" class="dashboard-stat-card"
            ><span>可见部门数</span
            ><strong>{{ summary.management.department_customer_counts.length }}</strong></el-card
          >
          <el-card shadow="never" class="dashboard-stat-card"
            ><span>可见负责人</span
            ><strong>{{ summary.management.employee_customer_counts.length }}</strong></el-card
          >
        </div>
        <div class="dashboard-chart-grid">
          <el-card shadow="never" class="dashboard-panel chart-panel"
            ><template #header
              ><div class="panel-heading"><strong>客户来源分布</strong></div></template
            >
            <div
              v-if="summary.management.customer_source_distribution.length"
              ref="sourceChartElement"
              class="dashboard-chart" />
            <el-empty v-else description="暂无客户来源数据"
          /></el-card>
          <el-card shadow="never" class="dashboard-panel chart-panel"
            ><template #header
              ><div class="panel-heading"><strong>客户等级分布</strong></div></template
            >
            <div
              v-if="summary.management.customer_level_distribution.length"
              ref="levelChartElement"
              class="dashboard-chart" />
            <el-empty v-else description="暂无客户等级数据"
          /></el-card>
          <el-card shadow="never" class="dashboard-panel chart-panel dashboard-chart-wide"
            ><template #header
              ><div class="panel-heading">
                <strong>客户新增趋势</strong
                ><span>{{
                  hasTrendData(summary.management.customer_new_trend) ? '按日' : '当前范围无数据'
                }}</span>
              </div></template
            >
            <div
              v-if="hasTrendData(summary.management.customer_new_trend)"
              ref="customerTrendChartElement"
              class="dashboard-chart dashboard-trend-chart" />
            <el-empty v-else description="当前范围暂无新增客户"
          /></el-card>
          <el-card shadow="never" class="dashboard-panel chart-panel dashboard-chart-wide"
            ><template #header
              ><div class="panel-heading">
                <strong>跟进次数趋势</strong
                ><span>{{
                  hasTrendData(summary.management.follow_up_trend) ? '按日' : '当前范围无数据'
                }}</span>
              </div></template
            >
            <div
              v-if="hasTrendData(summary.management.follow_up_trend)"
              ref="followUpTrendChartElement"
              class="dashboard-chart dashboard-trend-chart" />
            <el-empty v-else description="当前范围暂无跟进记录"
          /></el-card>
        </div>
        <div class="dashboard-breakdown-grid">
          <el-card shadow="never" class="dashboard-panel"
            ><template #header
              ><div class="panel-heading"><strong>部门客户数量</strong></div></template
            ><el-table :data="summary.management.department_customer_counts" size="small"
              ><el-table-column prop="department_name" label="部门" /><el-table-column
                prop="count"
                label="客户数"
                width="100" /><template #empty
                ><el-empty description="暂无部门数据" /></template></el-table
          ></el-card>
          <el-card shadow="never" class="dashboard-panel"
            ><template #header
              ><div class="panel-heading"><strong>负责人客户数量</strong></div></template
            ><el-table :data="summary.management.employee_customer_counts" size="small"
              ><el-table-column prop="user_name" label="负责人" /><el-table-column
                prop="count"
                label="客户数"
                width="100" /><template #empty
                ><el-empty description="暂无负责人数据" /></template></el-table
          ></el-card>
        </div>
      </section>
    </template>

    <el-skeleton v-else-if="loading" :rows="10" animated />
    <el-empty v-else description="暂无工作台数据" />
  </section>
</template>
