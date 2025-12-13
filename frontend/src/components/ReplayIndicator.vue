<template>
  <div class="replay-indicator" :class="{ 'is-fullscreen': isFullscreen }" v-if="hash">
    <div class="replay-badge">REPLAY</div>
    <div class="replay-hash">{{ shortHash }}</div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  hash: string | null
  isFullscreen?: boolean
}>()

const shortHash = computed(() => {
  if (!props.hash) return ''
  return props.hash.substring(0, 8)
})
</script>

<style scoped>
/* Replay Indicator - High priority */
.replay-overlay {
  z-index: 3050; /* Above Game Over, below Training */
  background: transparent;
  pointer-events: none;
}

.replay-icon {
  font-size: 1.5em;
  color: white;
  animation: blink 1s infinite;
}

.replay-indicator {
  position: absolute;
  bottom: 1px;
  left: 1px;
  background: rgba(255, 0, 0, 0.2);
  border: 1px solid rgba(255, 0, 0, 0.5);
  border-radius: 6px;
  padding: 5px 10px;
  display: flex;
  align-items: center;
  gap: 8px;
  z-index: 1500;
  backdrop-filter: blur(4px);
  pointer-events: none;
  animation: pulse 2s infinite;
}

.replay-badge {
  font-size: 0.7rem;
  font-weight: 800;
  color: #ff4444;
  letter-spacing: 0.5px;
  animation: pulse 2s infinite;
}

.replay-hash {
  font-family: 'Courier New', monospace;
  font-size: 0.8rem;
  color: rgba(255, 255, 255, 0.8);
}

.replay-indicator.is-fullscreen {
  position: fixed;
  top: auto;
  bottom: 30px;
  left: 30px;
  right: auto;
  
  background: rgba(0, 0, 0, 0.4);
  padding: 8px 16px;
  border-radius: 8px;
  transform: scale(1.2);
  transform-origin: bottom left;
}

@keyframes pulse {
  0% { opacity: 0.7; }
  50% { opacity: 1; text-shadow: 0 0 5px rgba(255, 0, 0, 0.5); }
  100% { opacity: 0.7; }
}
</style>
