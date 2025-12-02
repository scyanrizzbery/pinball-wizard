<template>
  <div id="app-container">
    <Header :connected="connected">
      <!-- Stats removed from header -->
    </Header>

    <div id="main-layout">
      <div id="game-area">


        <div class="game-view-wrapper">
          <div class="scoreboard-overlay">
            <ScoreBoard 
              :score="stats.score" 
              :highScore="stats.high_score" 
              :balls="stats.balls" 
            />
          </div>

          <VideoFeed v-if="viewMode === 'video' && !isSimulation" :videoSrc="videoSrc" :isTilted="isTilted" :stats="stats" :nudgeEvent="nudgeEvent" :physics="physics" :socket="socket"
            @update-zone="handleZoneUpdate" @reset-zones="handleResetZones" @toggle-view="toggleViewMode" />
          
          <Pinball3D 
          v-if="viewMode === '3d' || (viewMode === 'video' && isSimulation)"
          :width="400" 
          :height="711" 
          :socket="socket"
          :config="layoutConfig"
          :nudgeEvent="nudgeEvent"
          :cameraMode="viewMode === '3d' ? 'perspective' : 'top-down'"
          @toggle-view="toggleViewMode"
        />
        </div>

        <Controls :buttonStates="buttonStates" :toggles="toggles" @input="handleInput" @toggle-ai="toggleAI"
          @toggle-auto-start="toggleAutoStart" />


      </div>

      <GameHistory :gameHistory="stats.game_history" :gamesPlayed="stats.games_played" />

      <Settings :physics="physics" :stats="stats" :cameraPresets="cameraPresets" :models="models" :layouts="layouts"
        v-model:selectedModel="selectedModel" v-model:selectedLayout="selectedLayout"
        v-model:selectedPreset="selectedPreset" @update-physics="updatePhysics" @apply-preset="applyPreset"
        @save-preset="savePreset" @delete-preset="deletePreset" @load-model="loadModel"
        @change-layout="changeLayout" @start-training="startTraining" @stop-training="stopTraining" />

      <Logs :logs="logs" />
    </div>

    <div id="input-area">
      <div class="input-group" style="flex: 2;">
        <button class="input-btn" :class="{ pressed: buttonStates.left }" @mousedown="handleInput('KeyZ', 'down')"
          @mouseup="handleInput('KeyZ', 'up')" @touchstart.prevent="handleInput('KeyZ', 'down')"
          @touchend.prevent="handleInput('KeyZ', 'up')">Left</button>
        <button class="input-btn" :class="{ pressed: buttonStates.nudgeLeft }"
          style="min-height: 34px; font-size: 14px;" @mousedown="handleInput('ShiftLeft', 'down')"
          @mouseup="handleInput('ShiftLeft', 'up')" @touchstart.prevent="handleInput('ShiftLeft', 'down')"
          @touchend.prevent="handleInput('ShiftLeft', 'up')">N Left</button>
      </div>

      <div class="input-group" style="flex: 1; align-items: center;">
        <button class="input-btn launch" :class="{ pressed: buttonStates.launch }"
          @mousedown="handleInput('Space', 'down')" @mouseup="handleInput('Space', 'up')"
          @touchstart.prevent="handleInput('Space', 'down')"
          @touchend.prevent="handleInput('Space', 'up')">Launch</button>
      </div>

      <div class="input-group" style="flex: 2;">
        <button class="input-btn" :class="{ pressed: buttonStates.right }" @mousedown="handleInput('Slash', 'down')"
          @mouseup="handleInput('Slash', 'up')" @touchstart.prevent="handleInput('Slash', 'down')"
          @touchend.prevent="handleInput('Slash', 'up')">Right</button>
        <button class="input-btn" :class="{ pressed: buttonStates.nudgeRight }"
          style="min-height: 34px; font-size: 14px;" @mousedown="handleInput('ShiftRight', 'down')"
          @mouseup="handleInput('ShiftRight', 'up')" @touchstart.prevent="handleInput('ShiftRight', 'down')"
          @touchend.prevent="handleInput('ShiftRight', 'up')">N Right</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import io from 'socket.io-client'
import Header from './components/Header.vue'
import ScoreBoard from './components/ScoreBoard.vue'
import VideoFeed from './components/VideoFeed.vue'
import Pinball3D from './components/Pinball3D.vue'
import Controls from './components/Controls.vue'
import Settings from './components/Settings.vue'
import GameHistory from './components/GameHistory.vue'
import Logs from './components/Logs.vue'

