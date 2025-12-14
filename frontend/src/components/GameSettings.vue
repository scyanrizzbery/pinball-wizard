<template>
  <div class="sound-settings">
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

      <div class="control-group checkbox-group mute-control">
          <input
              id="mute-toggle"
              type="checkbox"
              v-model="muted"
              @change="updateMute"
          >
          <label for="mute-toggle">Mute</label>
      </div>

    </div>

    <!-- Visuals Section -->
    <div class="section">
      <h4 class="section-title">Visuals</h4>

      <div class="control-group">
        <label>Graphics Preset</label>
        <select v-model="selectedPreset" @change="applyPreset" style="width: 100%; padding: 5px; background: #333; color: white; border: 1px solid #555; border-radius: 4px;">
          <option value="low">Low (Fastest)</option>
          <option value="medium">Medium</option>
          <option value="high">High</option>
          <option value="ultra">Ultra (Max FX)</option>
        </select>
      </div>

      <div class="control-group">
        <label>Smoke Intensity: {{ Math.round(localSmokeIntensity * 100) }}%</label>
        <input
          type="range"
          min="0"
          max="2"
          step="0.1"
          v-model.number="localSmokeIntensity"
          @input="updateSmokeIntensity"
        >
      </div>
    </div>

    <div class="header-controls">
        <button class="icon-btn" @click="$emit('toggle-high-scores')" title="View High Scores">
            🏆 High Scores
        </button>
    </div>

  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import SoundManager from '../utils/SoundManager'

const props = defineProps<{
  smokeIntensity: number
}>()

const $emit = defineEmits<{
  (e: 'close'): void
  (e: 'update-smoke-intensity', value: number): void
  (e: 'toggle-high-scores'): void
}>()

const volume = ref(0.5)
const muted = ref(false)
const localSmokeIntensity = ref(0.5)
const selectedPreset = ref('medium')

// Explicit type for presets values based on usage
interface PresetSettings {
    smoke: number
}

const presets: Record<string, PresetSettings> = {
  low: { smoke: 0.0 },
  medium: { smoke: 0.5 },
  high: { smoke: 1.0 },
  ultra: { smoke: 2.0 }
}

onMounted(() => {
    // Initialize from SoundManager defaults
    volume.value = SoundManager.volume
    muted.value = SoundManager.muted
    // Initialize visual settings
    localSmokeIntensity.value = props.smokeIntensity
})

watch(() => props.smokeIntensity, (newVal) => {
  localSmokeIntensity.value = newVal
})

const updateVolume = () => {
    SoundManager.setVolume(volume.value)
}

const updateMute = () => {
    SoundManager.setMute(muted.value)
}

const updateSmokeIntensity = () => {
    $emit('update-smoke-intensity', localSmokeIntensity.value)
    // If manual adjustment doesn't match a preset, strictly speaking we are "custom", but for now keep last preset or ignore.
}

const applyPreset = () => {
  const settings = presets[selectedPreset.value]
  if (settings) {
    localSmokeIntensity.value = settings.smoke
    updateSmokeIntensity()
  }
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
  width: 185px;
  color: #eee;
  box-shadow: 0 4px 12px rgba(0,0,0,0.5);
  pointer-events: auto;
  z-index: 1100;
  position: relative;
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

.mute-control {
    justify-content: flex-end;
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

.header-controls {
}

.icon-btn {
    background: none;
    border: none;
    cursor: pointer;
    transition: transform 0.2s;
}

.icon-btn:hover {
    transform: scale(1.1);
}

</style>
