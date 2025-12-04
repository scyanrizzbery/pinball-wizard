<template>
  <div id="app-container">
    <Header :connected="connected">
      <!-- Stats removed from header -->
    </Header>

    <div id="main-layout">
      <div id="game-area">


        <div class="game-view-wrapper" id="playfield-container">
          <div class="scoreboard-overlay">
            <ScoreBoard 
              :score="stats.score" 
              :highScore="stats.high_score" 
              :balls="stats.balls"
              :comboCount="stats.combo_count || 0"
              :scoreMultiplier="stats.score_multiplier || 1.0"
              :comboActive="stats.combo_active || false"
            />
          </div>

          <VideoFeed v-if="viewMode === 'video'" :videoSrc="videoSrc" :isTilted="isTilted" :stats="stats" :nudgeEvent="nudgeEvent" :physics="physics" :socket="sockets.game" :configSocket="sockets.config" :hasUnsavedChanges="hasUnsavedChanges"
            @update-zone="handleZoneUpdate" @update-rail="handleRailUpdate" @update-bumper="handleBumperUpdate" @save-layout="saveChanges" @reset-zones="handleResetZones" @toggle-view="toggleViewMode" />
          
          <Pinball3D 
          v-if="viewMode === '3d'"
          :socket="sockets.game"
          :configSocket="sockets.config"
          :config="layoutConfig"
          :nudgeEvent="nudgeEvent"
          :stats="stats"
          :cameraMode="viewMode === '3d' ? 'perspective' : 'top-down'"
          @toggle-view="toggleViewMode"
        />
          <ComboDisplay 
            :comboCount="stats.combo_count || 0"
            :comboTimer="stats.combo_timer || 0"
            :comboActive="stats.combo_active || false"
            :maxTimer="physics.combo_window || 3.0"
            :scoreMultiplier="stats.score_multiplier || 1.0"
          />
        </div>

        <Controls :buttonStates="buttonStates" :toggles="toggles" @input="handleInput" @toggle-ai="toggleAI"
          @toggle-auto-start="toggleAutoStart" :disabled="stats.is_training" />



      </div>

      <GameHistory :gameHistory="stats.game_history" :gamesPlayed="stats.games_played" />

      <Settings :physics="physics" :stats="stats" :cameraPresets="cameraPresets" :models="models" :layouts="layouts"
        v-model:selectedModel="selectedModel" v-model:selectedLayout="selectedLayout"
        v-model:selectedPreset="selectedPreset" :selectedDifficulty="selectedDifficulty"
        @update-physics="updatePhysics" @apply-preset="applyPreset"
        @save-preset="savePreset" @delete-preset="deletePreset" @load-model="loadModel"
        @change-layout="changeLayout" @start-training="startTraining" @stop-training="stopTraining"
        @update-difficulty="updateDifficulty" />

      <Logs :logs="logs" />
    </div>

    <div id="input-area">
      <div class="input-group" style="flex: 2;">
        <button class="input-btn flipper-btn" :class="{ pressed: buttonStates.left }" @mousedown="handleInput('KeyZ', 'down')"
          @mouseup="handleInput('KeyZ', 'up')" @touchstart.prevent="handleInput('KeyZ', 'down')"
          @touchend.prevent="handleInput('KeyZ', 'up')" :disabled="stats.is_training">Left</button>
        <button class="input-btn" :class="{ pressed: buttonStates.nudgeLeft }"
          style="min-height: 34px; font-size: 14px;" @mousedown="handleInput('ShiftLeft', 'down')"
          @mouseup="handleInput('ShiftLeft', 'up')" @touchstart.prevent="handleInput('ShiftLeft', 'down')"
          @touchend.prevent="handleInput('ShiftLeft', 'up')" :disabled="stats.is_training">N Left</button>
      </div>

      <div class="input-group" style="flex: 1; align-items: center;">
        <button class="input-btn launch" :class="{ pressed: buttonStates.launch }"
          @mousedown="handleInput('Space', 'down')" @mouseup="handleInput('Space', 'up')"
          @touchstart.prevent="handleInput('Space', 'down')"
          @touchend.prevent="handleInput('Space', 'up')" :disabled="stats.is_training">Launch</button>
      </div>

      <div class="input-group" style="flex: 2;">
        <button class="input-btn flipper-btn" :class="{ pressed: buttonStates.right }" @mousedown="handleInput('Slash', 'down')"
          @mouseup="handleInput('Slash', 'up')" @touchstart.prevent="handleInput('Slash', 'down')"
          @touchend.prevent="handleInput('Slash', 'up')" :disabled="stats.is_training">Right</button>
        <button class="input-btn" :class="{ pressed: buttonStates.nudgeRight }"
          style="min-height: 34px; font-size: 14px;" @mousedown="handleInput('ShiftRight', 'down')"
          @mouseup="handleInput('ShiftRight', 'up')" @touchstart.prevent="handleInput('ShiftRight', 'down')"
          @touchend.prevent="handleInput('ShiftRight', 'up')" :disabled="stats.is_training">N Right</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, onMounted, onUnmounted } from 'vue'