const socket = io()
const connected = ref(false)
const videoSrc = ref('')
const logs = ref([])
const activeKeys = reactive(new Set())
const models = ref([])
const selectedModel = ref('')
const debounceTimers = {}
const nudgeEvent = ref(null)
const viewMode = ref('video')
const layoutConfig = ref(null)

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
  is_simulation: false
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
  tilt_threshold: 8.0,
  nudge_cost: 5.0,
  tilt_decay: 0.03,
  camera_pitch: 45,
  camera_x: 0.5,
  camera_y: 1.5,
  camera_z: 1.5,
  camera_zoom: 1.0,
  zones: []
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

    socket.emit('update_physics_v2', {
      camera_pitch: physics.camera_pitch,
      camera_x: physics.camera_x,
      camera_y: physics.camera_y,
      camera_z: physics.camera_z,
      camera_zoom: physics.camera_zoom
    })

    socket.emit('apply_preset', { name: selectedPreset.value })
  }
}

const applyPresetFromSettings = (name) => {
  selectedPreset.value = name
  applyPreset()
}

const savePreset = (name) => {
  socket.emit('save_preset', { name: name })
}

const deletePreset = (name) => {
  socket.emit('delete_preset', { name: name })
  if (selectedPreset.value === name) {
    selectedPreset.value = ''
  }
}

const layouts = ref([])
const selectedLayout = ref('default')
const gameHistory = ref([])

const handleInput = (key, type) => {
  if (type === 'down') {
    if (!activeKeys.has(key)) {
      activeKeys.add(key)
      socket.emit('input_event', { key, type: 'down' })

      if (key === 'KeyZ') buttonStates.left = true
      else if (key === 'Slash') buttonStates.right = true
      else if (key === 'Space') buttonStates.launch = true
      else if (key === 'ShiftLeft') buttonStates.nudgeLeft = true
      else if (key === 'ShiftRight') buttonStates.nudgeRight = true
    }
  } else {
    if (activeKeys.has(key)) {
      activeKeys.delete(key)
      socket.emit('input_event', { key, type: 'up' })

      if (key === 'KeyZ') buttonStates.left = false
      else if (key === 'Slash') buttonStates.right = false
      else if (key === 'Space') buttonStates.launch = false
      else if (key === 'ShiftLeft') buttonStates.nudgeLeft = false
      else if (key === 'ShiftRight') buttonStates.nudgeRight = false
    }
  }
}

const updatePhysics = (param, value) => {
  physics[param] = value // Update local state immediately
  if (debounceTimers[param]) clearTimeout(debounceTimers[param])
  debounceTimers[param] = setTimeout(() => {
    socket.emit('update_physics_v2', { [param]: physics[param] })
    socket.emit('save_physics')
    delete debounceTimers[param]
  }, 300)
}

const handleZoneUpdate = (newZones) => {
  // Update local state immediately
  physics.zones = newZones

  // Debounce socket emission
  const timerKey = `zones_update`
  if (debounceTimers[timerKey]) clearTimeout(debounceTimers[timerKey])
  
  debounceTimers[timerKey] = setTimeout(() => {
    socket.emit('update_zones', newZones)
    socket.emit('save_physics')
    delete debounceTimers[timerKey]
    delete debounceTimers[timerKey]
  }, 100)
}

const handleResetZones = () => {
  socket.emit('reset_zones')
}

const resetConfig = () => {
  socket.emit('reset_physics')
}

const loadModel = () => {
  if (selectedModel.value) {
    socket.emit('load_model', { model: selectedModel.value })
  }
}

const toggleAI = () => {
  socket.emit('toggle_ai', { enabled: !toggles.ai })
}

const toggleAutoStart = () => {
  socket.emit('toggle_auto_start', { enabled: !toggles.autoStart })
}

const changeLayout = () => {
  addLog(`Loading layout: ${selectedLayout.value}`)
  socket.emit('load_layout_by_name', { name: selectedLayout.value })
}

const startTraining = (config) => {
  try {
    addLog(`Starting training: ${config.modelName}`)
    if (!socket.connected) {
      addLog("Error: Socket not connected")
      return
    }
    socket.emit('start_training', {
      model_name: config.modelName,
      total_timesteps: config.timesteps,
      learning_rate: config.learningRate
    })
  } catch (e) {
    addLog(`Error starting training: ${e.message}`)
  }
}

