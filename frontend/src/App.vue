<template>
    <div id="app-container">
        <Header :connected="connected">

        </Header>

        <div id="main-layout">
            <div id="game-area">


                <div class="game-view-wrapper" id="playfield-container">
                    <div class="scoreboard-overlay" :class="{ 'fullscreen-overlay': isFullscreen }">
                        <ScoreBoard
                            :score="stats.score"
                            :highScore="stats.high_score"
                            :balls="stats.current_ball || 1"
                            :comboCount="stats.combo_count || 0"
                            :scoreMultiplier="stats.score_multiplier || 1.0"
                            :comboActive="stats.combo_active || false"
                            :isFullscreen="isFullscreen"
                        />
                    </div>

                    <VideoFeed
                        v-if="viewMode === 'video'"
                        :videoSrc="videoSrc"
                        :isTilted="isTilted"
                        :stats="stats"
                        :nudgeEvent="nudgeEvent"
                        :physics="physics"
                        :socket="sockets.game"
                        :configSocket="sockets.config"
                        :hasUnsavedChanges="hasUnsavedChanges"
                        @update-zone="handleZoneUpdate"
                        @update-rail="handleRailUpdate"
                        @update-bumper="handleBumperUpdate"
                        @save-layout="saveChanges"
                        @reset-zones="handleResetZones"
                        @toggle-view="toggleViewMode"
                        @toggle-fullscreen="toggleFullscreen"/>

                    <Pinball3D
                        v-if="viewMode === '3d'"
                        :socket="sockets.game"
                        :configSocket="sockets.config"
                        :config="physics"
                        :nudgeEvent="nudgeEvent"
                        :stats="stats"
                        :cameraMode="viewMode === '3d' ? 'perspective' : 'top-down'"
                        :autoStartEnabled="toggles.autoStart"
                        :showFlipperZones="showFlipperZones"
                        :connectionError="connectionError"
                        :isFullscreen="isFullscreen"
                        @toggle-view="toggleViewMode"
                        @toggle-fullscreen="toggleFullscreen"
                        @ship-destroyed="handleShipDestroyed"
                        @restart-game="startNewGame"
                        @update-rail="handleRailUpdate"
                        @update-bumper="handleBumperUpdate"
                        @update-zone="handleZoneUpdate"
                        @save-layout="saveChanges"
                    />
                    <ComboDisplay
                        :comboCount="stats.combo_count || 0"
                        :comboTimer="stats.combo_timer || 0"
                        :comboActive="stats.combo_active || false"
                        :maxTimer="physics.combo_window || 3.0"
                        :scoreMultiplier="stats.score_multiplier || 1.0"
                        :isFullscreen="isFullscreen"
                    />

                    <HighScoreBar
                        :score="stats.score"
                        :highScore="stats.high_score"
                        :isFullscreen="isFullscreen"
                    />

                    <ToastNotification
                        :show="toastVisible"
                        :title="toastTitle"
                        :message="toastMessage"
                        :isFullscreen="isFullscreen"
                        @hide="toastVisible = false"
                    />

                    <ReplayIndicator
                        v-if="stats.is_replay"
                        :hash="stats.hash"
                        :isFullscreen="isFullscreen"
                    />
                </div>

                <Controls :buttonStates="buttonStates"
                          :toggles="toggles"
                          @input="handleInput"
                          @toggle-ai="toggleAI"
                          @toggle-auto-start="toggleAutoStart"
                          :disabled="stats.is_training"/>


            </div>

            <GameHistory :gameHistory="stats.game_history" :gamesPlayed="stats.games_played"/>

            <Settings class="settings-panel"
                      :physics="physics"
                      :rewards="rewards"
                      :stats="stats"
                      :models="models"
                      :layouts="layouts"
                      :camera-presets="cameraPresets"
                      :selected-difficulty="selectedDifficulty"
                      :optimized-hyperparams="optimizedHyperparams"
                      v-model:selected-model="selectedModel"
                      v-model:selected-layout="selectedLayout"
                      v-model:selected-preset="selectedPreset"
                      @update-physics="handleUpdatePhysics"
                      @update-rewards="handleUpdateRewards"
                      @reset-config="handleResetConfig"
                      @apply-preset="applyPreset"
                      @save-preset="(savePreset as any)"
                      @delete-preset="deletePreset"
                      @load-model="(loadModel as any)"
                      @change-layout="changeLayout"
                      @start-training="startTraining"
                      @stop-training="stopTraining"
                      @update-difficulty="updateDifficulty"
                      @update:showFlipperZones="showFlipperZones = $event"
                      @save-new-layout="handleSaveNewLayout"
                      @save-layout="handleSaveLayout"/>

            <Logs :logs="logs"/>

        </div>

        <div id="input-area">
            <div class="input-group" style="flex: 2;">
                <button class="input-btn flipper-btn" :class="{ pressed: buttonStates.left }"
                        @mousedown="handleInput('KeyZ', 'down')"
                        @mouseup="handleInput('KeyZ', 'up')"
                        @touchstart.prevent="handleInput('KeyZ', 'down')"
                        @touchend.prevent="handleInput('KeyZ', 'up')"
                        :disabled="stats.is_training">Left
                </button>
                <button class="input-btn" :class="{ pressed: buttonStates.nudgeLeft }"
                        style="min-height: 34px; font-size: 14px;" @mousedown="handleInput('ShiftLeft', 'down')"
                        @mouseup="handleInput('ShiftLeft', 'up')"
                        @touchstart.prevent="handleInput('ShiftLeft', 'down')"
                        @touchend.prevent="handleInput('ShiftLeft', 'up')"
                        :disabled="stats.is_training">N Left
                </button>
            </div>

            <div class="input-group" style="flex: 1; align-items: center;">
                <button class="input-btn launch" :class="{ pressed: buttonStates.launch }"
                        @mousedown="handleInput('Space', 'down')"
                        @mouseup="handleInput('Space', 'up')"
                        @touchstart.prevent="handleInput('Space', 'down')"
                        @touchend.prevent="handleInput('Space', 'up')"
                        :disabled="stats.is_training">Launch
                </button>
            </div>

            <div class="input-group" style="flex: 2;">
                <button class="input-btn flipper-btn" :class="{ pressed: buttonStates.right }"
                        @mousedown="handleInput('Slash', 'down')"
                        @mouseup="handleInput('Slash', 'up')"
                        @touchstart.prevent="handleInput('Slash', 'down')"
                        @touchend.prevent="handleInput('Slash', 'up')"
                        :disabled="stats.is_training">Right
                </button>
                <button class="input-btn" :class="{ pressed: buttonStates.nudgeRight }"
                        style="min-height: 34px; font-size: 14px;"
                        @mousedown="handleInput('ShiftRight', 'down')"
                        @mouseup="handleInput('ShiftRight', 'up')"
                        @touchstart.prevent="handleInput('ShiftRight', 'down')"
                        @touchend.prevent="handleInput('ShiftRight', 'up')"
                        :disabled="stats.is_training">N Right
                </button>
            </div>
        </div>
    </div>