import SoundManager from './utils/SoundManager'


import Header from './components/Header.vue'
import ScoreBoard from './components/ScoreBoard.vue'
import ComboDisplay from './components/ComboDisplay.vue'
import VideoFeed from './components/VideoFeed.vue'
import Pinball3D from './components/Pinball3D.vue'
import Controls from './components/Controls.vue'
import Settings from './components/Settings.vue'
import GameHistory from './components/GameHistory.vue'
import io from 'socket.io-client'
import Logs from './components/Logs.vue'

const sockets = {
  game: io('/game'),
  control: io('/control'),
  config: io('/config'),
  training: io('/training')
}
const connected = ref(false)
const videoSrc = ref('')
const logs = ref([])
const activeKeys = reactive(new Set())
const models = ref([])
const selectedModel = ref('')
const debounceTimers = {}
const nudgeEvent = ref(null)
const viewMode = ref('3d')
const layoutConfig = ref(null)
const isLoadingLayout = ref(false)
const hasUnsavedChanges = ref(false)

// Track button pressed states for visual feedback
const buttonStates = reactive({
  left: false,
  right: false,
  launch: false,
  nudgeLeft: false,
  nudgeRight: false
})

const addLog = (message) => {
  const timestamp = new Date().toLocaleTimeString()
  logs.value.push(`[${timestamp}] ${message}`)
  if (logs.value.length > 50) logs.value.shift()
}



const stats = reactive({
  score: 0,
  high_score: 0,
  balls: 0,
  games_played: 0,
  game_history: [],
  timesteps: 0,
  mean_reward: 0,
  is_training: false,
  nudge: null,
  tilt_value: 0,
  is_tilted: false,
  training_progress: 0,
  current_step: 0,
  total_steps: 0,
  eta_seconds: 0,
  is_simulation: false,
  combo_count: 0,
  combo_timer: 0.0,
  score_multiplier: 1.0,
  combo_active: true,
})

const isSimulation = computed(() => stats.is_simulation || false)

const toggleViewMode = () => {
  viewMode.value = viewMode.value === '3d' ? 'video' : '3d'
}

const isTilted = computed(() => stats.is_tilted || false)

const physics = reactive({
  gravity: 1200.0,
  friction: 0.999,
  restitution: 0.5,
  flipper_speed: 1500.0,
  flipper_resting_angle: -30,
  flipper_stroke_angle: 50,
  flipper_length: 0.2,
  flipper_width: 0.025,
  flipper_tip_width: 0.025,
  flipper_elasticity: 0.5,
  ball_mass: 1.0,
  tilt_threshold: 8.0,
  nudge_cost: 5.0,
  tilt_decay: 0.03,
  camera_pitch: 45,
  camera_x: 0.5,
  camera_y: 1.5,
  camera_z: 1.5,
  camera_zoom: 1.0,
  combo_window: 3.0,
  multiplier_max: 5.0,
  base_combo_bonus: 50,
  combo_multiplier_enabled: true,
  combo_multiplier_enabled: true,
  zones: [],
  rails: [],
  bumpers: [],
  rail_x_offset: 0,
  rail_y_offset: 0
})

