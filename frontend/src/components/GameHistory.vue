<template>
  <div id="history-container">
    <h3>Game History <span class="game-count">({{ gamesPlayed }} Games)</span></h3>
    
    <div v-if="historyStats" class="stats-row">
      <div class="stat-item">
        <span class="stat-label">Min</span>
        <span class="stat-value">{{ historyStats.min.toLocaleString() }}</span>
      </div>
      <div class="stat-item">
        <span class="stat-label">Max</span>
        <span class="stat-value">{{ historyStats.max.toLocaleString() }}</span>
      </div>
      <div class="stat-item">
        <span class="stat-label">Avg</span>
        <span class="stat-value">{{ historyStats.mean.toLocaleString() }}</span>
      </div>
    </div>

    <div class="sparkline-container">
      <div v-if="!showChart"
        style="flex: 1; display: flex; align-items: center; justify-content: center; color: #666; font-style: italic;">
        Play at least 3 games to see history
      </div>
      <highcharts v-show="showChart" :options="chartOptions" ref="chartRef" style="width:100%; flex: 1;"></highcharts>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import { Chart } from 'highcharts-vue'

const props = defineProps({
  gameHistory: { type: Array, default: () => [] },
  gamesPlayed: { type: Number, default: 0 }
})

const chartRef = ref(null)
const isVertical = ref(window.innerWidth >= 1200)

// Stable history to prevent flickering (only update when content actually changes)
const stableGameHistory = ref([])

watch(() => props.gameHistory, (newVal) => {
  // Check if update is needed
  if (newVal.length !== stableGameHistory.value.length) {
    stableGameHistory.value = [...newVal]
    return
  }
  
  // Check last item (most likely to change)
  if (newVal.length > 0) {
    const lastNew = newVal[newVal.length - 1]
    const lastOld = stableGameHistory.value[stableGameHistory.value.length - 1]
    if (lastNew.timestamp !== lastOld.timestamp || lastNew.score !== lastOld.score) {
      stableGameHistory.value = [...newVal]
    }
  }
}, { deep: true, immediate: true })

const updateOrientation = () => {
  // Vertical layout if desktop (>1200px) OR medium/square viewport (600px-1200px)
  // Basically, horizontal only on very small screens (<600px) or if we decide otherwise.
  // User requested vertical on medium viewport.
  isVertical.value = window.innerWidth >= 600
}

window.addEventListener('resize', updateOrientation)

const showChart = computed(() => {
  return stableGameHistory.value.filter(g => g.type === 'game').length >= 3
})

const historyStats = computed(() => {
  const games = stableGameHistory.value.filter(g => g.type === 'game')
  if (games.length === 0) return null
  
  const scores = games.map(g => g.score)
  const min = Math.min(...scores)
  const max = Math.max(...scores)
  const sum = scores.reduce((a, b) => a + b, 0)
  const mean = Math.round(sum / scores.length)
  
  return { min, max, mean, count: games.length }
})

