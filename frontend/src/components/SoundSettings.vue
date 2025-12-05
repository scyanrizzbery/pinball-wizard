<template>
  <div class="sound-settings">
    <div class="header">
      <h3>Sound Settings</h3>
      <button @click="$emit('close')" class="close-btn">×</button>
    </div>
    
    <!-- Sound Section -->
    <div class="section">
      <h4 class="section-title">Sound</h4>

      <div class="control-group">
        <label>Volume: {{ Math.round(volume * 100) }}%</label>
        <input
          type="range"
          min="0"
          max="1"
          step="0.01"
          v-model.number="volume"
          @input="updateVolume"
        >
      </div>

      <div class="control-group checkbox-group">
        <label for="mute-toggle">Mute</label>
        <input
          id="mute-toggle"
          type="checkbox"
          v-model="muted"
          @change="updateMute"
        >
      </div>

      <div class="actions">
        <button @click="testSound" class="test-btn">Test Sound</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import SoundManager from '../utils/SoundManager'

const volume = ref(0.5)
const muted = ref(false)

onMounted(() => {
    // Initialize from SoundManager defaults
    volume.value = SoundManager.volume
    muted.value = SoundManager.muted
})

const updateVolume = () => {
    SoundManager.setVolume(volume.value)
}

const updateMute = () => {
    SoundManager.setMute(muted.value)
}

const testSound = () => {
    SoundManager.resume()
    SoundManager.playBumper()
}
</script>

<style scoped>
.sound-settings {
  background: rgba(30, 30, 30, 0.95);
  border: 1px solid #555;
  border-radius: 8px;
  padding: 15px;
  width: 250px;
  color: #eee;
  box-shadow: 0 4px 12px rgba(0,0,0,0.5);
  pointer-events: auto;
  z-index: 200;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
  border-bottom: 1px solid #444;
  padding-bottom: 5px;
}

.header h3 {
  margin: 0;
  font-size: 16px;
  color: #fff;
}

.close-btn {
  background: none;
  border: none;
  color: #aaa;
  font-size: 20px;
  cursor: pointer;
  padding: 0 5px;
}

.close-btn:hover {
  color: #fff;
}

.section {
  margin-bottom: 15px;
  padding-bottom: 15px;
  border-bottom: 1px solid #333;
}

.section:last-child {
  border-bottom: none;
  margin-bottom: 0;
  padding-bottom: 0;
}

.section-title {
  margin: 0 0 10px 0;
  font-size: 14px;
  color: #999;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  font-weight: 500;
}

.control-group {
  margin-bottom: 15px;
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.control-group:last-child {
  margin-bottom: 0;
}

.checkbox-group {
  flex-direction: row;
  align-items: center;
  gap: 10px;
}

input[type="range"] {
  width: 100%;
  cursor: pointer;
}

.actions {
  margin-top: 10px;
}

.test-btn {
  width: 100%;
  padding: 8px;
  background: #4caf50;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
}

.test-btn:hover {
  background: #45a049;
}
</style>