const toggles = reactive({
  ai: true,
  autoStart: true
})

const cameraPresets = ref({})
const selectedPreset = ref('')

const applyPreset = () => {
  const preset = cameraPresets.value[selectedPreset.value]
  if (preset) {
    if (preset.camera_pitch !== undefined) physics.camera_pitch = preset.camera_pitch
    if (preset.camera_x !== undefined) physics.camera_x = preset.camera_x
    if (preset.camera_y !== undefined) physics.camera_y = preset.camera_y
    if (preset.camera_z !== undefined) physics.camera_z = preset.camera_z
    if (preset.camera_zoom !== undefined) physics.camera_zoom = preset.camera_zoom

    sockets.config.emit('apply_preset', { name: selectedPreset.value })

    sockets.config.emit('update_physics_v2', {
      camera_pitch: physics.camera_pitch,
      camera_x: physics.camera_x,
      camera_y: physics.camera_y,
      camera_z: physics.camera_z,
      camera_zoom: physics.camera_zoom
    })
  }
}

const applyPresetFromSettings = (name) => {
  selectedPreset.value = name
  applyPreset()
}

const savePreset = (name) => {
  sockets.config.emit('save_preset', { name: name })
}

const deletePreset = (name) => {
  sockets.config.emit('delete_preset', { name: name })
  if (selectedPreset.value === name) {
    selectedPreset.value = ''
  }
}

const layouts = ref([])
const selectedLayout = ref('default')
const selectedDifficulty = ref('medium')
const gameHistory = ref([])

const updateDifficulty = (difficulty) => {
  selectedDifficulty.value = difficulty
  sockets.training.emit('update_difficulty', { difficulty })
  addLog(`Set difficulty to: ${difficulty}`)
}

const handleInput = (key, type) => {
  if (type === 'down') {
    if (!activeKeys.has(key)) {
      activeKeys.add(key)
      sockets.control.emit('input_event', { key, type: 'down' })

      if (key === 'KeyZ') {
          buttonStates.left = true
          SoundManager.playFlipperUp()
      }
      else if (key === 'Slash') {
          buttonStates.right = true
          SoundManager.playFlipperUp()
      }
      else if (key === 'Space') {
          buttonStates.launch = true
          SoundManager.playLaunch()
      }
      else if (key === 'ShiftLeft') buttonStates.nudgeLeft = true
      else if (key === 'ShiftRight') buttonStates.nudgeRight = true
    }
  } else {
    if (activeKeys.has(key)) {
      activeKeys.delete(key)
      sockets.control.emit('input_event', { key, type: 'up' })

      if (key === 'KeyZ') {
          buttonStates.left = false
          SoundManager.playFlipperDown()
      }
      else if (key === 'Slash') {
          buttonStates.right = false
          SoundManager.playFlipperDown()
      }
      else if (key === 'Space') buttonStates.launch = false
      else if (key === 'ShiftLeft') buttonStates.nudgeLeft = false
      else if (key === 'ShiftRight') buttonStates.nudgeRight = false
    }
  }
}

// Watch all physics properties to trigger updates automatically
// This avoids race conditions between v-model and @input events
Object.keys(physics).forEach(key => {
  watch(() => physics[key], (newVal) => {
    updatePhysics(key, newVal)
  })
})

