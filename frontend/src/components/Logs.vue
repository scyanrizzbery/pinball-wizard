<template>
  <div class="console">
    <div class="game-log-container" ref="logContainer">
      <div v-for="(log, index) in logs" :key="index" class="log-entry">{{ log }}</div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'

const props = defineProps({
  logs: Array
})

const logContainer = ref(null)

watch(() => props.logs.length, () => {
  nextTick(() => {
    if (logContainer.value) {
      logContainer.value.scrollTop = logContainer.value.scrollHeight
    }
  })
})
</script>

<style scoped>
.console {
  grid-area: logs;
  height: 100%;
  overflow: hidden;
}

.game-log-container {
  flex: 0 0 auto;
  overflow-y: auto;
  background: #0a0a0a;
  border: 1px solid #333;
  border-radius: 4px;
  padding: 10px;
  font-family: 'Courier New', monospace;
  font-size: 0.85em;
  text-align: left;
  height: 100%;
  width: 100%;
  max-height: 15em;
  box-sizing: border-box;
}

.log-entry {
  padding: 2px 0;
  color: #4caf50;
}

@media (max-width: 1200px) {
  .game-log-container {
    flex-direction: row;
  }
}
</style>
