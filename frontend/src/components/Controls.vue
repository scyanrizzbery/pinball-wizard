<template>
  <div class="control-group" style="align-items: center; justify-content: center; gap: 15px;">
    <div style="display: flex; flex-direction: column; gap: 15px; min-width: 140px;">
      <button class="control-btn input-btn desktop-only" :class="{ pressed: buttonStates.left }"
        @mousedown="handleInput('KeyZ', 'down')" @mouseup="handleInput('KeyZ', 'up')" :disabled="disabled">
        <span>Left Flip</span>
        <span class="key-hint">Z Key</span>
      </button>
      <button class="control-btn input-btn desktop-only" :class="{ pressed: buttonStates.nudgeLeft }"
        style="font-size: 11px; padding: 10px;"
        @mousedown="handleInput('ShiftLeft', 'down')" @mouseup="handleInput('ShiftLeft', 'up')" :disabled="disabled">
        <span>Nudge Left</span>
        <span class="key-hint">L-Shift</span>
      </button>
    </div>
    
    <button class="control-btn launch-btn input-btn desktop-only" :class="{ pressed: buttonStates.launch }"
      @mousedown="handleInput('Space', 'down')" @mouseup="handleInput('Space', 'up')" :disabled="disabled">
      <span>LAUNCH</span>
      <span class="key-hint">Space</span>
    </button>
    
    <div style="display: flex; flex-direction: column; gap: 15px; min-width: 140px;">
      <button class="control-btn input-btn desktop-only" :class="{ pressed: buttonStates.right }"
        @mousedown="handleInput('Slash', 'down')" @mouseup="handleInput('Slash', 'up')" :disabled="disabled">
        <span>Right Flip</span>
        <span class="key-hint">/ Key</span>
      </button>
      <button class="control-btn input-btn desktop-only" :class="{ pressed: buttonStates.nudgeRight }"
        style="font-size: 11px; padding: 10px;"
        @mousedown="handleInput('ShiftRight', 'down')" @mouseup="handleInput('ShiftRight', 'up')" :disabled="disabled">
        <span>Nudge Right</span>
        <span class="key-hint">R-Shift</span>
      </button>
    </div>
  </div>
  <div class="toggle-row">
    <button class="toggle-btn" :class="{ active: toggles.ai }" @click="$emit('toggle-ai')" :disabled="disabled">
      <span class="toggle-dot"></span>
      AI: {{ toggles.ai ? 'ON' : 'OFF' }}
    </button>
    <button class="toggle-btn" :class="{ active: toggles.autoStart }" @click="$emit('toggle-auto-start')" :disabled="disabled">
      <span class="toggle-dot"></span>
      Auto-Start: {{ toggles.autoStart ? 'ON' : 'OFF' }}
    </button>
  </div>
</template>

<script setup>
defineProps({
  buttonStates: Object,
  toggles: Object,
  disabled: Boolean
})

const emit = defineEmits(['input', 'toggle-ai', 'toggle-auto-start'])

const handleInput = (key, type) => {
  emit('input', key, type)
}
</script>

<style scoped>
.control-group {
  display: flex;
  gap: 20px;
  margin-bottom: 15px;
  flex-wrap: nowrap;
  align-items: center;
  justify-content: center;
}

.control-btn {
  position: relative;
  flex: 1;
  padding: 15px;
  background: linear-gradient(180deg, #444 0%, #222 100%);
  color: #fff;
  border: 4px solid #111;
  border-bottom-width: 8px;
  border-radius: 12px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 1px;
  transition: all 0.1s cubic-bezier(0.25, 0.46, 0.45, 0.94);
  min-width: 140px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 0 #000, 0 5px 10px rgba(0,0,0,0.5);
  text-shadow: 0 -1px 1px rgba(0,0,0,0.5);
}

.control-btn:hover {
  filter: brightness(1.2);
  transform: translateY(-1px);
  box-shadow: 0 5px 0 #000, 0 7px 15px rgba(0,0,0,0.5);
}

.control-btn:active, .control-btn.pressed {
  transform: translateY(4px);
  border-bottom-width: 4px;
  box-shadow: 0 0 0 #000, 0 0 5px rgba(0,0,0,0.5) inset;
  background: linear-gradient(180deg, #222 0%, #111 100%);
  color: #aaa;
}

.control-btn.pressed {
  color: #fff;
  background: linear-gradient(180deg, #4caf50 0%, #2e7d32 100%);
  border-color: #1b5e20;
  box-shadow: 0 0 20px rgba(76, 175, 80, 0.6), inset 0 2px 10px rgba(0,0,0,0.3);
  text-shadow: 0 0 5px rgba(255,255,255,0.5);
}

.control-btn:disabled {
  background: #222;
  color: #444;
  border-color: #111;
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}

/* Launch Button Specifics */
.control-btn.launch-btn {
  width: 100px;
  height: 100px;
  border-radius: 50%;
  background: linear-gradient(145deg, #d32f2f, #b71c1c);
  border: 4px solid #7f0000;
  border-bottom-width: 8px;
  color: white;
  z-index: 5;
  box-shadow: 0 6px 0 #5c0000, 0 10px 20px rgba(0,0,0,0.6);
  font-size: 16px;
}

.control-btn.launch-btn:hover {
  background: linear-gradient(145deg, #f44336, #d32f2f);
  box-shadow: 0 8px 0 #5c0000, 0 12px 25px rgba(244, 67, 54, 0.4);
}

.control-btn.launch-btn.pressed {
  background: radial-gradient(circle, #ff5252 0%, #d32f2f 100%);
  box-shadow: 0 0 0 #5c0000, 0 0 15px #f44336;
  border-bottom-width: 4px;
}

.key-hint {
  font-size: 10px;
  color: rgba(255,255,255,0.5);
  margin-top: 4px;
  font-weight: normal;
  background: rgba(0,0,0,0.3);
  padding: 2px 6px;
  border-radius: 4px;
}

.control-btn.pressed .key-hint {
  color: rgba(255,255,255,0.9);
}

.toggle-row {
  display: flex;
  gap: 15px;
  margin-top: 20px;
  width: 100%;
  padding: 0 20px;
  justify-content: center;
}

.toggle-btn {
  flex: 1;
  max-width: 200px;
  padding: 12px 20px;
  background-color: #1a1a1a;
  color: #888;
  border: 1px solid #333;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  transition: all 0.2s;
  text-transform: uppercase;
}

.toggle-btn:hover {
  background-color: #252525;
  color: #ddd;
  border-color: #444;
}

.toggle-btn.active {
  background: rgba(76, 175, 80, 0.1);
  border-color: #4caf50;
  color: #4caf50;
  box-shadow: 0 0 10px rgba(76, 175, 80, 0.1);
}

.toggle-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: #444;
  box-shadow: inset 0 1px 2px rgba(0,0,0,0.5);
}

.toggle-btn.active .toggle-dot {
  background-color: #4caf50;
  box-shadow: 0 0 6px #4caf50;
}

.toggle-btn.test-btn {
  background: rgba(255, 152, 0, 0.1);
  border-color: #ff9800;
  color: #ff9800;
}

.toggle-btn.test-btn:hover {
  background: rgba(255, 152, 0, 0.2);
  box-shadow: 0 0 10px rgba(255, 152, 0, 0.2);
}

@media (max-width: 900px) {
  .desktop-only {
    display: none !important;
  }
}
</style>