</template>

<script setup lang="ts">
import {ref, reactive, computed, watch, onMounted, onUnmounted, provide} from 'vue'
import SoundManager from './utils/SoundManager'

import type { Zone, PhysicsConfig, GameStats, RewardsConfig } from './types'



import Header from './components/Header.vue'
import ScoreBoard from './components/ScoreBoard.vue'
import ComboDisplay from './components/ComboDisplay.vue'
import VideoFeed from './components/VideoFeed.vue'
import HighScoreBar from './components/HighScoreBar.vue'
import Pinball3D from './components/Pinball3D.vue'
import Controls from './components/Controls.vue'
import Settings from './components/Settings.vue'
import GameHistory from './components/GameHistory.vue'
import Logs from './components/Logs.vue'
import ToastNotification from './components/ToastNotification.vue'
import ReplayIndicator from './components/ReplayIndicator.vue'
import sockets from './services/socket'

provide('sockets', sockets)
// window.sockets assigned in main.js now
const connected = ref(false)
const connectionError = ref(false)
const videoSrc = ref('')
const logs = ref<string[]>([])
const activeKeys = reactive(new Set())
const models = ref<any[]>([])
const selectedModel = ref(localStorage.getItem('pinball_selected_model') || '')
watch(selectedModel, (newVal: string) => {
    if (newVal) localStorage.setItem('pinball_selected_model', newVal)
})
const debounceTimers: Record<string, ReturnType<typeof setTimeout>> = {}
const nudgeEvent = ref<{ direction: string; time: number; type?: string; strength?: number } | null>(null)
const viewMode = ref('3d')
const layoutConfig = ref<any>(null)
const optimizedHyperparams = ref(null)

const isLoadingLayout = ref(false)
const hasUnsavedChanges = ref(false)
const isSyncingPhysics = ref(false)
let physicsSyncReleaseTimer: ReturnType<typeof setTimeout> | null = null

// Race condition prevention for auto-start toggle
const lastAutoStartToggleTime = ref(0)

// UI State
const isFullscreen = ref(false)

// Track button pressed states for visual feedback
const buttonStates = reactive({
    left: false,
    right: false,
    launch: false,
    nudgeLeft: false,
    nudgeRight: false
})

const addLog = (message: string) => {
    const timestamp = new Date().toLocaleTimeString()
    logs.value.push(`[${timestamp}] ${message}` as never)
    if (logs.value.length > 50) logs.value.shift()
}

// Track bumper destructions for milestone notifications
const bumpersDestroyed = ref(0)
const MILESTONES = [5, 10, 25, 50, 100]

// Toast notification state
const toastVisible = ref(false)
const toastTitle = ref('')
const toastMessage = ref('')