const updatePhysics = (param, value) => {
  // If value is undefined (e.g. called from @input without value), use current physics value
  const val = value !== undefined ? value : physics[param]
  
  physics[param] = val // Update local state (redundant if v-model used, but safe)
  
  // Also update layoutConfig so Pinball3D sees the change immediately
  if (layoutConfig.value) {
    layoutConfig.value[param] = val
  }

  if (debounceTimers[param]) clearTimeout(debounceTimers[param])
  debounceTimers[param] = setTimeout(() => {
    sockets.config.emit('update_physics_v2', { [param]: val })
    // sockets.config.emit('save_physics') // Redundant, update_physics_v2 saves automatically
    delete debounceTimers[param]
  }, 300)
}

const handleZoneUpdate = (newZones) => {
  physics.zones = newZones
  if (layoutConfig.value) layoutConfig.value.zones = newZones
  hasUnsavedChanges.value = true
}

const handleRailUpdate = (newRails) => {
  physics.rails = newRails
  if (layoutConfig.value) layoutConfig.value.rails = newRails
  hasUnsavedChanges.value = true
}

const handleBumperUpdate = (newBumpers) => {
  physics.bumpers = newBumpers
  if (layoutConfig.value) layoutConfig.value.bumpers = newBumpers
  hasUnsavedChanges.value = true
}

const saveChanges = () => {
  if (!layoutConfig.value) return
  
  sockets.config.emit('update_zones', physics.zones)
  sockets.config.emit('update_rails', physics.rails)
  sockets.config.emit('update_bumpers', physics.bumpers)
  
  hasUnsavedChanges.value = false
  addLog('Layout saved manually')
}

const handleResetZones = () => {
  sockets.config.emit('reset_zones')
}

const resetConfig = () => {
  sockets.config.emit('reset_physics')
}

const loadModel = () => {
  if (selectedModel.value) {
    sockets.training.emit('load_model', { model: selectedModel.value })
  }
}

const toggleAI = () => {
  sockets.training.emit('toggle_ai', { enabled: !toggles.ai })
}

const toggleAutoStart = () => {
  sockets.training.emit('toggle_auto_start', { enabled: !toggles.autoStart })
}



const changeLayout = () => {
  isLoadingLayout.value = true
  addLog(`Loading layout: ${selectedLayout.value}`)
  sockets.config.emit('load_layout_by_name', { name: selectedLayout.value })
}

const startTraining = (config) => {
  try {
    addLog(`Starting training: ${config.modelName}`)
    if (!sockets.training.connected) {
      addLog("Error: Socket not connected")
      return
    }
    sockets.training.emit('start_training', {
      model_name: config.modelName,
      total_timesteps: config.timesteps,
      learning_rate: config.learningRate,
      layout: config.layout,
      physics: config.physics
    })
  } catch (e) {
    addLog(`Error starting training: ${e.message}`)
  }
}

const stopTraining = () => {
  try {
    addLog('Stopping training...')
    sockets.training.emit('stop_training')
  } catch (e) {
    addLog(`Error stopping training: ${e.message}`)
  }
}

const handleKeydown = (e) => {
  if (e.repeat) return
  if (e.code === 'KeyZ' || e.code === 'Slash' || e.code === 'Space' || e.code === 'ShiftLeft' ||
    e.code === 'ShiftRight') {
    e.preventDefault()
    handleInput(e.code, 'down')
  }
}

const handleKeyup = (e) => {
  if (e.code === 'KeyZ' || e.code === 'Slash' || e.code === 'Space' || e.code === 'ShiftLeft' ||
    e.code === 'ShiftRight') {
    handleInput(e.code, 'up')
  }
}

