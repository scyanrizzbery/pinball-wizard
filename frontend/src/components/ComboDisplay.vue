<template>
  <transition name="toast-slide">
    <div class="combo-toast" v-if="comboActive && comboCount >= 10">
      <div class="combo-content" :class="{ 'pulse-anim': triggerAnim }">
        <div class="count" :style="gradientStyle">{{ Math.floor(comboCount) }}x</div>
        <div class="label">COMBO</div>
        <div class="multiplier" v-if="scoreMultiplier > 1">{{ Math.floor(scoreMultiplier) }}x Multiplier</div>
        <div class="scale-indicator" v-if="comboCount >= 10">🎵 {{ currentScaleName }}</div>
      </div>
      
      <div class="timer-bar-container">
        <div class="timer-bar" :style="{ width: (timerPercent * 100) + '%' }"></div>
      </div>
    </div>
  </transition>
</template>

<script setup>
import { computed, ref, watch, onMounted } from 'vue'
import SoundManager from '../utils/SoundManager'

const props = defineProps({
  comboCount: {
    type: Number,
    default: 0
  },
  comboTimer: {
    type: Number,
    default: 0
  },
  comboActive: {
    type: Boolean,
    default: false
  },
  maxTimer: {
    type: Number,
    default: 3.0
  },
  scoreMultiplier: {
    type: Number,
    default: 1.0
  }
})

const triggerAnim = ref(false)
const currentScaleName = ref('Major')

// Update scale name when combo changes
watch(() => props.comboCount, (newVal, oldVal) => {
  if (newVal > oldVal) {
    triggerAnim.value = false
    setTimeout(() => {
      triggerAnim.value = true
    }, 10)
  }

  // Update scale name display
  if (newVal >= 10) {
    const scale = SoundManager.getCurrentScale()
    currentScaleName.value = scale.name
  }
})

onMounted(() => {
  // Initialize scale name
  const scale = SoundManager.getCurrentScale()
  currentScaleName.value = scale.name
})

const timerPercent = computed(() => {
  return Math.max(0, Math.min(1, props.comboTimer / props.maxTimer))
})

const gradientStyle = computed(() => {
  if (props.comboCount < 5) {
    // Yellow/Gold (First) - Smallest
    return {
      background: 'linear-gradient(180deg, #f8cdda 0%, #f5af19 100%)',
      '-webkit-background-clip': 'text',
      '-webkit-text-fill-color': 'transparent',
      'filter': 'drop-shadow(0 0 5px rgba(245, 175, 25, 0.3))',
      'transform': 'scale(1.0)'
    }
  } else if (props.comboCount < 10) {
    // Purple (Second) - Medium
    return {
      background: 'linear-gradient(180deg, #da22ff 0%, #9733ee 100%)',
      '-webkit-background-clip': 'text',
      '-webkit-text-fill-color': 'transparent',
      'filter': 'drop-shadow(0 0 8px rgba(218, 34, 255, 0.4))',
      'transform': 'scale(1.25)'
    }
  } else {
    // Blue/Cyan (Third) - Largest
    return {
      background: 'linear-gradient(180deg, #00d2ff 0%, #3a7bd5 100%)',
      '-webkit-background-clip': 'text',
      '-webkit-text-fill-color': 'transparent',
      'filter': 'drop-shadow(0 0 15px rgba(0, 210, 255, 0.6))',
      'transform': 'scale(1.5)'
    }
  }
})
</script>

<style scoped>
.combo-toast {
  position: absolute;
  top: 10px;
  right: 10px;
  left: auto;
  transform: none;
  z-index: 1000;
  
  background: rgba(20, 20, 20, 0.85);
  backdrop-filter: blur(8px);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 12px;
  padding: 12px 24px;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5), 0 0 20px rgba(255, 255, 255, 0.05) inset;
  
  display: flex;
  flex-direction: column;
  align-items: center;
  pointer-events: none;
  min-width: 120px;
  transition: transform 0.3s ease, top 0.3s ease, right 0.3s ease;
}

@media (min-width: 1920px) {
  .combo-toast {
    transform: scale(1.3);
    transform-origin: top right;
  }
}

:global(:fullscreen) .combo-toast {
  transform: scale(1.5);
  transform-origin: top right;
  top: 40px;
  right: 120px; /* Moved further left from 30px */
}

.combo-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  line-height: 1;
  margin-bottom: 10px;
}

.count {
  font-size: 2.5rem;
  margin: 5px;
  font-weight: 900;
  font-family: 'Arial Black', sans-serif;
  letter-spacing: -1px;
}

.label {
  font-size: 0.9rem;
  font-weight: 700;
  color: #fff;
  letter-spacing: 3px;
  margin-top: -3px;
  text-transform: uppercase;
  opacity: 0.9;
}

.multiplier {
  font-size: 0.65rem;
  font-weight: 600;
  color: #ffeb3b;
  letter-spacing: 1px;
  margin-top: 2px;
  text-transform: uppercase;
  opacity: 0.95;
  text-shadow: 0 0 8px rgba(255, 235, 59, 0.6);
}

.scale-indicator {
  font-size: 0.7rem;
  font-weight: 700;
  color: #00ff88;
  letter-spacing: 1.5px;
  margin-top: 4px;
  text-transform: uppercase;
  opacity: 1;
  text-shadow: 0 0 10px rgba(0, 255, 136, 0.8);
  animation: scale-glow 2s ease-in-out infinite;
}

@keyframes scale-glow {
  0%, 100% {
    text-shadow: 0 0 10px rgba(0, 255, 136, 0.8);
  }
  50% {
    text-shadow: 0 0 20px rgba(0, 255, 136, 1), 0 0 30px rgba(0, 255, 136, 0.6);
  }
}

.timer-bar-container {
  width: 100%;
  height: 4px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 2px;
  overflow: hidden;
}

.timer-bar {
  height: 100%;
  background: #fff;
  box-shadow: 0 0 8px rgba(255, 255, 255, 0.8);
  transition: width 0.1s linear;
}

/* Animations */
.pulse-anim {
  animation: toast-bump 0.2s cubic-bezier(0.175, 0.885, 0.32, 1.275);
}

@keyframes toast-bump {
  0% { transform: scale(1); }
  50% { transform: scale(1.15); }
  100% { transform: scale(1); }
}

/* Enter/Leave Transitions */
.toast-slide-enter-active,
.toast-slide-leave-active {
  transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.toast-slide-enter-from,
.toast-slide-leave-to {
  opacity: 0;
  transform: translateX(20px) scale(0.9);
}

@media (max-width: 690px) {
  .combo-toast {
    top: 10px;
    left: auto;
    right: 10px;
    transform: none;
    min-width: 100px;
    padding: 8px 16px;
    background: rgba(0, 0, 0, 0.4); /* More transparent */
    backdrop-filter: blur(2px);
    border-radius: 10px;
    box-shadow: 0 4px 10px rgba(0, 0, 0, 0.3);
  }

  .count {
    font-size: 1.8rem;
    letter-spacing: -1px;
  }

  .label {
    font-size: 0.6rem;
    letter-spacing: 1px;
    margin-top: -2px;
  }
  
  .combo-content {
    margin-bottom: 5px;
    padding-right: 0;
  }

  /* Override transition for non-centered state */
  .toast-slide-enter-from,
  .toast-slide-leave-to {
    transform: translateY(-10px) scale(0.9);
  }
}
</style>
