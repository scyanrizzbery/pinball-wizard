<template>
  <transition name="toast-slide">
    <div class="toast-notification" :class="{ 'is-fullscreen': isFullscreen }" v-if="visible">
      <div class="toast-content">
        <div class="toast-icon">{{ icon }}</div>
        <div class="toast-text">
          <div class="toast-title">{{ title }}</div>
          <div class="toast-message" v-if="message">{{ message }}</div>
        </div>
      </div>
    </div>
  </transition>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  title: {
    type: String,
    required: true
  },
  message: {
    type: String,
    default: ''
  },
  icon: {
    type: String,
    default: '🛸'
  },
  duration: {
    type: Number,
    default: 3000
  },
  isFullscreen: {
    type: Boolean,
    default: false
  },
  show: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['hide'])

const visible = ref(false)
let hideTimer = null

// Watch for show prop changes
watch(() => props.show, (newVal) => {
  if (newVal) {
    visible.value = true
    
    // Clear existing timer
    if (hideTimer) {
      clearTimeout(hideTimer)
    }
    
    // Auto-hide after duration
    hideTimer = setTimeout(() => {
      visible.value = false
      emit('hide')
    }, props.duration)
  } else {
    visible.value = false
  }
})
</script>

<style scoped>
.toast-notification {
  position: absolute;
  top: 80px;
  left: 10px;
  z-index: 1001;
  
  background: rgba(20, 20, 20, 0.85);
  backdrop-filter: blur(6px);
  border: 1px solid rgba(255, 152, 0, 0.4);
  border-radius: 8px;
  padding: 8px 12px;
  box-shadow: 
    0 4px 12px rgba(255, 152, 0, 0.2),
    0 0 8px rgba(255, 152, 0, 0.05) inset;
  
  display: flex;
  align-items: center;
  pointer-events: none;
  min-width: 140px;
  max-width: 250px;
  transition: transform 0.2s ease, top 0.2s ease, left 0.2s ease;
}

.toast-content {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
}

.toast-icon {
  font-size: 1.3rem;
  line-height: 1;
  flex-shrink: 0;
  filter: drop-shadow(0 0 4px rgba(255, 152, 0, 0.4));
}

.toast-text {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.toast-title {
  font-size: 0.75rem;
  font-weight: 700;
  color: #ff9800;
  letter-spacing: 0.5px;
  text-transform: uppercase;
  text-shadow: 0 0 6px rgba(255, 152, 0, 0.4);
  line-height: 1.2;
}

.toast-message {
  font-size: 0.65rem;
  font-weight: 500;
  color: #fff;
  opacity: 0.8;
  line-height: 1.2;
}

/* Enter/Leave Transitions */
.toast-slide-enter-active,
.toast-slide-leave-active {
  transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.toast-slide-enter-from,
.toast-slide-leave-to {
  opacity: 0;
  transform: translateX(-20px) scale(0.85);
}

/* Mobile Responsive */
@media (max-width: 690px) {
  .toast-notification {
    top: 60px;
    left: 10px;
    right: auto;
    max-width: 200px;
    padding: 6px 10px;
    background: rgba(20, 20, 20, 0.8);
    backdrop-filter: blur(4px);
  }

  .toast-icon {
    font-size: 1.1rem;
  }

  .toast-title {
    font-size: 0.65rem;
    letter-spacing: 0.3px;
  }

  .toast-message {
    font-size: 0.6rem;
  }

  .toast-slide-enter-from,
  .toast-slide-leave-to {
    transform: translateX(-15px) scale(0.85);
  }
}

/* Fullscreen Overrides */
.toast-notification.is-fullscreen {
  top: 220px;
  right: 60px;
  padding: 30px 40px;
  border-radius: 16px;
  border-width: 3px;
  min-width: 300px;
  max-width: 500px;
}

.is-fullscreen .toast-icon {
  font-size: 3.5rem;
}

.is-fullscreen .toast-title {
  font-size: 1.8rem;
  letter-spacing: 2px;
}

.is-fullscreen .toast-message {
  font-size: 1.2rem;
}
</style>