const handleShipDestroyed = () => {
    bumpersDestroyed.value++
    const count = bumpersDestroyed.value
    
    // Check if this is a milestone
    if (MILESTONES.includes(count)) {
        addLog(`🛸 MILESTONE: ${count} SHIPS DESTROYED! 🛸`)
        console.log(`[Milestone] ${count} ships destroyed!`)
        
        // Show toast notification
        toastTitle.value = `MILESTONE: ${count} SHIPS DESTROYED!`
        toastMessage.value = 'Keep up the great work!'
        toastVisible.value = true
    }
}


const stats = reactive<GameStats>({
    score: 0,
    high_score: 0,
    balls: 0,  // Legacy prop (unused now in favor of current_ball)
    balls_remaining: 3, // Actual balls remaining (3, 2, 1)
    current_ball: 1, // Current ball number (1, 2, 3)
    ball_count: 0,  // actual balls on table
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
    hash: null,
    seed: null,
    last_score: 0, // Track last game score
    game_over: false,
    is_high_score: false, // Frontend-managed high score flag
    is_replay: false
})

// Watch for new high score from backend
watch(() => stats.high_score, (newValue: number, oldValue: number) => {
    if (newValue > oldValue && oldValue > 0) {
        // New high score achieved! Backend updated the high_score
        stats.is_high_score = true
        addLog(`🏆 NEW HIGH SCORE: ${newValue}!`)
    }
})



const toggleViewMode = () => {
    viewMode.value = viewMode.value === '3d' ? 'video' : '3d'
}

const toggleFullscreen = () => {
    if (!document.fullscreenElement) {
        const elem = document.getElementById('playfield-container') || document.documentElement
        elem.requestFullscreen()
    } else {
        document.exitFullscreen()
    }
}

const isTilted = computed(() => stats.is_tilted || false)

const physics = reactive<any>({
    gravity: 1200.0,
    friction: 0.01,
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
    plunger_release_speed: 1500.0,
    launch_angle: 0.0,
    base_combo_bonus: 50,
    combo_multiplier_enabled: true,
    bumper_force: 800.0,
    bumper_respawn_time: 10.0,
    drop_target_cooldown: 2.0,
    zones: [
        {
            id: 'zone_left_default',
            type: 'left',
             points: [
              {x: 0.1, y: 0.6},
              {x: 0.3, y: 0.6},
              {x: 0.3, y: 0.8},
              {x: 0.1, y: 0.8}
            ]
        },
        {
            id: 'zone_right_default',
            type: 'right',
            points: [
              {x: 0.7, y: 0.6},
              {x: 0.9, y: 0.6},
              {x: 0.9, y: 0.8},
              {x: 0.7, y: 0.8}
            ]
        }
    ],
    rails: [],
    bumpers: [],
    rail_x_offset: 0,
    rail_y_offset: 0,
    god_mode: false,
    left_flipper_pos_x: 0.25,
    left_flipper_pos_y: 0.85,
    right_flipper_pos_x: 0.70,
    right_flipper_pos_y: 0.85
})

const rewards = reactive<RewardsConfig>({
    score_log_scale: 0.1,
    combo_increase_factor: 0.1,
    multiplier_increase_factor: 0.5,
    flipper_penalty: 0.0001,
    bumper_hit: 0.5,
    drop_target_hit: 1.0,
    rail_hit: 0.5
})

const toggles = reactive({
    ai: true,
    autoStart: true
})

// Auto-start state management (frontend-controlled)

const autoStartTimeoutId = ref(null)

const cameraPresets = ref<Record<string, any>>({})
const selectedPreset = ref(localStorage.getItem('pinball_selected_preset') || '')
watch(selectedPreset, (newVal: string) => {
    if (newVal) localStorage.setItem('pinball_selected_preset', newVal)
    else localStorage.removeItem('pinball_selected_preset')
})

const handleFullscreenChange = () => {
    console.log('Fullscreen changed:', document.fullscreenElement)
    isFullscreen.value = !!document.fullscreenElement
}

const deletePreset = (name: string) => {
    sockets.config.emit('delete_preset', {name: name})
    if (selectedPreset.value === name) {
        selectedPreset.value = ''
    }
}

const layouts = ref<any[]>([])
const selectedLayout = ref(localStorage.getItem('pinball_selected_layout') || 'default')
watch(selectedLayout, (newVal: string) => {
    if (newVal) localStorage.setItem('pinball_selected_layout', newVal)
})
const selectedDifficulty = ref('medium')
const showFlipperZones = ref(false)

const updateDifficulty = (difficulty: string) => {
    selectedDifficulty.value = difficulty
    sockets.training.emit('update_difficulty', {difficulty})
    addLog(`Set difficulty to: ${difficulty}`)
}

