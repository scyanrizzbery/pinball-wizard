<template>
  <transition name="toast-slide">
    <div class="combo-toast" v-if="comboActive && comboCount > 5">
      <div class="combo-content" :class="{ 'pulse-anim': triggerAnim }">
        <div class="count" :style="gradientStyle">{{ comboCount }}x</div>
        <div class="label">COMBO</div>
      </div>
      
      <div class="timer-bar-container">
        <div class="timer-bar" :style="{ width: (timerPercent * 100) + '%' }"></div>
      </div>
    </div>
  </transition>
</template>

<script setup>
import { computed, ref, watch } from 'vue'

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
  }
})

const triggerAnim = ref(false)

watch(() => props.comboCount, (newVal, oldVal) => {
  if (newVal > oldVal) {
    triggerAnim.value = false
    setTimeout(() => {
      triggerAnim.value = true
    }, 10)
  }
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
  top: 15%; /* Slightly higher */
  left: 50%;
  transform: translateX(-50%);
  z-index: 1000; /* High z-index to ensure visibility */
  
  background: rgba(20, 20, 20, 0.85); /* Dark semi-transparent background */
  backdrop-filter: blur(8px); /* Blur effect */
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 16px;
  padding: 20px 60px 20px 40px; /* Significantly increased right padding */
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5), 0 0 20px rgba(255, 255, 255, 0.05) inset;
  
  display: flex;
  flex-direction: column;
  align-items: center;
  pointer-events: none;
  min-width: 200px; /* Increased min-width */
}

.combo-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  line-height: 1;
  margin-bottom: 10px;
  padding-right: 10px; /* Extra safety padding for italic text */
}

.count {
  font-size: 4.5rem; /* Slightly smaller than before but still huge */
  font-weight: 900;
  font-family: 'Arial Black', sans-serif;
  font-style: italic;
  letter-spacing: -2px;
}

.label {
  font-size: 1.2rem;
  font-weight: 700;
  color: #fff;
  letter-spacing: 4px;
  margin-top: -5px;
  text-transform: uppercase;
  opacity: 0.9;
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
  transform: translate(-50%, -20px) scale(0.9);
}
</style>
