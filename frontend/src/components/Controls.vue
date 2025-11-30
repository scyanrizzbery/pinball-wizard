<template>
  <div class="control-group" style="align-items: center; justify-content: center; gap: 15px;">
    <div style="display: flex; flex-direction: column; gap: 8px; min-width: 120px;">
      <button class="control-btn desktop-only" :class="{ pressed: buttonStates.left }"
        style="width: 100%; padding: 12px 20px; font-size: 16px; font-weight: bold;"
        @mousedown="handleInput('KeyZ', 'down')" @mouseup="handleInput('KeyZ', 'up')">Left
        Flipper</button>
      <button class="control-btn desktop-only" :class="{ pressed: buttonStates.nudgeLeft }"
        style="width: 100%; padding: 8px 15px; font-size: 12px;" @mousedown="handleInput('ShiftLeft', 'down')"
        @mouseup="handleInput('ShiftLeft', 'up')">Nudge Left</button>
    </div>
    <button class="control-btn desktop-only" :class="{ pressed: buttonStates.launch }"
      style="width: 90px; height: 90px; border-radius: 50%; background-color: #d32f2f; border-color: #b71c1c; font-size: 16px; font-weight: bold; padding: 0; display: flex; align-items: center; justify-content: center;"
      @mousedown="handleInput('Space', 'down')" @mouseup="handleInput('Space', 'up')">Launch</button>
    <div style="display: flex; flex-direction: column; gap: 8px; min-width: 120px;">
      <button class="control-btn desktop-only" :class="{ pressed: buttonStates.right }"
        style="width: 100%; padding: 12px 20px; font-size: 16px; font-weight: bold;"
        @mousedown="handleInput('Slash', 'down')" @mouseup="handleInput('Slash', 'up')">Right
        Flipper</button>
      <button class="control-btn desktop-only" :class="{ pressed: buttonStates.nudgeRight }"
        style="width: 100%; padding: 8px 15px; font-size: 12px;" @mousedown="handleInput('ShiftRight', 'down')"
        @mouseup="handleInput('ShiftRight', 'up')">Nudge Right</button>
    </div>
  </div>
  <div class="toggle-row">
    <button class="toggle-btn" :class="{ active: toggles.ai }" @click="$emit('toggle-ai')">
      <span class="toggle-dot"></span>
      AI: {{ toggles.ai ? 'ON' : 'OFF' }}
    </button>
    <button class="toggle-btn" :class="{ active: toggles.autoStart }" @click="$emit('toggle-auto-start')">
      <span class="toggle-dot"></span>
      Auto-Start: {{ toggles.autoStart ? 'ON' : 'OFF' }}
    </button>
  </div>
</template>

<script setup>
defineProps({
  buttonStates: Object,
  toggles: Object
})

const emit = defineEmits(['input', 'toggle-ai', 'toggle-auto-start'])

const handleInput = (key, type) => {
  emit('input', key, type)
}
</script>

<style scoped>
.control-group {
  display: flex;
  gap: 10px;
  margin-bottom: 10px;
  flex-wrap: wrap;
}

.control-btn {
  flex: 1;
  padding: 10px 15px;
  background-color: #333;
  color: #fff;
  border: none;
  border-radius: 5px;
  cursor: pointer;
  font-size: 14px;
  transition: background-color 0.2s;
  min-width: 100px;
  margin: 0 5px;
}

.control-btn:hover {
  background-color: #444;
}

.control-btn:active {
  background-color: #555;
}

.control-btn.active {
  background-color: #4caf50;
}

.control-btn.pressed {
  background-color: #4caf50 !important;
  border-color: #45a049 !important;
  box-shadow: 0 0 15px rgba(76, 175, 80, 0.8);
}

.control-btn:disabled {
  background-color: #222;
  color: #666;
  cursor: not-allowed;
}

.toggle-row {
  display: flex;
  gap: 10px;
  margin: 10px;
  width: 100%;
}

.toggle-btn {
  flex: 1;
  padding: 10px 15px;
  background-color: #333;
  color: #fff;
  border: 1px solid #444;
  border-radius: 5px;
  cursor: pointer;
  font-size: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  transition: all 0.2s;
}

.toggle-btn:hover {
  background-color: #444;
}

.toggle-btn.active {
  border-color: #4caf50;
}

.toggle-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: #555;
  box-shadow: inset 0 1px 2px rgba(0, 0, 0, 0.5);
}

.toggle-btn.active .toggle-dot {
  background-color: #4caf50;
  box-shadow: 0 0 5px #4caf50;
}

@media (max-width: 900px) {
  .desktop-only {
    display: none !important;
  }
}
</style>