const handleInput = (key: string, type: string) => {
    // Update button state immediately for visual feedback
    if (type === 'down') {
        if (key === 'KeyZ') buttonStates.left = true
        if (key === 'Slash') buttonStates.right = true
        if (key === 'Space') {
            buttonStates.launch = true
            // Manual Start: If game is over, start new game.
            // Otherwise, let the event pass through to backend (controls plunger/relaunch)
            if (stats.game_over) {
                console.log('[Manual Start] Space pressed, starting new game...')
                startNewGame()
                return // Don't send input event for start
            }
        }
        if (key === 'ShiftLeft') {
            buttonStates.nudgeLeft = true
            nudgeEvent.value = {direction: 'left', time: Date.now()}
        }
        if (key === 'ShiftRight') {
            buttonStates.nudgeRight = true
            nudgeEvent.value = {direction: 'right', time: Date.now()}
        }
    } else {
        if (key === 'KeyZ') buttonStates.left = false
        if (key === 'Slash') buttonStates.right = false
        if (key === 'Space') buttonStates.launch = false
        if (key === 'ShiftLeft') buttonStates.nudgeLeft = false
        if (key === 'ShiftRight') buttonStates.nudgeRight = false
    }

    // Send to backend
    sockets.control.emit('input_event', {key, type})
}

const toggleAI = () => {
    toggles.ai = !toggles.ai
    sockets.training.emit('toggle_ai', {enabled: toggles.ai})
    addLog(`AI ${toggles.ai ? 'Enabled' : 'Disabled'}`)
}

const toggleAutoStart = () => {
    toggles.autoStart = !toggles.autoStart
    // Record time to prevent race condition where stale config overwrites user input
    lastAutoStartToggleTime.value = Date.now()
    
    addLog(`Auto-start ${toggles.autoStart ? 'Enabled' : 'Disabled'}`)
    
    // Sync to backend so vision.py knows about it!
    sockets.config.emit('set_physics_param', { key: 'auto_plunge_enabled', value: toggles.autoStart })

    // Cancel pending auto-start if disabled (check against toggles.autoStart)
    if (!toggles.autoStart && autoStartTimeoutId.value) {
        clearTimeout(autoStartTimeoutId.value)
        autoStartTimeoutId.value = null
        console.log('[Auto-Start Toggle] Cancelled pending timeout')
    }
}

// Function to start new game
const startNewGame = () => {
    addLog('Starting new game...')

    // Play Close Encounters motif if we just had a good game (score > 5000)

    if (stats.score > 5000) {
        console.log('🛸 Playing Close Encounters welcome for new game!')
        setTimeout(() => {
            // Use global callback (automatically handled by SoundManager)
            SoundManager.playCloseEncounters()
        }, 500) // Slight delay for dramatic effect
    }


    stats.is_high_score = false // Reset high score flag
    stats.is_replay = false
    stats.score = 0 // Reset score visually immediately
    bumpersDestroyed.value = 0 // Reset ship counter
    sockets.control.emit('start_game')
}

const changeLayout = (layoutId: string) => {
    console.trace('[App] changeLayout called with:', layoutId)
    if (layoutId && typeof layoutId === 'string') {
        selectedLayout.value = layoutId
    }
    isLoadingLayout.value = true
    addLog(`Loading layout: ${selectedLayout.value}`)
    sockets.config.emit('load_layout_by_name', {name: selectedLayout.value})
}

const handleSaveNewLayout = (name: string) => {
    console.log("Saving new layout:", name)
    sockets.config.emit('save_new_layout', {name: name})
}

const handleSaveLayout = () => {
    console.log("Saving current layout")
    sockets.config.emit('save_layout')
}

const startTraining = (config: any) => {

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
            ent_coef: config.entCoef,
            gamma: config.gamma,
            n_steps: config.nSteps,
            batch_size: config.batchSize,
            gae_lambda: config.gaeLambda,
            layout: config.layout,
            physics: config.physics,
        })

        addLog('Auto-start Disabled (Training Started)')

    } catch (e: any) {
        addLog(`Error starting training: ${e.message}`)
    }
}

const stopTraining = () => {
    try {
        addLog('Stopping training...')
        sockets.training.emit('stop_training')
    } catch (e: any) {
        addLog(`Error stopping training: ${e.message}`)
    }
}

const loadModel = (filename: string) => {
    addLog(`Loading model: ${filename}`)
    sockets.training.emit('load_model', {filename})
}



const handleUpdateRewards = (data: any) => {
    // Update local state
    Object.keys(data).forEach(key => {
        rewards[key] = data[key]
    })
    // Send to backend
    sockets.config.emit('update_rewards', data)
}

const applyPreset = (name: string) => {
    const preset = cameraPresets.value[name]
    if (!preset) {
        console.error('Preset not found:', name)
        return
    }

    selectedPreset.value = name

    // Apply all camera properties from preset
    Object.keys(preset).forEach(key => {
        if (key in physics) {
            physics[key] = preset[key]
        }
    })

    // Send to backend
    sockets.config.emit('apply_preset', {name})
    addLog(`Applied camera preset: ${name}`)
}

const savePreset = (name: string, config: any) => {
    sockets.config.emit('save_preset', {name, config})
    addLog(`Saved camera preset: ${name}`)
}