const chartOptions = computed(() => {
  const seriesData = []
  const plotLines = []

  const games = stableGameHistory.value.filter(g => g.type === 'game')
  const maxScore = games.length > 0 ? Math.max(...games.map(g => g.score)) : 0

  stableGameHistory.value.forEach((g, i) => {
    const timestamp = g.timestamp * 1000 // Convert to ms
    
    if (g.type === 'game') {
      // Only mark the LAST occurrence of the high score to avoid duplicates
      // Find the index of the last occurrence
      const lastHighScoreIndex = stableGameHistory.value.findLastIndex(h => h.type === 'game' && h.score === maxScore)
      const isHighScore = i === lastHighScoreIndex && g.score > 0

      seriesData.push({
        x: timestamp,
        y: g.score,
        marker: {
          enabled: isHighScore,
          fillColor: '#ffeb3b',
          radius: 8,
          lineWidth: 2,
          lineColor: '#ffffff',
          symbol: 'circle'
        }
      })
    } else if (g.type === 'model_change') {
      plotLines.push({
        color: '#ff9800',
        width: 2,
        value: timestamp,
        zIndex: 5,
        label: {
          text: `<span style="font-size: 8px;">${g.model}</span>`,
          rotation: isVertical.value ? 0 : 90,
          align: isVertical.value ? 'right' : 'left',
          x: isVertical.value ? -5 : 10,
          y: isVertical.value ? 10 : 0,
          style: {
            color: '#ffffff',
            fontWeight: 'bold'
          }
        }
      })
    } else if (g.type === 'layout_change') {
      plotLines.push({
        color: '#2196f3',
        width: 2,
        value: timestamp,
        zIndex: 5,
        label: {
          text: `<span style="font-size: 8px;">${g.layout}</span>`,
          rotation: isVertical.value ? 0 : 90,
          align: isVertical.value ? 'right' : 'left',
          x: isVertical.value ? -5 : 10,
          y: isVertical.value ? 10 : 0,
          style: {
            color: '#ffffff',
            fontWeight: 'bold'
          }
        }
      })
    } else if (g.type === 'settings_change') {
      plotLines.push({
        color: '#9c27b0',
        width: 1,
        value: timestamp,
        zIndex: 5,
        label: {
          text: `<span style="font-size: 8px;">⚙️</span>`,
          rotation: 0,
          align: 'center',
          y: isVertical.value ? 20 : 0,
          style: {
            color: '#ffffff',
            fontWeight: 'bold'
          }
        },
        // Custom tooltip for settings
        events: {
          mouseover: function (e) {
            // Highcharts doesn't support tooltips on plotLines natively easily,
            // but we can rely on the point tooltip if we added a dummy point,
            // or just let the user see the icon.
            // For now, let's just show the icon.
          }
        }
      })
    }
  })

  return {
    chart: {
      type: 'area',
      backgroundColor: 'transparent',
      margin: [10, 10, 50, 60], // Increased bottom/left margins for axis visibility
      inverted: isVertical.value,
      height: null,
      reflow: true,
      animation: false
    },
    title: { text: null },
    credits: { enabled: false },
    legend: { enabled: false },
    xAxis: {
      type: 'datetime',
      visible: true,
      minPadding: 0,
      maxPadding: 0,
      labels: {
        style: { color: '#aaa' },
        format: '{value:%H:%M}'
      },
      gridLineColor: '#333',
      plotLines: plotLines
    },
    yAxis: {
      title: { text: null },
      gridLineColor: '#333',
      labels: {
        style: { color: '#aaa' }
      }
    },
    plotOptions: {
      area: {
        fillColor: {
          linearGradient: { x1: 0, y1: 0, x2: 0, y2: 1 },
          stops: [
            [0, 'rgba(76, 175, 80, 0.5)'],
            [1, 'rgba(76, 175, 80, 0.1)']
          ]
        },
        lineColor: '#4caf50',
        lineWidth: 2,
        marker: {
          enabled: false,
          radius: 3,
          states: {
            hover: { enabled: true }
          }
        },
        threshold: null,
        animation: false
      }
    },
    tooltip: {
      backgroundColor: 'rgba(0, 0, 0, 0.85)',
      style: { color: '#fff' },
      headerFormat: '',
      pointFormatter: function () {
        return `<b>Score: ${this.y.toLocaleString()}</b><br />Time: ${new Date(this.x).toLocaleTimeString()}`
      }
    },
    series: [{
      name: 'Score',
      data: seriesData
    }]
  }
})

watch(showChart, (newVal) => {
  if (newVal) {
    nextTick(() => {
      if (chartRef.value && chartRef.value.chart) {
        // Safeguard against negative height
        const container = chartRef.value.$el.closest('.sparkline-container')
        if (container && container.clientHeight > 0) {
           chartRef.value.chart.reflow()
        }
      }
    })
  }
})
</script>
<style scoped>
#history-container {
  grid-area: history;
  background: #1e1e1e;
  padding: 15px;
  border-radius: 8px;
  border: 1px solid #3d3d3d;
  display: flex;
  flex-direction: column;
  gap: 10px;
  height: 100%;
  min-height: 600px;
  max-height: 850px;
  overflow: hidden;
}

#history-container h3 {
  margin: 0 0 10px 0;
  font-size: 1.1em;
  color: #4caf50;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.game-count {
  font-size: 0.8em;
  color: #666;
  font-weight: normal;
}

.stats-row {
  display: flex;
  justify-content: space-around;
  margin-bottom: 5px;
  background: #2a2a2a;
  padding: 10px;
  border-radius: 6px;
  flex-shrink: 0;
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.stat-label {
  font-size: 0.8em;
  color: #aaa;
  text-transform: uppercase;
  margin-bottom: 2px;
}

.stat-value {
  font-size: 1.1em;
  font-weight: bold;
  color: #fff;
}

.sparkline-container {
  flex: 1;
  background: #0a0a0a;
  border: 1px solid #333;
  border-radius: 4px;
  padding: 10px;
  position: relative;
  height: 100%;
  min-height: 150px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

@media (max-width: 1200px) {
  #history-container {
    height: auto;
    min-height: 250px;
    max-height: 300px;
  }
}

@media (min-width: 600px) and (max-width: 900px) {
  #history-container {
    height: 100%;
    min-height: 600px;
    max-height: 850px;
  }
}

@media (max-width: 690px) {
  #history-container {
    min-height: 200px;
    max-height: 300px;
  }
}
</style>