const stopTraining = () => {
  try {
    addLog('Stopping training...')
    socket.emit('stop_training')
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
  socket.on('physics_config_loaded', (config) => {
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
    }
  })

  socket.on('presets_updated', (presets) => {
    cameraPresets.value = presets
    if (!selectedPreset.value && 'Default' in presets) {
      selectedPreset.value = 'Default'
    }
  })

  socket.on('connect', () => {
    connected.value = true
    addLog('Connected to server')
    socket.emit('load_physics')
  })

  socket.on('disconnect', () => {
    connected.value = false
    addLog('Disconnected from server')
  })

  socket.on('video_frame', (data) => {
    videoSrc.value = 'data:image/jpeg;base64,' + data.image
  })

  socket.on('stats_update', (data) => {
    Object.assign(stats, data)
    if (data.game_history) {
      gameHistory.value = data.game_history
    }
    if (data.nudge) {
      nudgeEvent.value = data.nudge
    }
  })
  
  socket.on('layout_loaded', (data) => {
    console.log('Layout loaded:', data)
    if (data.status === 'success') {
      // Request the new physics config to update 3D view
      socket.emit('load_physics')
    }
  })

  socket.on('ai_status', (data) => {
    toggles.ai = data.enabled
    addLog(`AI Enabled: ${data.enabled}`)
  })

  socket.on('auto_start_status', (data) => {
    toggles.autoStart = data.enabled
    addLog(`Auto-Start: ${data.enabled}`)
  })

  socket.on('layouts_list', (data) => {
    layouts.value = data
    const exists = layouts.value.some(l => l.filename === selectedLayout.value)
    if (!exists && layouts.value.length > 0) {
      selectedLayout.value = 'default'
    }
  })

  socket.on('layout_loaded', (data) => {
    if (data.status === 'success') {
      addLog('Layout loaded successfully')
    } else {
      addLog(`Error loading layout: ${data.message}`)
    }
  })

  socket.emit('get_layouts')
  socket.emit('get_models')

  socket.on('log_message', (data) => {
    addLog(data.message)
  })

  socket.on('models_list', (data) => {
    models.value = data
    if (data.length > 0 && !selectedModel.value) {
      selectedModel.value = data[0].filename
    }
  })
  socket.on('model_loaded', (data) => {
    if (data.status === 'success') {
      addLog(`Model loaded: ${data.model}`)
    } else {
      addLog(`Error loading model: ${data.message}`)
    }
  })



  // If already connected, trigger load
  if (socket.connected) {
    connected.value = true
    addLog('Connected to server (existing)')
    socket.emit('load_physics')
  }

  window.addEventListener('keydown', handleKeydown)
  window.addEventListener('keyup', handleKeyup)

  window.addEventListener('blur', () => {
    activeKeys.clear()
    socket.emit('input_event', { key: 'KeyZ', type: 'up' })
    socket.emit('input_event', { key: 'Slash', type: 'up' })
    socket.emit('input_event', { key: 'Space', type: 'up' })
    socket.emit('input_event', { key: 'ShiftLeft', type: 'up' })
    socket.emit('input_event', { key: 'ShiftRight', type: 'up' })
  })
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown)
  window.removeEventListener('keyup', handleKeyup)
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
  background: rgba(20, 20, 20, 0.1);
  border-top: 1px solid #333;
  z-index: 2000;
  display: none;
  justify-content: center;
  align-items: center;
  gap: 10px;
  backdrop-filter: blur(10px);
  box-shadow: 0 -4px 20px rgba(0, 0, 0, 0.5);
  padding: 10px;
  box-sizing: border-box;
}

.input-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.input-btn {
  padding: 15px 30px;
  background-color: #333;
  color: #fff;
  border: 1px solid #444;
  border-radius: 8px;
  cursor: pointer;
  font-size: 16px;
  font-weight: bold;
  transition: all 0.1s;
  text-transform: uppercase;
  width: 100%;
  height: 100%;
  min-height: 80px;
  touch-action: manipulation;
  user-select: none;
  display: flex;
  align-items: center;
  justify-content: center;
}

.input-btn:active {
  background-color: #555;
  transform: translateY(2px);
}

.input-btn.pressed {
  background-color: #4caf50 !important;
  border-color: #45a049 !important;
  box-shadow: 0 0 15px rgba(76, 175, 80, 0.8);
  transform: translateY(2px);
}

.input-btn.launch {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  background-color: #d32f2f;
  font-size: 1em;
  border-color: #b71c1c;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto;
}

.input-btn.launch:active {
  background-color: #b71c1c;
  transform: scale(0.95);
}

.input-btn.launch.pressed {
  background-color: #ff5722 !important;
  border-color: #e64a19 !important;
  box-shadow: 0 0 20px rgba(255, 87, 34, 0.9);
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
    padding: 0 4px 160px; /* Reduced side padding and bottom padding */
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
  width: fit-content;
  display: flex;
  justify-content: center;
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

  .input-btn.launch {
    width: 60px;
    height: 60px;
    font-size: 0.8em;
  }
}

@media (max-width: 1200px) {
  .switch-view-btn {
    /* Keep default for Pinball3D, but VideoFeed uses .video-controls */
    bottom: auto;
    top: 82px;
    right: 10px;
  }

  /* Position the grouped controls in VideoFeed */
  .video-controls {
    bottom: auto !important;
    top: 82px !important;
    right: 10px !important;
  }

  /* Override scoped styles from VideoFeed.vue */
  .add-controls {
    bottom: 130px !important;
  }
}
</style>