const handleZoneUpdate = (newZones: Zone[]) => {
    physics.zones = newZones
    if (layoutConfig.value) layoutConfig.value.zones = newZones
    hasUnsavedChanges.value = true

    if (debounceTimers.zones) clearTimeout(debounceTimers.zones)
    debounceTimers.zones = setTimeout(() => {
        sockets.config.emit('update_zones', physics.zones)
    }, 300)
}

const handleRailUpdate = (newRails: any[]) => {
    physics.rails = newRails
    if (layoutConfig.value) layoutConfig.value.rails = newRails
    hasUnsavedChanges.value = true

    if (debounceTimers.rails) clearTimeout(debounceTimers.rails)
    debounceTimers.rails = setTimeout(() => {
        sockets.config.emit('update_rails', physics.rails)
    }, 300)
}

const handleBumperUpdate = (newBumpers: any[]) => {
    physics.bumpers = newBumpers
    if (layoutConfig.value) layoutConfig.value.bumpers = newBumpers
    hasUnsavedChanges.value = true

    if (debounceTimers.bumpers) clearTimeout(debounceTimers.bumpers)
    debounceTimers.bumpers = setTimeout(() => {
        sockets.config.emit('update_bumpers', physics.bumpers)
    }, 300)
}

const handleUpdatePhysics = (key: string, value: any) => {
    // Update local state is handled by v-model in Settings usually, but if this event passes key/value:
    physics[key] = value
    hasUnsavedChanges.value = true
    
    // Emit single parameter update if supported, or full sync?
    // Based on previous code, we likely have set_physics_param
    sockets.config.emit('set_physics_param', { key, value })
}

const handleResetConfig = () => {
    if (confirm('Are you sure you want to reset all physics parameters to default?')) {
        sockets.config.emit('reset_config')
    }
}

const handleResetZones = () => {
    console.log("Reset zones")
    // Default zones defined in VideoFeed logic (Left/Right)
    const defaultZones = [
        {
            id: 'zone_left_default',
            type: 'left',
             points: [
              {x: 0.1, y: 0.6},
              {x: 0.3, y: 0.6},
              {x: 0.3, y: 0.8},
              {x: 0.1, y: 0.8}
            ]
        },
        {
            id: 'zone_right_default',
            type: 'right',
            points: [
              {x: 0.7, y: 0.6},
              {x: 0.9, y: 0.6},
              {x: 0.9, y: 0.8},
              {x: 0.7, y: 0.8}
            ]
        }
    ]
    physics.zones = JSON.parse(JSON.stringify(defaultZones))
    hasUnsavedChanges.value = true
    sockets.config.emit('update_zones', physics.zones)
}

const saveChanges = () => {
    console.log("Saving changes")
    sockets.config.emit('save_layout')
    hasUnsavedChanges.value = false
}



const handleKeydown = (e: KeyboardEvent) => {
    // Ignore keyboard events if user is typing in an input field
    const target = e.target as HTMLElement
    if (target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.tagName === 'SELECT')) {
        return // Don't process game controls when typing
    }

    if (e.repeat) return
    if (e.code === 'KeyZ' || e.code === 'Slash' || e.code === 'Space' || e.code === 'ShiftLeft' ||
        e.code === 'ShiftRight') {
        e.preventDefault()
        handleInput(e.code, 'down')
    }
}

const handleKeyup = (e: KeyboardEvent) => {
    // Ignore keyboard events if user is typing in an input field
    const target = e.target as HTMLElement
    if (target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.tagName === 'SELECT')) {
        return // Don't process game controls when typing
    }

    if (e.code === 'KeyZ' || e.code === 'Slash' || e.code === 'Space' || e.code === 'ShiftLeft' ||
        e.code === 'ShiftRight') {
        handleInput(e.code, 'up')
    }
}

// Watch for combo reset to reset musical scale
watch(() => stats.combo_count, (newCombo: number, oldCombo: number) => {
    // If combo dropped to 0, reset the musical scale
    if (oldCombo > 0 && newCombo === 0) {
        SoundManager.resetScale()
    }
})

// Watch for ball count changes to detect game over and auto-restart

watch(() => stats.ball_count, (newCount: number, oldCount: number) => {
    // If all balls drained (ball_count went to 0) and we have balls remaining
    if (oldCount > 0 && newCount === 0) {
        // If we still have balls remaining (checked from updated stats)
        // Note: stats.balls_remaining comes from backend "lives" logic (3, 2, 1)
        // If > 0, we expect backend to respawn
        if (stats.balls_remaining > 0) {
             // Do NOTHING here. Backend handles respawn.
             // We only implemented startNewGame helper if we needed to trigger it
             // But usually physics engine adds ball automatically?
             // Wait, in vision.py we implemented explicit physics_engine.add_ball
             // So we don't need to call startNewGame() here!
             // Calling startNewGame() resets the backend state (Ball 1), causing infinite loop.
             
             // Just let backend spawn the ball.
        } else {
            // Game over - all balls drained and no balls remaining
            // console.log('[Ball Count Watch] GAME OVER! Starting new game in 3 seconds...')
            if (stats.score > 0) {
                addLog(`Game Over! Final Score: ${stats.score}`)
                stats.last_score = stats.score // Save last score
            }
            // stats.game_over is also set by backend, but we can set it here for immediate UI
            stats.game_over = true 
            
            // Auto-start is now handled by Pinball3D.vue with a visible timer
        }
    }
})