onMounted(() => {
  sockets.config.on('physics_config_loaded', (config) => {
    console.log('Physics Config Loaded:', config)
    if (config) {
      window.__PHYSICS__ = config // Expose for E2E testing
      layoutConfig.value = config // Store full config for 3D view
      
      Object.keys(config).forEach(key => {
        if (key in physics) {
          physics[key] = config[key]
        }
      })
      if (config.camera_presets) {
        cameraPresets.value = config.camera_presets
        // Auto-select Default preset if none selected
        if (!selectedPreset.value && 'Default' in config.camera_presets) {
          selectedPreset.value = 'Default'
        }
      }
      addLog('Physics config loaded')
      if (config.last_model) {
        selectedModel.value = config.last_model
        addLog(`Restored last model selection: ${config.last_model}`)
      }
      if (config.last_preset) {
        selectedPreset.value = config.last_preset
        addLog(`Restored last camera preset: ${config.last_preset}`)
      }
      if (config.current_layout_id && !isLoadingLayout.value) {
        selectedLayout.value = config.current_layout_id
        addLog(`Restored last layout: ${config.current_layout_id}`)
      }
    }
  })

  sockets.config.on('presets_updated', (presets) => {
    cameraPresets.value = presets
    if (!selectedPreset.value && 'Default' in presets) {
      selectedPreset.value = 'Default'
    }
  })

  sockets.game.on('connect', () => {
    connected.value = true
    addLog('Connected to game server')
  })

  sockets.config.on('connect', () => {
    addLog('Connected to config server')
    sockets.config.emit('load_physics')
  })

  sockets.game.on('disconnect', () => {
    connected.value = false
    addLog('Disconnected from server')
  })

  sockets.game.on('video_frame', (data) => {
    videoSrc.value = 'data:image/jpeg;base64,' + data.image
  })

  sockets.game.on('stats_update', (data) => {
    Object.assign(stats, data)
    if (data.nudge) {
      nudgeEvent.value = data.nudge
    }
  })
  
  sockets.config.on('layout_loaded', (data) => {
    console.log('Layout loaded:', data)
    if (data.status === 'success') {
      isLoadingLayout.value = false
      // Request the new physics config to update 3D view
      sockets.config.emit('load_physics')
    } else {
      isLoadingLayout.value = false
    }
  })

  sockets.training.on('ai_status', (data) => {
    toggles.ai = data.enabled
    addLog(`AI Enabled: ${data.enabled}`)
  })

  sockets.training.on('model_selected', (data) => {
    addLog(`Auto-selected model: ${data.model}`)
    selectedModel.value = data.model
    // Refresh model list to ensure the new model is in the dropdown
    sockets.training.emit('get_models')
  })

  sockets.training.on('auto_start_status', (data) => {
    toggles.autoStart = data.enabled
    addLog(`Auto-Start: ${data.enabled}`)
  })

  sockets.training.on('difficulty_status', (data) => {
    selectedDifficulty.value = data.difficulty
    addLog(`Difficulty updated: ${data.difficulty}`)
  })

  sockets.config.on('layouts_list', (data) => {
    layouts.value = data
    // Check if selectedLayout exists in list
    const exists = layouts.value.some(l => l.id === selectedLayout.value)
    if (!exists) {
        // Try 'default' (lowercase)
        const defaultExists = layouts.value.some(l => l.id === 'default')
        if (defaultExists) {
            selectedLayout.value = 'default'
        } else if (layouts.value.length > 0) {
            // Fallback to first
            selectedLayout.value = layouts.value[0].id
        }
    }
  })

  sockets.config.on('layout_loaded', (data) => {
    if (data.status === 'success') {
      addLog('Layout loaded successfully')
    } else {
      addLog(`Error loading layout: ${data.message}`)
    }
  })

  sockets.config.emit('get_layouts')
  sockets.training.emit('get_models')

  sockets.game.on('log_message', (data) => {
    addLog(data.message)
  })

  sockets.training.on('models_list', (data) => {
    const currentSelection = selectedModel.value
    models.value = data
    
    // Preserve selection if it exists in new list
    if (currentSelection) {
      const exists = data.some(m => m.filename === currentSelection)
      if (exists) {
        // Force reactivity by reassigning
        selectedModel.value = currentSelection
      } else if (data.length > 0) {
        selectedModel.value = data[0].filename
      }
    } else if (data.length > 0) {
      selectedModel.value = data[0].filename
    }
  })
  sockets.training.on('model_loaded', (data) => {
    if (data.status === 'success') {
      addLog(`Model loaded: ${data.model}`)
    } else {
      addLog(`Error loading model: ${data.message}`)
    }
  })



  // If already connected, trigger load
  if (sockets.config.connected) {
    connected.value = true
    addLog('Connected to server (existing)')
    sockets.config.emit('load_physics')
  }

  window.addEventListener('keydown', handleKeydown)
  window.addEventListener('keyup', handleKeyup)

  window.addEventListener('blur', () => {
    activeKeys.clear()
    sockets.control.emit('input_event', { key: 'KeyZ', type: 'up' })
    sockets.control.emit('input_event', { key: 'Slash', type: 'up' })
    sockets.control.emit('input_event', { key: 'Space', type: 'up' })
    sockets.control.emit('input_event', { key: 'ShiftLeft', type: 'up' })
    sockets.control.emit('input_event', { key: 'ShiftRight', type: 'up' })
  })

  // Expose stats for Cypress testing
  if (window.Cypress || import.meta.env.DEV) {
    window.__APP_STATS__ = stats
  }
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown)
  window.removeEventListener('keyup', handleKeyup)
  Object.values(sockets).forEach(s => s.disconnect())
})
</script>

