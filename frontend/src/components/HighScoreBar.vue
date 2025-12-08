<template>
  <div class="highscore-bar-container" :class="{ 'fullscreen': isFullscreen }">
    <div class="bar-track">
      <div 
        class="bar-fill" 
        :style="{ height: fillPercentage + '%' }"
        :class="{ 'record-broken': isRecordBroken }"
      >
        <div class="glow-tip"></div>
      </div>
    </div>
    <div class="marker-label">High Score</div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  score: {
    type: Number,
    default: 0
  },
  highScore: {
    type: Number,
    default: 10000
  },
  isFullscreen: {
    type: Boolean,
    default: false
  }
})

const isRecordBroken = computed(() => {
  return props.score > props.highScore
})

const fillPercentage = computed(() => {
  if (props.highScore <= 0) return 0
  const ratio = props.score / props.highScore
  // Cap at 100% physically, but maybe show different effects
  return Math.min(ratio * 100, 100)
})
</script>

<style scoped>
.highscore-bar-container {
  position: absolute;
  right: -30px;
  top: 5%;
  bottom: 5%;
  width: 20px;
  display: flex;
  flex-direction: column;
  align-items: center;
  z-index: 10;
  pointer-events: auto; /* Allow tooltips if we add them */
}

.highscore-bar-container.fullscreen {
  right: 10px; /* Inside in fullscreen? Or still outside? Keep inside for fullscreen usually */
  width: 20px;
}

.bar-track {
  flex: 1;
  width: 100%;
  background: rgba(0, 0, 0, 0.5);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 6px;
  position: relative;
  overflow: hidden;
  backdrop-filter: blur(2px);
}

.bar-fill {
  position: absolute;
  bottom: 0;
  left: 0;
  width: 100%;
  background: linear-gradient(to top, #2196F3, #00BCD4);
  transition: height 0.5s cubic-bezier(0.25, 0.8, 0.25, 1);
  box-shadow: 0 0 10px rgba(33, 150, 243, 0.5);
}

.bar-fill.record-broken {
  background: linear-gradient(to top, #FFD700, #FFC107);
  box-shadow: 0 0 20px rgba(255, 215, 0, 0.8);
}

.glow-tip {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 2px;
  background: rgba(255, 255, 255, 0.8);
  box-shadow: 0 0 5px white;
}

.marker-label {
  margin-top: 5px;
  font-size: 10px;
  color: rgba(255, 255, 255, 0.6);
  text-transform: uppercase;
  text-shadow: 0 1px 2px black;
  writing-mode: vertical-rl;
  text-orientation: mixed;
  transform: rotate(180deg);
}

.highscore-bar-container.fullscreen .marker-label {
    font-size: 14px;
}
</style>