onMounted(() => {
    // Resume AudioContext on first user interaction (required by browsers)
    const resumeAudio = () => {
        console.log('[Audio] Resuming AudioContext on user interaction...')
        SoundManager.resume()
        console.log('[Audio] AudioContext state:', SoundManager.ctx?.state)

        // Test sound immediately after resume
        setTimeout(() => {
            console.log('[Audio] Playing test bumper sound...')
            SoundManager.playBumper(1.0)
        }, 100)

        document.removeEventListener('click', resumeAudio)
        document.removeEventListener('keydown', resumeAudio)
        document.removeEventListener('touchstart', resumeAudio)
    }
    document.addEventListener('click', resumeAudio, {once: true})
    document.addEventListener('keydown', resumeAudio, {once: true})
    document.addEventListener('touchstart', resumeAudio, {once: true})

    sockets.config.on('physics_config_loaded', (config: PhysicsConfig) => {
        // console.log('Physics Config Loaded:', config)
        if (config) {
            isSyncingPhysics.value = true
            if (physicsSyncReleaseTimer) {
                clearTimeout(physicsSyncReleaseTimer)
                physicsSyncReleaseTimer = null
            }
            try {
                (window as any).__PHYSICS__ = config // Expose for E2E testing
                Object.keys(config).forEach(key => {
                    physics[key] = config[key]
                })

                if (config.rewards) {
                    Object.keys(config.rewards).forEach(key => {
                        rewards[key] = config.rewards[key]
                    })
                }

                // Sync Auto-Start toggle from backend config
                // Ignore if user recently toggled it manually (race condition fix)
                if (config.auto_plunge_enabled !== undefined) {
                    const timeSinceToggle = Date.now() - lastAutoStartToggleTime.value
                    if (timeSinceToggle > 2000) {
                        toggles.autoStart = config.auto_plunge_enabled
                        addLog(`Auto-Start synced from config: ${config.auto_plunge_enabled}`)
                    } else {
                        console.log(`[Auto-Start] Ignoring config sync (user toggled ${timeSinceToggle}ms ago)`)
                    }
                }

                // Register global callback for Alien Shake effect
                SoundManager.setAlienResponseCallback(() => {
                    console.log('👽 GLOBAL ALIEN RESPONSE TRIGGERED!')
                    // 1. Trigger Visual Shake (Stronger, explicit 'alien' type)
                    nudgeEvent.value = {
                        direction: (Math.random() > 0.5 ? 'left' : 'right'), 
                        time: Date.now(),
                        type: 'alien',
                        strength: 5.0 // Much stronger visual application
                    }
                    
                    // 2. Trigger Physics Nudge (Free, massive force)
                    sockets.control.emit('alien_nudge')
                    
                    // 3. Vibrate device if supported - redundant here as SoundManager handles it, 
                    // but good for redundancy or specific UI feedback.
                    // SoundManager has better pattern now.
                })
                if (config.camera_presets) {
                    cameraPresets.value = config.camera_presets
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
                    const preset = cameraPresets.value[config.last_preset]
                    if (preset) {
                        if (preset.camera_pitch !== undefined) physics.camera_pitch = preset.camera_pitch
                        if (preset.camera_x !== undefined) physics.camera_x = preset.camera_x
                        if (preset.camera_y !== undefined) physics.camera_y = preset.camera_y
                        if (preset.camera_z !== undefined) physics.camera_z = preset.camera_z
                        if (preset.camera_zoom !== undefined) physics.camera_zoom = preset.camera_zoom
                    }
                    addLog(`Restored last camera preset: ${config.last_preset}`)
                }
                if (config.current_layout_id) {
                    console.log(`[Config Loaded] Updating selectedLayout from config: ${config.current_layout_id} (was: ${selectedLayout.value})`)
                    selectedLayout.value = config.current_layout_id
                    addLog(`Restored last layout: ${config.current_layout_id}`)
                }
            } finally {
                physicsSyncReleaseTimer = setTimeout(() => {
                    isSyncingPhysics.value = false
                    physicsSyncReleaseTimer = null
                }, 0)
            }
        }
    })

    sockets.training.on('models_list', (data: any[]) => {
        models.value = data
        if (!selectedModel.value && data.length > 0) {
            selectedModel.value = data[0].filename
        }
    })

    // Listen for optimized hyperparameters
    sockets.training.on('hyperparams_loaded', (params: any) => {
        // console.log('Received optimized hyperparameters:', params)
        optimizedHyperparams.value = params
        addLog('Loaded optimized hyperparameters')
    })

    sockets.training.on('connect', () => {
        sockets.training.emit('get_models')
        sockets.training.emit('get_hyperparams')
    })

    sockets.config.on('presets_updated', (presets: any) => {
        cameraPresets.value = presets
        if (!selectedPreset.value && 'Default' in presets) {
            selectedPreset.value = 'Default'
        }
    })

    sockets.game.on('connect', () => {
        connected.value = true
        addLog('Connected to game server')
        // Expose sockets for E2E testing
        if (window) {
            (window as any).sockets = sockets;
            (window as any).__APP_STATS__ = stats;
        }

        // Start initial game after a short delay (let physics engine initialize)
        setTimeout(() => {
            // console.log('[Initial Game] Checking if we should start first game...')
            // console.log(`[Initial Game] ball_count: ${stats.ball_count}`)

            // If auto-start is enabled and no balls exist, start the first game
            // Added check for score and games_played to prevent resets on socket reconnection
            if (toggles.autoStart && stats.ball_count === 0 && stats.score === 0 && stats.games_played === 0 && !stats.game_over) {
                // console.log('[Initial Game] Starting first game automatically')
                addLog('Starting first game...')
                startNewGame()
            } else {
                // console.log('[Initial Game] Not starting automatically (auto-start off or ball already exists)')
            }
        }, 1000) // Wait 1 second for backend to fully initialize
    })

    sockets.config.on('connect', () => {
        addLog('Connected to config server')
        sockets.config.emit('load_physics')
        sockets.config.emit('get_layouts')
        sockets.training.emit('get_models')
    })

    sockets.game.on('disconnect', () => {
        connected.value = false
        addLog('Disconnected from server')
    })

    sockets.game.on('connect_error', (err: Error) => {
        console.error('Connection Error:', err)
        connectionError.value = true
        addLog(`Connection Error: ${err.message}`)
    })

    sockets.game.on('connect', () => {
        connectionError.value = false
    })

    sockets.game.on('video_frame', (data: {image: string}) => {
        videoSrc.value = 'data:image/jpeg;base64,' + data.image
    })

    sockets.game.on('stats_update', (data: any) => {
        // Only protect frontend-managed properties (not high_score - that comes from backend now)
        // Allow game_over to be synced from backend!
        const frontendOnlyProps = ['is_high_score'] // last_score now comes from backend
        const filteredData = {...data}
        frontendOnlyProps.forEach(prop => delete filteredData[prop])

        Object.assign(stats, filteredData)
        if (data.nudge) {
            nudgeEvent.value = data.nudge
        }
    })

    sockets.game.on('game_init', (data: any) => {
        console.log('Game Initialized:', data)
        stats.seed = data.seed
        stats.hash = data.hash
        // We could set is_replay flag if we had one in stats
    })

    sockets.game.on('game_hash', (data: any) => {
        console.log('Game Hash Received:', data)
        stats.seed = data.seed
        stats.hash = data.hash
    })

    sockets.game.on('replay_status', (data: any) => {
        if (data.status === 'playing') {
            stats.is_replay = true
            addLog(`REPLAY STARTED: ${stats.hash?.substring(0,8)}`)
        }
    })

    sockets.config.on('layout_loaded', (data: any) => {
        console.log('Layout loaded:', data)
        if (data.status === 'success') {
            isLoadingLayout.value = false
            // Request the new physics config to update 3D view
            // sockets.config.emit('load_physics') // redundant? checks loop
        } else {
            isLoadingLayout.value = false
        }
    })

    sockets.training.on('ai_status', (data: any) => {
        toggles.ai = data.enabled
        addLog(`AI Enabled: ${data.enabled}`)
    })

    sockets.training.on('model_selected', (data: any) => {
        addLog(`Auto-selected model: ${data.model}`)
        selectedModel.value = data.model
        // Refresh model list to ensure the new model is in the dropdown
        sockets.training.emit('get_models')
    })


    sockets.training.on('difficulty_status', (data: any) => {
        selectedDifficulty.value = data.difficulty
        addLog(`Difficulty updated: ${data.difficulty}`)
    })

    sockets.training.on('training_finished', (data: any) => {
        addLog(`Training Finished. New Model: ${data.model}`)
        selectedModel.value = data.model
        // Refresh models to ensure lists are in sync
        sockets.training.emit('get_models')

        // Re-enable Auto-Start and launch a game
        toggles.autoStart = true
        addLog('Auto-start Re-enabled. Starting game...')
        setTimeout(() => {
            startNewGame()
        }, 2000)
    })

    sockets.config.on('layouts_list', (data: any[]) => {
        console.log('[Layouts List] Received:', data.map((l: any) => l.id))
        layouts.value = data
        // Check if selectedLayout exists in list
        const exists = layouts.value.some((l: any) => l.id === selectedLayout.value)
        if (!exists) {
            console.warn(`[Layouts List] Selected layout '${selectedLayout.value}' not found in list.`)
            // Start of auto-reset logic
            /*
            // Try 'default' (lowercase)
            const defaultExists = layouts.value.some(l => l.id === 'default')
            if (defaultExists) {
                console.warn(`[Layouts List] Reverting to 'default'`)
                selectedLayout.value = 'default'
            } else if (layouts.value.length > 0) {
                // Fallback to first
                console.warn(`[Layouts List] Reverting to first available: ${layouts.value[0].id}`)
                selectedLayout.value = layouts.value[0].id
            }
            */
        }
    })

    sockets.config.on('layout_loaded', (data: any) => {
        if (data.status === 'success') {
            addLog('Layout loaded successfully')
        } else {
            addLog(`Error loading layout: ${data.message}`)
        }
    })

    sockets.config.emit('get_layouts')
    sockets.training.emit('get_models')

    sockets.game.on('log_message', (data: any) => {
        addLog(data.message)
    })

    sockets.game.on('ball_loaded', (data: any) => {
        console.log(`🔫 Ball ${data.ball_number} loaded - playing revolver ratchet sound`)
        SoundManager.playRevolverRatchet(0.8)
    })

    sockets.training.on('models_list', (data: any[]) => {
        // console.log("Provably Fair / Model Verification Hashes:", data)
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
    sockets.training.on('model_loaded', (data: any) => {
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
        sockets.control.emit('input_event', {key: 'KeyZ', type: 'up'})
        sockets.control.emit('input_event', {key: 'Slash', type: 'up'})
        sockets.control.emit('input_event', {key: 'Space', type: 'up'})
        sockets.control.emit('input_event', {key: 'ShiftLeft', type: 'up'})
        sockets.control.emit('input_event', {key: 'ShiftRight', type: 'up'})
    })

    document.addEventListener('fullscreenchange', handleFullscreenChange)

    // Expose stats for Cypress testing
    if ((window as any).Cypress || (import.meta as any).env.DEV) {
        (window as any).__APP_STATS__ = stats
    }

    // Diagnostic: Log ball_count every 3 seconds to see if it's updating
    // setInterval(() => {
    //   console.log(`[Diagnostic] Current ball_count: ${stats.ball_count}, balls: ${stats.balls}, score: ${stats.score}`)
    // }, 3000)

})

onUnmounted(() => {
    // Clean up auto-start timeout
    if (autoStartTimeoutId.value) {
        clearTimeout(autoStartTimeoutId.value)
    }

    window.removeEventListener('keydown', handleKeydown)
    window.removeEventListener('keyup', handleKeyup)
    document.removeEventListener('fullscreenchange', handleFullscreenChange)
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
    max-width: 2400px;
    margin: 0 auto;
    padding: 0 20px 180px;
}

#main-layout {
    /* Base Desktop Layout (> 1400px) */
    display: grid;
    /* Use minmax and 1fr for flexible central column, auto for fixed sidebars */
    grid-template-columns: 280px minmax(500px, 1fr) 300px;
    grid-template-rows: auto auto; /* Game/Sides then Logs */
    grid-template-areas:
    "history game settings"
    "logs logs logs";
    gap: 20px;
    width: 100%;
    /* Increase max-width to allow expansion on large screens */
    max-width: 2400px;
    margin: 20px auto;
    align-items: start;
    justify-content: center;
}

#game-area {
    grid-area: game;
    display: flex;
    flex-direction: column;
    align-items: center;
    width: 100%;
    min-width: 0; /* Prevents flex item from overflowing grid track */
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
    margin: 10px;
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

/* Laptop / Tablet (900px - 1400px): 2 Columns */
@media (max-width: 1400px) {
    #main-layout {
        grid-template-columns: 1fr 340px;
        grid-template-areas:
      "game settings"
      "history settings"
      "logs logs";
        gap: 20px;
    }
}

/* Mobile / Small Tablet (< 900px): 1 Column */
@media (max-width: 900px) {
    #main-layout {
        grid-template-columns: 1fr;
        grid-template-areas:
      "game"
      "history"
      "settings"
      "logs";
        gap: 15px;
    }

    #input-area {
        display: flex;
    }
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
    max-width: 100%; /* Ensure it doesn't exceed container */
    box-sizing: border-box; /* Include padding in width */
    pointer-events: none;
    display: flex;
    justify-content: center;
    /* overflow: hidden; REMOVED to allow combo badge to show */
    padding: 0 10px; /* Add some safety padding */
}

.scoreboard-overlay.fullscreen-overlay {
    top: 40px;
    left: 40px;
    transform: none;
    width: auto;
    justify-content: flex-start;
    align-items: flex-start;
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
    0% {
        box-shadow: 0 0 0 0 rgba(255, 152, 0, 0.7);
    }
    70% {
        box-shadow: 0 0 0 10px rgba(255, 152, 0, 0);
    }
    100% {
        box-shadow: 0 0 0 0 rgba(255, 152, 0, 0);
    }
}
</style>