<style>
body {
  font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
  background-color: #121212;
  color: #e0e0e0;
  text-align: center;
  margin: 0;
  padding: 10px;
  touch-action: manipulation;
}

#app-container {
  max-width: 1600px;
  margin: 0 auto;
  padding: 0 20px 180px;
}

#main-layout {
  display: grid;
  grid-template-columns: minmax(400px, 1fr) 240px minmax(320px, 1fr);
  grid-template-rows: auto auto minmax(0, 1fr);
  grid-template-areas:
    "game history settings"
    "logs logs logs";
  gap: 20px;
  margin: 20px 0;
  align-items: start;
}

#game-area {
  grid-area: game;
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 100%;
}

.controls-container {
  grid-area: controls;
  background: #1e1e1e;
  padding: 15px;
  border-radius: 8px;
  border: 1px solid #3d3d3d;
  width: 100%;
  box-sizing: border-box;
  margin-top: 10px;
}

.control-group {
  display: flex;
  gap: 10px;
  margin-bottom: 10px;
  flex-wrap: wrap;
}

/* Sticky Input Area */
#input-area {
  position: fixed;
  bottom: 0;
  left: 0;
  width: 100%;
  background: rgba(0, 0, 0, 0.1);
  border-top: 1px solid rgba(255, 255, 255, 0.1);
  z-index: 2000;
  display: none;
  justify-content: center;
  align-items: center;
  gap: 12px;
  backdrop-filter: blur(4px);
  box-shadow: none;
  padding: 12px;
  box-sizing: border-box;
}

.input-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.input-btn {
  padding: 16px 32px;
  background: rgba(255, 255, 255, 0.1);
  color: rgba(255, 255, 255, 0.8);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 10px;
  cursor: pointer;
  font-size: 16px;
  font-weight: bold;
  transition: all 0.15s ease;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  width: 100%;
  height: 100%;
  min-height: 80px;
  touch-action: manipulation;
  user-select: none;
  -webkit-user-select: none;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
  backdrop-filter: blur(4px);
}

.input-btn:active {
  background: rgba(255, 255, 255, 0.2);
  transform: translateY(2px);
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
}

.input-btn.pressed {
  background: rgba(76, 175, 80, 0.4) !important;
  border-color: rgba(76, 175, 80, 0.6) !important;
  color: #fff;
  box-shadow: 0 0 20px rgba(76, 175, 80, 0.4), 0 4px 8px rgba(0, 0, 0, 0.2) !important;
  transform: translateY(2px);
}

.input-btn.launch {
  width: 85px;
  height: 85px;
  border-radius: 50%;
  background: rgba(239, 83, 80, 0.3);
  font-size: 1em;
  border: 2px solid rgba(239, 83, 80, 0.5);
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto;
  box-shadow: 0 6px 12px rgba(0, 0, 0, 0.2);
}

.input-btn.launch:active {
  background: rgba(239, 83, 80, 0.5);
  transform: scale(0.95);
  box-shadow: 0 3px 6px rgba(0, 0, 0, 0.3);
}

.input-btn.launch.pressed {
  background: rgba(255, 87, 34, 0.5) !important;
  border-color: rgba(255, 87, 34, 0.7) !important;
  box-shadow: 0 0 24px rgba(255, 87, 34, 0.5), 0 4px 8px rgba(0, 0, 0, 0.2) !important;
  transform: scale(0.95);
}

.switch-view-btn {
  position: absolute;
  bottom: 10px;
  right: 10px;
  background: rgba(0, 0, 0, 0.6);
  color: #fff;
  border: 1px solid #555;
  padding: 5px 10px;
  border-radius: 4px;
  cursor: pointer;
  z-index: 30;
  font-size: 12px;
  user-select: none;
  -webkit-user-select: none;
}

.switch-view-btn:hover {
  background: rgba(0, 0, 0, 0.8);
}

/* Responsive Design */
@media (max-width: 1200px) {
  #main-layout {
    grid-template-columns: 1fr 350px;
    grid-template-areas:
      "game settings"
      "controls settings"
      "history history"
      "logs logs";
  }
}

@media (max-width: 900px) {
  #main-layout {
    grid-template-columns: 1fr;
    grid-template-areas:
      "game"
      "controls"
      "history"
      "settings"
      "logs";
  }

  #input-area {
    display: flex;
  }
}

@media (min-width: 600px) and (max-width: 900px) {
  #main-layout {
    grid-template-columns: 1fr minmax(auto, 400px) 1fr;
    grid-template-areas:
      "history game settings"
      "logs logs logs";
  }
  
  /* Hide controls in this specific layout if desired, or let them flow? 
     User didn't specify controls, but "Game in middle of History and Settings" implies 3 columns.
     The "Controls" component is usually part of the grid. 
     If we don't define "controls" in grid-areas, it might auto-place or disappear if display:none isn't set.
     However, the Controls component is inside #game-area in the HTML structure!
     Wait, let's check the HTML structure.
  */
}

@media (max-width: 690px) {
  .controls-container {
    margin-top: 0;
    padding: 8px; /* Reduced padding further */
  }

  #app-container {
    padding: 0 0 160px; /* Removed side padding */
    margin-bottom: 0;
  }

  #main-layout {
    gap: 5px; /* Reduced gap */
    margin: 5px 0; /* Reduced margin */
  }
  
  body {
    padding: 0; /* Removed body padding */
  }
}

.game-view-wrapper {
  position: relative;
  width: 100%;
  max-width: 450px; /* Match standard table width */
  aspect-ratio: 450 / 800; /* Maintain aspect ratio */
  min-height: 300px; /* Prevent total collapse */
  display: flex;
  justify-content: center;
  margin: 0 auto; /* Center it */
}

.scoreboard-overlay {
  position: absolute;
  top: 10px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 50;
  width: 100%;
  pointer-events: none;
  display: flex;
  justify-content: center;
}

@media (max-width: 600px) {
  /* Header visibility handled in Header.vue now */

  #input-area {
    padding: 5px;
    gap: 5px;
  }

  .input-btn {
    min-height: 60px;
    font-size: 14px;
    padding: 10px;
  }

  .flipper-btn {
    min-height: 120px;
  }

  .input-btn.launch {
    width: 60px;
    height: 60px;
    font-size: 0.8em;
  }
}




.save-btn {
  background: #ff9800;
  color: white;
  font-weight: bold;
  animation: pulse-save 2s infinite;
}

@keyframes pulse-save {
  0% { box-shadow: 0 0 0 0 rgba(255, 152, 0, 0.7); }
  70% { box-shadow: 0 0 0 10px rgba(255, 152, 0, 0); }
  100% { box-shadow: 0 0 0 0 rgba(255, 152, 0, 0); }
}
</style>
