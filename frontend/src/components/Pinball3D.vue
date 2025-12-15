<template>
  <div ref="container" 
       class="pinball-container" 
       :class="{ 'controls-active': controlsActive }"
       style="touch-action: pan-y"
       @mousedown="onMouseDown"
       @click="activateControls"
       @touchstartPassive="activateControls"
       @mousemove="onMouseMove" 
       @mouseup="onMouseUp"
       @mouseleave="onMouseUp"
       @wheel.prevent="onWheel"
       @dragover.prevent
       @drop="onDrop">

    <!-- Training Overlay (Above Game Over) -->
    <div v-if="stats && stats.is_training" class="overlay-screen training-overlay">
      <h2>TRAINING IN PROGRESS</h2>
      <p style="font-size: 1.2em; font-weight: bold; color: #4caf50;">{{ Math.round(stats.training_progress * 100) }}%</p>
      <p>Step {{ formatNumber(stats.current_step) }} / {{ formatNumber(stats.total_steps) }}</p>
      <div style="width: 60%; height: 8px; background: #555; border-radius: 4px; overflow: hidden; margin-top: 10px;">
        <div
          :style="{ width: (stats.training_progress * 100) + '%', height: '100%', background: '#4caf50', transition: 'width 0.3s' }">
        </div>
      </div>
    </div>

    <!-- Replay Indicator -->
    <ReplayIndicator 
        v-if="isReplayActive"
        :hash="stats?.hash" 
        :isFullscreen="isFullscreen"
    />

    <!-- Tilted Overlay -->
    <div v-if="stats?.is_tilted === true" class="overlay-screen tilted-overlay">
        <h1>TILTED!</h1>
    </div>

    <!-- Game Over Overlay -->
    <div v-if="stats?.game_over || showHighScores" class="overlay-screen game-over-overlay" :class="{ 'is-fullscreen': isFullscreen }">
        <div class="game-over-text">{{ stats?.game_over ? 'GAME OVER' : 'HIGH SCORES' }}</div>
        <div v-if="stats?.game_over && stats.is_high_score" class="high-score-text">NEW HIGH SCORE!</div>
        <div class="final-score" v-if="stats?.game_over">SCORE: {{ formatNumber(stats.last_score) }}</div>

        <!-- High Score Table -->
        <div class="high-score-table-container" v-if="stats?.high_scores && stats.high_scores.length > 0" @wheel.stop>
            <table class="high-score-table">
                <thead>
                    <tr>
                        <th>Rank</th>
                        <th>Score</th>
                        <th>Model/Player</th>
                        <!-- <th>Layout</th> -->
                        <th>Date</th>
                    </tr>
                </thead>
                <tbody>
                    <tr v-for="(entry, index) in stats.high_scores" :key="index" :class="{ 'highlight': stats?.game_over && entry.score === stats.last_score }">
                        <td>{{ index + 1 }}</td>
                        <td>{{ formatNumber(entry.score) }}</td>
                        <td>
                            <div class="model-name-truncate" :title="entry.model">{{ entry.model }}</div>
                        </td>
                        <!-- <td>{{ entry.layout }}</td> -->
                        <td>{{ entry.date }}</td>
                    </tr>
                </tbody>
            </table>
        </div>
        
        <div v-if="stats && stats.game_over">
            <div v-if="autoStartEnabled" class="auto-restart-text">
                Restarting in {{ Math.ceil(autoRestartTimer) }}...
            </div>
            <div v-else class="press-start-text">
                PRESS LAUNCH TO START
            </div>
        </div>
        <div v-else class="close-overlay-container">
            <button class="close-overlay-btn" @click="emit('close-high-scores')">Close</button>
        </div>
    </div>

    <div v-if="!config?.rails || connectionError" class="loading-placeholder">
      <div class="spinner"></div>
      <div class="loading-text">{{ connectionError ? 'CONNECTION ERROR' : 'INITIALIZING SYSTEM' }}</div>
      <div style="margin-top: 10px; font-size: 0.8em; color: #666;">
        {{ connectionError ? 'RETRYING LINK...' : 'ESTABLISHING LINK...' }}
      </div>
    </div>

    <div v-if="cameraMode === 'perspective' && showDebug" class="debug-overlay">
      <div>Camera X: {{ cameraDebug.x.toFixed(2) }}</div>
      <div>Camera Y: {{ cameraDebug.y.toFixed(2) }}</div>
      <div>Camera Z: {{ cameraDebug.z.toFixed(2) }}</div>
    </div>
    
    <!-- MULTIBALL DEBUG INDICATOR -->
    <div v-if="activeBallCount > 1" class="multiball-indicator">
      🎱 MULTIBALL: {{ activeBallCount }} balls
    </div>

    <!-- PERMANENT DEBUG PANEL (bottom-right) -->
    <div class="permanent-debug-panel">
      <div>Balls: {{ activeBallCount }}</div>
      <div v-if="camera && 'aspect' in camera">Aspect: {{ camera.aspect?.toFixed(3) }}</div>
      <div v-if="renderer">Canvas: {{ rendererSize }}</div>
      <div v-if="container">Container: {{ containerSize }}</div>
    </div>

    <!-- Rail Editor Controls -->
    <div class="editor-controls" v-if="cameraMode === 'perspective' && isEditMode">

        <div v-if="isEditMode" class="edit-actions">
            <button @click="addRail">+ Rail</button>
            <button @click="addBumper">+ Bumper</button>
            <button
                @click="deleteSelectedObject"
                :disabled="selectedRailIndex === -1 && selectedBumperIndex === -1">🗑️ Delete</button>
        </div>
    </div>
    
    <!-- Game Settings Overlay with Backdrop -->
    <div v-if="showSettings" class="settings-backdrop" @click="showSettings = false"></div>
    <div v-if="showSettings" class="sound-settings-overlay">
        <GameSettings 
            :smokeIntensity="smokeIntensity"
            @update-smoke-intensity="(val: number) => smokeIntensity = val"
            @close="showSettings = false"
            @toggle-high-scores="toggleHighScores"
        />
    </div>

    <!-- Settings Toggle Button (Top Right) -->
    <button class="sound-toggle-btn" @click="showSettings = !showSettings">
        ⚙️
    </button>
    
    <!-- Stuck Ball Dialog -->
    <div v-if="stuckBallDialog" class="stuck-ball-dialog">
      <div class="dialog-content">
        <h2>BALL NOT FOUND! RESTART?</h2>
        <div class="timer">{{ stuckBallTimer }}</div>
        <div class="buttons">
          <button @click="confirmRelaunch" class="confirm-btn">Yes</button>
          <button @click="cancelRelaunch" class="cancel-btn">No</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, computed } from 'vue'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import SoundManager from '../utils/SoundManager'
import GameSettings from './GameSettings.vue'
import type { PhysicsConfig, GameStats, Point } from '../types'
import ReplayIndicator from "@/components/ReplayIndicator.vue";


onMounted(() => {
    console.log(`[Pinball3D] MOUNTED. Camera Mode: ${props.cameraMode}, Is Fullscreen: ${props.isFullscreen}`)
})

const props = withDefaults(defineProps<{
    socket?: any;
    configSocket?: any;
    config?: PhysicsConfig | null;
    nudgeEvent?: { direction: string; time: number; type?: string; strength?: number } | null;
    stats?: GameStats | null;
    cameraMode?: string;
    autoStartEnabled?: boolean;
    showFlipperZones?: boolean;
    connectionError?: boolean;
    isFullscreen?: boolean;
    isEditMode?: boolean; // NEW: controlled from App.vue
    showHighScores?: boolean;
}>(), {
    cameraMode: 'perspective',
    autoStartEnabled: false,
    showFlipperZones: false,
    connectionError: false,
    isFullscreen: false
})

const emit = defineEmits([
    'toggle-fullscreen',
    'toggle-high-scores',
    'toggle-view',
    'ship-destroyed',
    'restart-game',
    'update-rail',
    'update-bumper',
    'close-high-scores'
])

const container = ref<HTMLElement | null>(null)
let scene: THREE.Scene, camera: THREE.PerspectiveCamera | THREE.OrthographicCamera, renderer: THREE.WebGLRenderer, controls: OrbitControls
let resizeObserver: ResizeObserver
// let socket // Use props.socket
// Interactive objects container type
interface InteractiveObjects {
    left: THREE.Group | null;
    right: THREE.Group | null;
    upper: any[];
    dropTargets: THREE.Mesh[];
    bumpers: THREE.Group[];
    mothership?: THREE.Group;
    [key: string]: any;
}

let balls: THREE.Mesh[] = [] // Array of mesh objects
let flippers: InteractiveObjects = { left: null, right: null, upper: [], dropTargets: [], bumpers: [] }
let tableGroup: THREE.Group
let ballGeo: THREE.SphereGeometry, ballMat: THREE.MeshStandardMaterial
let zoneMeshes: THREE.Mesh[] = [] // Store zone meshes for show/hide

// Ball effects for combo-based visuals
let ballGlows: any[] = []
let ballTrails: { mesh: THREE.Mesh, positions: THREE.Vector3[] }[] = [] // { mesh: THREE.Mesh, positions: THREE.Vector3[] }
let ballParticles: any[] = []

// Physics Config (to sync dimensions)
let physicsConfig = ref<PhysicsConfig | null>(null)
// Store previous flipper values for change detection (not reactive)
let lastFlipperValues = {
    length: null as number | null,
    width: null as number | null,
    tipWidth: null as number | null
}
const cameraDebug = ref({ x: 0, y: 0, z: 0 })
const showDebug = ref(false)
const showSettings = ref(false)
const smokeIntensity = ref(0.5)
let debugTimeout: ReturnType<typeof setTimeout> | null = null

// Auto-Restart Timer State
const autoRestartTimer = ref(3)
let autoRestartInterval: ReturnType<typeof setInterval> | null = null

// Watch for Game Over state
watch(() => props.stats?.game_over, (isGameOver: boolean) => {
    if (isGameOver) {
        // Game Over Triggered
        if (props.autoStartEnabled) {
            startRestartCountdown()
        }
    } else {
        // Game Started / Reset
        stopRestartCountdown()
    }
})

// Also watch autoStartEnabled in case it's toggled ON during Game Over
watch(() => props.autoStartEnabled, (enabled: boolean) => {
    if (enabled && props.stats?.game_over) {
        startRestartCountdown()
    } else {
        stopRestartCountdown()
    }
})

watch(() => props.isEditMode, (newVal: boolean, oldVal: boolean) => {
    if (newVal !== oldVal) {
        updateRailHandles()
    }
})

const startRestartCountdown = () => {
    if (autoRestartInterval) clearInterval(autoRestartInterval)
    autoRestartTimer.value = 3
    
    autoRestartInterval = setInterval(() => {
        autoRestartTimer.value -= 1
        if (autoRestartTimer.value <= 0) {
            stopRestartCountdown()
            emit('restart-game')
        }
    }, 1000)
}

const stopRestartCountdown = () => {
    if (autoRestartInterval) {
        clearInterval(autoRestartInterval)
        autoRestartInterval = null
    }
    autoRestartTimer.value = 3 // Reset for next time
}

const toggleHighScores = () => {
    showSettings.value = false
    emit('toggle-high-scores')
}

// Computed properties for permanent debug panel
const rendererSize = computed(() => {
  if (!renderer) return 'N/A'
  try {
    const size = renderer.getSize(new THREE.Vector2())
    return `${Math.round(size.x)}x${Math.round(size.y)}`
  } catch (e) {
    return 'Error'
  }
})

const containerSize = computed(() => {
  if (!container.value) return 'N/A'
  return `${container.value.clientWidth}x${container.value.clientHeight}`
})

const activeBallCount = ref(0)

// Computed: Check if replay is active
const isReplayActive = computed(() => props.stats?.is_replay)

// Mobile Controls State
const controlsActive = ref(false)

// Stuck Ball State
const stuckBallDialog = ref(false)
const stuckBallTimer = ref(20)
let stuckBallInterval: ReturnType<typeof setInterval> | null = null

const formatNumber = (num: number | null | undefined) => {
  if (num === undefined || num === null) return '0'
  return num.toLocaleString()
}

// Rail Editor State
// isEditMode is now a prop from App.vue
const selectedRailIndex = ref(-1)
const selectedBumperIndex = ref(-1)
const selectedType = ref(null) // 'rail' or 'bumper'
const isDragging = ref(false)
const dragPoint = ref(null) // 'p1', 'p2', or 'body'
const dragStartPos = new THREE.Vector2()
const dragState: { initialP1: Point | null, initialP2: Point | null, initialPos: Point | null } = { initialP1: null, initialP2: null, initialPos: null }
const raycaster = new THREE.Raycaster()
const mouse = new THREE.Vector2()
const railHandles: THREE.Mesh[] = [] // Array of mesh handles
const railMeshes: THREE.Mesh[] = [] // Array of rail body meshes
const bumperMeshes: THREE.Group[] = [] // Array of bumper meshes
let dragPlane = new THREE.Plane() // Plane for raycasting during drag

// Camera Pan State
const isPanning = ref(false)
const panStart = new THREE.Vector2()
const cameraStartPos = new THREE.Vector3()



const addRail = () => {
    // Add a default rail in the center
    const newRail = {
        p1: { x: 0.4, y: 0.4 },
        p2: { x: 0.6, y: 0.6 }
    }
    // props.configSocket.emit('create_rail', newRail)
    const newRails = [...(props.config.rails || [])]
    newRails.push(newRail)
    emit('update-rail', newRails)
}

const addBumper = () => {
    const newBumper = {
        x: 0.5,
        y: 0.5,
        radius_ratio: 0.04,
        value: 100
    }
    // props.configSocket.emit('create_bumper', newBumper)
    const newBumpers = [...(props.config.bumpers || [])]
    newBumpers.push(newBumper)
    emit('update-bumper', newBumpers)
}

const deleteSelectedObject = () => {
    if (selectedType.value === 'rail' && selectedRailIndex.value !== -1) {
        // props.configSocket.emit('delete_rail', { index: selectedRailIndex.value })
        const newRails = [...(props.config.rails || [])]
        newRails.splice(selectedRailIndex.value, 1)
        emit('update-rail', newRails)
        
        selectedRailIndex.value = -1
        clearRailHandles()
    } else if (selectedType.value === 'bumper' && selectedBumperIndex.value !== -1) {
        // props.configSocket.emit('delete_bumper', { index: selectedBumperIndex.value })
        const newBumpers = [...(props.config.bumpers || [])]
        newBumpers.splice(selectedBumperIndex.value, 1)
        emit('update-bumper', newBumpers)
        
        selectedBumperIndex.value = -1
    }
}

const updateRailHandles = () => {
    clearRailHandles()
    if (!props.isEditMode || !props.config || !props.config.rails) return
    
    props.config.rails.forEach((rail, index) => {
        // Create handles for p1 and p2
        const p1 = mapToWorld(rail.p1.x, rail.p1.y)
        const p2 = mapToWorld(rail.p2.x, rail.p2.y)
        
        const createHandle = (pos: {x: number, y: number}, pointName: string) => {
            const geometry = new THREE.SphereGeometry(0.02, 16, 16)
            const material = new THREE.MeshBasicMaterial({ 
                color: index === selectedRailIndex.value ? 0xff0000 : 0x00ff00 
            })
            const mesh = new THREE.Mesh(geometry, material)
            mesh.position.set(pos.x, pos.y, 0.05) // Slightly above rail
            mesh.userData = { railIndex: index, point: pointName, isHandle: true }
            scene.add(mesh)
            railHandles.push(mesh)
        }
        
        createHandle(p1, 'p1')
        createHandle(p2, 'p2')
    })
}

const clearRailHandles = () => {
    railHandles.forEach(h => scene.remove(h))
    railHandles.length = 0
}

const mapToWorld = (x: number, y: number) => {
    // Map normalized (0-1) to world coordinates used in 3D scene
    // Based on mapX and mapY functions
    return {
        x: (x - 0.5) * 0.6,
        y: (0.5 - y) * 1.2
    }
}

const mapFromWorld = (wx: number, wy: number) => {
    // Inverse of mapToWorld
    return {
        x: (wx / 0.6) + 0.5,
        y: 0.5 - (wy / 1.2)
    }
}

// Drag & Drop logic removed (replaced by buttons)
const onDrop = () => {}

const onMouseDown = (event: MouseEvent) => {
    // console.log("Container MouseDown", event.button)
    // Resume Audio Context on first interaction
    SoundManager.resume()

    // Middle mouse button for camera panning
    if (event.button === 1) {
        // Only allow if controls are active
        if (!controlsActive.value) return
        
        event.preventDefault()
        isPanning.value = true
        panStart.set(event.clientX, event.clientY)
        cameraStartPos.copy(camera.position)
        return
    }
    
    if (!props.isEditMode) return
    
    updateMouse(event)
    raycaster.setFromCamera(mouse, camera)
    
    // Check handles first
    const intersects = raycaster.intersectObjects(railHandles)
    if (intersects.length > 0) {
        const hit = intersects[0].object
        selectedRailIndex.value = hit.userData.railIndex
        selectedType.value = 'rail'
        selectedBumperIndex.value = -1
        
        // Enable drag
        dragPoint.value = hit.userData.point
        isDragging.value = true
        
        // Setup drag plane
        dragPlane.setFromNormalAndCoplanarPoint(new THREE.Vector3(0, 0, 1), intersects[0].point)
        const target = new THREE.Vector3()
        raycaster.ray.intersectPlane(dragPlane, target)
        
        if (target) {
            const norm = mapFromWorld(target.x, target.y)
            dragStartPos.x = norm.x
            dragStartPos.y = norm.y
            
            const rail = props.config.rails[selectedRailIndex.value]
            dragState.initialP1 = { ...rail.p1 }
            dragState.initialP2 = { ...rail.p2 }
        }
        
        updateRailHandles() // To update selection color
        return
    }
    
    // Check rails (body selection)
    const bodyIntersects = raycaster.intersectObjects(railMeshes)
    if (bodyIntersects.length > 0) {
        const hit = bodyIntersects[0].object
        selectedRailIndex.value = hit.userData.railIndex
        selectedType.value = 'rail'
        selectedBumperIndex.value = -1
        
        // Enable drag
        dragPoint.value = 'body'
        isDragging.value = true
        
        // Setup drag plane
        // Setup drag plane
        dragPlane.setFromNormalAndCoplanarPoint(new THREE.Vector3(0, 0, 1), bodyIntersects[0].point)
        const target = new THREE.Vector3()
        raycaster.ray.intersectPlane(dragPlane, target)
        
        if (target) {
            const norm = mapFromWorld(target.x, target.y)
            dragStartPos.x = norm.x
            dragStartPos.y = norm.y
            
            const rail = props.config.rails[selectedRailIndex.value]
            dragState.initialP1 = { ...rail.p1 }
            dragState.initialP2 = { ...rail.p2 }
        }
        
        updateRailHandles()
        return
    }
    
    // Check bumpers (Group with children)
    const bumperIntersects = raycaster.intersectObjects(bumperMeshes, true)
    if (bumperIntersects.length > 0) {
        const hit = bumperIntersects[0].object
        // Hit object might be a child (dome/ring), check parent group for index
        let bIndex = hit.userData.bumperIndex
        if (bIndex === undefined && hit.parent && hit.parent.userData) {
            bIndex = hit.parent.userData.bumperIndex
        }
        
        if (bIndex !== undefined) {
            selectedBumperIndex.value = bIndex
            selectedType.value = 'bumper'
            selectedRailIndex.value = -1
            
            // Enable drag
            isDragging.value = true
            
            // Setup drag plane
            dragPlane.setFromNormalAndCoplanarPoint(new THREE.Vector3(0, 0, 1), bumperIntersects[0].point)
            const target = new THREE.Vector3()
            raycaster.ray.intersectPlane(dragPlane, target)
            
            if (target) {
                const norm = mapFromWorld(target.x, target.y)
                dragStartPos.x = norm.x
                dragStartPos.y = norm.y
                
                const bumper = props.config.bumpers[selectedBumperIndex.value]
                if (bumper) {
                    dragState.initialPos = { x: bumper.x, y: bumper.y }
                } else {
                    return // Abort if bumper data not found
                }
            }
            
            updateRailHandles() // Clear rail handles
        }
        return
    }
}

const onMouseMove = (event: MouseEvent) => {
    // Handle camera panning
    if (isPanning.value) {
        const deltaX = event.clientX - panStart.x
        const deltaY = event.clientY - panStart.y
        
        // Pan sensitivity (adjust as needed)
        const sensitivity = 0.005
        camera.position.x = cameraStartPos.x - deltaX * sensitivity
        camera.position.y = cameraStartPos.y + deltaY * sensitivity
        camera.lookAt(0, 0, 0)
        return
    }
    
    // Hover detection for OrbitControls locking
    if (props.isEditMode && !isDragging.value && !isPanning.value) {
        updateMouse(event)
        raycaster.setFromCamera(mouse, camera)
        
        const hitHandles = raycaster.intersectObjects(railHandles).length > 0
        const hitRails = raycaster.intersectObjects(railMeshes).length > 0
        const hitBumpers = raycaster.intersectObjects(bumperMeshes, true).length > 0
        
        const isHovering = hitHandles || hitRails || hitBumpers
        
        if (controls) {
            // Disable controls if hovering over an interactive object, otherwise follow activation state
            controls.enabled = !isHovering && controlsActive.value
        }
        
        // Optional: Change cursor
        document.body.style.cursor = isHovering ? 'pointer' : 'default'
    } else if (controls && controlsActive.value && !isDragging.value && !isPanning.value) {
         // Restore if we moved off object (implicit in above, but good for safety)
         controls.enabled = true
         document.body.style.cursor = 'default'
    }

    if (!isDragging.value) return
    
    updateMouse(event)
    raycaster.setFromCamera(mouse, camera)
    
    const target = new THREE.Vector3()
    raycaster.ray.intersectPlane(dragPlane, target)
    
    if (target) {
        // Convert world to normalized
        const normPos = mapFromWorld(target.x, target.y)
        
        // Update local config
        // Update local config
        if (selectedType.value === 'rail') {
            const rail = props.config.rails[selectedRailIndex.value]
            if (rail) {
                if (dragPoint.value === 'body' && dragState.initialP1 && dragState.initialP2) {
                    // Calculate delta
                    const dx = normPos.x - dragStartPos.x
                    const dy = normPos.y - dragStartPos.y
                    
                    // Apply to initial positions
                    rail.p1.x = dragState.initialP1.x + dx
                    rail.p1.y = dragState.initialP1.y + dy
                    rail.p2.x = dragState.initialP2.x + dx
                    rail.p2.y = dragState.initialP2.y + dy
                } else {
                    // Handle dragging
                    rail[dragPoint.value].x = normPos.x
                    rail[dragPoint.value].y = normPos.y
                }
                
                updateRailHandles()
                
                // Update 3D Rail Mesh Visualization
                // const railMesh = railMeshes[selectedRailIndex.value] // This might be unreliable if indices shifted? 
                // Better to use the stored reference if possible, but rail object in props.config is just data.
                // We stored user data in railMesh.userData.railIndex?
                // railMeshes should correspond to config.rails index IF no filtering happened.
                
                const railMesh = railMeshes[selectedRailIndex.value]
                if (railMesh) {
                     // Recalculate position/rotation similar to createTable
                     const nOffsetX = Number(props.config.rail_x_offset || 0)
                     const nOffsetY = Number(props.config.rail_y_offset || 0)
                     const lengthScale = Number(props.config.guide_length_scale || 1.0)
                     
                     // Use the UPDATED rail data directly
                     const r1x = rail.p1.x + nOffsetX
                     const r1y = rail.p1.y + nOffsetY
                     const r2x = rail.p2.x + nOffsetX
                     const r2y = rail.p2.y + nOffsetY

                     // Map 3D
                     let x1 = mapX(r1x), y1 = mapY(r1y)
                     const x2 = mapX(r2x), y2 = mapY(r2y)
                     
                     let dx = x2 - x1
                     let dy = y2 - y1
                     const length = Math.sqrt(dx * dx + dy * dy)
                     
                     if (length > 0 && Math.abs(lengthScale - 1.0) > 0.001) {
                         const scaledLen = length * lengthScale
                         const ux = dx / length, uy = dy / length
                         x1 = x2 - ux * scaledLen
                         y1 = y2 - uy * scaledLen
                     }
                     
                     // Update Mesh Position
                     railMesh.position.set((x1 + x2) / 2, (y1 + y2) / 2, railMesh.position.z)
                     railMesh.rotation.z = Math.atan2(y2 - y1, x2 - x1)
                     
                     // Update Geometry Length? 
                     // Cylinder height (length) is immutable without rebuilding geometry or scaling.
                     // Scaling Y axis matches length (Cylinder is Y-up by default, but we rotated it? 
                     // Wait, in createTable we did railGeo.rotateZ(Math.PI/2), so length is along X axis now?
                     // No, original cylinder is Y-up. rotateZ(90) makes it X-axis aligned.
                     // But we rotate the MESH by `angle`.
                     // Actually, usually we scale the mesh in the length axis.
                     
                     // Let's assume we need to scale Y (original length axis) or check implementation.
                     // In createTable: new CylinderGeometry(r, r, length). rotateZ(PI/2).
                     // So length is along X.
                     
                     // We can just Scale X to match new length / old length?
                     // But initial length is baked into geometry.
                     // Safer to just Update Scale?
                     // Initial length was passed to constructor.
                     // If we want to change length, we scaling the mesh on the axis of length.
                     // Since we rotated geometry Z 90deg, the "height" of cylinder (Y) is now aligned with X local.
                     
                     // BUT, scaling cylinder scales radius too if we are not careful? 
                     // No, scaling the Mesh scales the local axes.
                     // If Cylinder was created with length L_init.
                     // We rotated geometry so L is along X.
                     // We want new length L_new.
                     // scale.x = L_new / L_init.
                     
                     // Problem: We don't know L_init easily without storing it.
                     // BUT, we can just dispose and recreate geometry? Expensive for drag?
                     // Maybe just scale?
                     // Let's just update position/rotation for now. The length change might be noticeable looking distorted if we scale.
                     // But scaling X only affects length if aligned.
                     // Radius is Y and Z (after rotation).
                     
                     // Let's rely on Rebuild on MouseUp for perfect geometry.
                     // For dragging, just positioning the center/rotation is 90% of visual feedback.
                     // Scaling is bonus.
                     
                     // Actually, if we just move P1/P2, length changes.
                     // If we don't scale, the rail will look detached from points.
                     // Let's try to set scale.
                     // We need L_init. Geometry.parameters.height?
                     if ((railMesh.geometry as any).parameters) {
                         const initLen = (railMesh.geometry as any).parameters.height // Cylinder height is the length
                         railMesh.scale.x = length / initLen
                         // Note: rotateZ(PI/2) makes Y become X?
                         // Cylinder is created along Y. rotateZ(PI/2) moves Y to negative X?
                         // verify: Y (up) -> rotate Z 90 -> X (left).
                         // So X scale should control length.
                     }
                     
                     // Update 2D Rail
                     const rail2D = railMesh.userData.rail2D
                     if (rail2D) {
                        rail2D.position.set((x1 + x2) / 2, (y1 + y2) / 2, rail2D.position.z)
                        rail2D.rotation.z = Math.atan2(y2 - y1, x2 - x1)
                        // rail2D is PlaneGeometry(length, width). Created X-aligned I think?
                        // PlaneGeometry(width, height).
                        // In createTable: PlaneGeometry(length, rail2DWidth). Defaults to XY plane. 
                        // So X is length.
                        if (rail2D.geometry.parameters) {
                             const initLen2D = rail2D.geometry.parameters.width
                             rail2D.scale.x = length / initLen2D
                        }
                     }
                }
            }
        } else if (selectedType.value === 'bumper') {
            const bumper = props.config.bumpers[selectedBumperIndex.value]
            if (bumper && dragState.initialPos) {
                const dx = normPos.x - dragStartPos.x
                const dy = normPos.y - dragStartPos.y
                
                bumper.x = dragState.initialPos.x + dx
                bumper.y = dragState.initialPos.y + dy
                
                // Update mesh position
                const mesh = bumperMeshes[selectedBumperIndex.value]
                if (mesh) {
                    mesh.position.set(mapX(bumper.x), mapY(bumper.y), 0.025)
                }
            }
        }
    }
}

const onMouseUp = () => {
    // End camera panning
    if (isPanning.value) {
        isPanning.value = false
        // Don't persist camera pan - let it be a temporary adjustment
        // Camera will reset to config values on reload or view change
        return
    }
    
    if (isDragging.value) {
        isDragging.value = false
        // Emit update
        if (props.config) {
            if (selectedType.value === 'rail' && props.config.rails) {
                // props.configSocket.emit('update_rails', props.config.rails)
                const newRails = [...props.config.rails]
                emit('update-rail', newRails)
            } else if (selectedType.value === 'bumper' && props.config.bumpers) {
                // props.configSocket.emit('update_bumpers', props.config.bumpers)
                const newBumpers = [...props.config.bumpers]
                emit('update-bumper', newBumpers)
            }
        }
    }
}

// Zoom functionality
const onWheel = (event: WheelEvent) => {
    // If controls are NOT active, ignore wheel (require click to activate)
    if (!controlsActive.value) return

    // If controls are active (unlocked), let OrbitControls handle the zoom
    // Note: OrbitControls handles wheel automatically if enabled.
    // The previous manual logic was for when controls were locked or providing custom zoom.
    if (controls && controls.enabled) return
    if (!props.config || !camera) return

    // Calculate sensitivity based on current zoom or fixed
    const sensitivity = 0.001
    const delta = event.deltaY * sensitivity
    
    // Move camera along its viewing axis (Dolly)
    // Positive deltaY (scroll down) = zoom out = move back (+Z locally)
    camera.translateZ(delta * 5.0) // Scale factor for speed
    
    // Update local config zoom value to match roughly (inverse of distance?)
    // This is tricky because calculateZoom from distance depends on (0,0,0) lookat.
    // If we want to keep the UI slider somewhat useful, we can update it merely as a scalar.
    let currentZoom = physicsConfig.value.camera_zoom || 1.0
    let newZoom = currentZoom - delta
    newZoom = Math.max(0.2, Math.min(3.0, newZoom))
    
    physicsConfig.value.camera_zoom = newZoom
    
    // CRITICAL: Update lastCameraConfig to allow watcher to skip updateCamera()
    // This prevents the camera from snapping back to the calculated position
    if (lastCameraConfig.value) {
        lastCameraConfig.value.zoom = newZoom
    }
    
    props.configSocket.emit('update_physics_v2', { camera_zoom: newZoom })
}

const updateMouse = (event: MouseEvent) => {
    const rect = container.value.getBoundingClientRect()
    mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1
    mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1
}
const onStuckBall = (data) => {
    console.log("Stuck ball detected!", data)
    if (stuckBallDialog.value) return // Already showing
    
    stuckBallDialog.value = true
    stuckBallTimer.value = 20
    
    if (stuckBallInterval) clearInterval(stuckBallInterval)
    stuckBallInterval = setInterval(() => {
        stuckBallTimer.value--
        if (stuckBallTimer.value <= 0) {
            cancelRelaunch()
        }
    }, 1000)
}

const confirmRelaunch = () => {
    // console.log("Relaunch confirmed")
    props.socket.emit('relaunch_ball')
    clearInterval(stuckBallInterval)
    stuckBallDialog.value = false
}

const cancelRelaunch = () => {
    // console.log("Relaunch cancelled")
    clearInterval(stuckBallInterval)
    stuckBallDialog.value = false
}

// Watch for config changes from parent
// Watch moved to after createTable definition



const mapX = (x: number) => (x - 0.5) * 0.6
const mapY = (y: number) => (0.5 - y) * 1.2

const createTable = (config: PhysicsConfig | null = null) => {
  console.log('[createTable] Called with config:', config ? 'present' : 'null')
  console.log('[createTable] Current ball count:', balls.length)

  // console.log('Creating Table with config:', config)
  if (tableGroup) scene.remove(tableGroup)
  // Remove old table if it exists
  if (tableGroup) {
    scene.remove(tableGroup)
    // Dispose of geometries and materials to free memory
    tableGroup.traverse((obj) => {
      if ('geometry' in obj && obj.geometry) (obj.geometry as THREE.BufferGeometry).dispose()
      if ('material' in obj && obj.material) {
        if (Array.isArray(obj.material)) {
          obj.material.forEach(mat => (mat as THREE.Material).dispose())
        } else {
          (obj.material as THREE.Material).dispose()
        }
      }
    })
  }
  
  tableGroup = new THREE.Group()
  scene.add(tableGroup)
  railMeshes.length = 0
  bumperMeshes.length = 0
  
  // Clear existing balls and flippers so they are recreated in the new group
  balls = []
  
  // Clear ball effects arrays
  ballGlows = []
  ballTrails = []
  ballParticles = []

  // Initialize Texture Loader
  const textureLoader = new THREE.TextureLoader()

  // Initialize ball resources - Chrome finish with Texture
  ballGeo = new THREE.SphereGeometry(0.016, 32, 32)
  const ballTex = textureLoader.load('/textures/ball_texture.png')
  ballTex.colorSpace = THREE.SRGBColorSpace
  
  ballMat = new THREE.MeshStandardMaterial({ 
    map: ballTex,
    color: 0xeeeeee, 
    metalness: 0.8, // High metalness for shiny look
    roughness: 0.3, // Texture provides the detail
    emissive: 0x222222, 
    emissiveIntensity: 0.1
  })
  flippers = { left: null, right: null, upper: [], dropTargets: [], bumpers: [] }
  zoneMeshes = [] // Clear zone meshes array

// Floor - Brighter playfield with Texture Support
  const floorGeo = new THREE.PlaneGeometry(0.6, 1.2)
  
  // Determine layout ID for texture lookup
  let layoutId = null
  if (config) {
      if (config.current_layout_id) {
          layoutId = config.current_layout_id
      } else if (config.name) {
          layoutId = config.name.toLowerCase().replace(/ /g, '_')
      }
  }


  let floorMat
  
  // Try to load texture dynamically - no hardcoded list
  if (layoutId) {
      const texturePath = `/textures/${layoutId}.png`
      
      // Attempt to load texture with error handling
      const texture = textureLoader.load(
          texturePath,
          // onLoad callback
          () => {
              // Texture loaded successfully
              console.log(`Loaded texture for layout: ${layoutId}`)
          },
          // onProgress callback
          undefined,
          // onError callback
          () => {
              // Texture not found, use default material
              console.log(`No texture found for layout: ${layoutId}, using default`)
              if (floor && floor.material) {
                  floor.material.dispose()
                  floor.material = new THREE.MeshStandardMaterial({
                      color: 0x2a2a44,
                      roughness: 0.4,
                      metalness: 0.6,
                      emissive: 0x1a1a2e,
                      emissiveIntensity: 0.15
                  })
              }
          }
      )
      texture.colorSpace = THREE.SRGBColorSpace
      
      floorMat = new THREE.MeshStandardMaterial({
        map: texture,
        roughness: 0.4,
        metalness: 0.3,
        emissive: 0x1a1a2e,
        emissiveIntensity: 0.05
      })
  } else {
      // No layout ID, use default
      floorMat = new THREE.MeshStandardMaterial({
        color: 0x2a2a44,
        roughness: 0.4,
        metalness: 0.6,
        emissive: 0x1a1a2e,
        emissiveIntensity: 0.15
      })
  }

  const floor = new THREE.Mesh(floorGeo, floorMat)
  floor.receiveShadow = true
  tableGroup.add(floor)

  // Walls - Brushed Metal Texture
  // Walls - Dynamic or Default Brushed Metal
  let wallTexturePath = '/textures/wall_texture.png'
  if (layoutId === 'lisa_frank') {
      wallTexturePath = '/textures/lisa_frank_wall.png'
  }
  const wallTexture = textureLoader.load(wallTexturePath)
  wallTexture.colorSpace = THREE.SRGBColorSpace
  wallTexture.wrapS = THREE.RepeatWrapping
  wallTexture.wrapT = THREE.RepeatWrapping
  wallTexture.repeat.set(1, 4)

  const wallMat = new THREE.MeshStandardMaterial({
    map: wallTexture,
    color: 0xaaaaaa,
    roughness: 0.4,
    metalness: 0.8,
    emissive: 0x111111,
    emissiveIntensity: 0.1
  })
  const wallHeight = 0.1
  
  // Left Wall
  const w1 = new THREE.Mesh(new THREE.BoxGeometry(0.02, 1.2, wallHeight), wallMat)
  w1.position.set(-0.31, 0, wallHeight/2)
  tableGroup.add(w1)
  
  // Right Wall
  const w2 = new THREE.Mesh(new THREE.BoxGeometry(0.02, 1.2, wallHeight), wallMat)
  w2.position.set(0.31, 0, wallHeight/2)
  tableGroup.add(w2)
  
  // Top Wall
  const w3 = new THREE.Mesh(new THREE.BoxGeometry(0.64, 0.02, wallHeight), wallMat)
  w3.position.set(0, 0.61, wallHeight/2)
  tableGroup.add(w3)

  // --- Dynamic Features from Config ---
  if (config) {
    // Top Arch (Visual) - Enhanced chrome finish
    const archShape = new THREE.Shape()
    archShape.moveTo(mapX(1.0), mapY(0.15))
    archShape.lineTo(mapX(0.6), mapY(0.0))
    archShape.lineTo(mapX(1.0), mapY(0.0))
    archShape.lineTo(mapX(1.0), mapY(0.15))
    
    const archGeo = new THREE.ExtrudeGeometry(archShape, { depth: 0.05, bevelEnabled: false })
    const archMat = new THREE.MeshStandardMaterial({
      color: 0x999999,
      roughness: 0.2,
      metalness: 0.9
    })
    const arch = new THREE.Mesh(archGeo, archMat)
    tableGroup.add(arch)

    // Triangle Guide - Top-Left - Enhanced chrome finish
    const leftGuideShape = new THREE.Shape()
    leftGuideShape.moveTo(mapX(0.0), mapY(0.15))
    leftGuideShape.lineTo(mapX(0.4), mapY(0.0))
    leftGuideShape.lineTo(mapX(0.0), mapY(0.0))
    leftGuideShape.lineTo(mapX(0.0), mapY(0.15))
    
    const leftGuideGeo = new THREE.ExtrudeGeometry(leftGuideShape, { depth: 0.05, bevelEnabled: false })
    const leftGuideMat = new THREE.MeshStandardMaterial({
      color: 0x999999,
      roughness: 0.2,
      metalness: 0.9
    })
    const leftGuide = new THREE.Mesh(leftGuideGeo, leftGuideMat)
    tableGroup.add(leftGuide)

    // Bumpers - Close Encounters UFO style (larger and more visible)
    if (config.bumpers) {
      // UFO dome geometry - larger and flatter
      const domeGeo = new THREE.SphereGeometry(0.035, 32, 16, 0, Math.PI * 2, 0, Math.PI / 2.5)
      // UFO base ring geometry - thicker and more visible
      const ringGeo = new THREE.TorusGeometry(0.035, 0.008, 16, 32)
      // Larger light spheres
      const lightGeo = new THREE.SphereGeometry(0.006, 16, 16)
      // 2D representation for top-down view - bright circle on the floor
      const bumper2DGeo = new THREE.CircleGeometry(0.04, 32)

      config.bumpers.forEach((b, i) => {
         // Create group for UFO bumper
         const bumperGroup = new THREE.Group()

         // Main dome - brighter metallic silver with texture
         const bumperTexture = textureLoader.load('/textures/bumper_dome.png')
         bumperTexture.colorSpace = THREE.SRGBColorSpace
         
         const domeMat = new THREE.MeshStandardMaterial({
           map: bumperTexture,
           color: 0xcccccc, // Brighter silver
           roughness: 0.15,
           metalness: 0.95,
           emissive: 0x666666,
           emissiveIntensity: 0.4
         })
         const domeMesh = new THREE.Mesh(domeGeo, domeMat)
         domeMesh.rotation.x = Math.PI / 2
         domeMesh.position.z = 0.012
         domeMesh.castShadow = true
         bumperGroup.add(domeMesh)

         // Ring base around dome - more prominent with texture
         const ringTexture = textureLoader.load('/textures/bumper_base.png')
         ringTexture.colorSpace = THREE.SRGBColorSpace
         
         const ringMat = new THREE.MeshStandardMaterial({
           map: ringTexture,
           color: 0x888888, // Lighter gray
           roughness: 0.3,
           metalness: 0.8,
           emissive: 0x222222,
           emissiveIntensity: 0.2
         })
         const ringMesh = new THREE.Mesh(ringGeo, ringMat)
         ringMesh.rotation.x = Math.PI / 2
         ringMesh.position.z = 0.005
         ringMesh.castShadow = true
         bumperGroup.add(ringMesh)

         // Colored lights around the UFO - larger and brighter
         const lightColors = [0xff0000, 0x00ff00, 0x0000ff, 0xffff00, 0xff00ff]
         const numLights = 5
         const lights = []

         for (let j = 0; j < numLights; j++) {
           const angle = (j / numLights) * Math.PI * 2
           const radius = 0.028

           const lightMat = new THREE.MeshStandardMaterial({
             color: lightColors[j],
             roughness: 0.1,
             metalness: 0.3,
             emissive: lightColors[j],
             emissiveIntensity: 1.2
           })

           const lightMesh = new THREE.Mesh(lightGeo, lightMat)
           lightMesh.position.x = Math.cos(angle) * radius
           lightMesh.position.y = Math.sin(angle) * radius
           lightMesh.position.z = 0.008
           bumperGroup.add(lightMesh)
           lights.push(lightMesh)
         }

         // Add 2D representation for top-down view (flat circle on floor)
         const bumper2DMat = new THREE.MeshBasicMaterial({
           color: 0xffff00,
           side: THREE.DoubleSide
         })
         const bumper2D = new THREE.Mesh(bumper2DGeo, bumper2DMat)
         bumper2D.position.z = 0.001 // Just above floor
         bumperGroup.add(bumper2D)

         bumperGroup.position.set(mapX(b.x), mapY(b.y), 0)
         bumperGroup.userData = {
           bumperIndex: i,
           type: 'bumper',
           domeMesh,
           ringMesh,
           lights,
           lightColors,
           isActive: false,
           bumper2D, // Store reference for updates
           originalPos: new THREE.Vector3(mapX(b.x), mapY(b.y), 0) // Store original position for shake restore
         }

         // Health Bar
         const barGroup = new THREE.Group()
         barGroup.position.set(0, 0.06, 0.05)
         const bgGeo = new THREE.PlaneGeometry(0.06, 0.008)
         const bgMat = new THREE.MeshBasicMaterial({ color: 0x550000 })
         const bgMesh = new THREE.Mesh(bgGeo, bgMat)
         barGroup.add(bgMesh)
         const fgGeo = new THREE.PlaneGeometry(0.06, 0.008)
         fgGeo.translate(0.03, 0, 0)
         const fgMat = new THREE.MeshBasicMaterial({ color: 0x00ff00 })
         const fgMesh = new THREE.Mesh(fgGeo, fgMat)
         fgMesh.position.x = -0.03
         fgMesh.position.z = 0.001
         barGroup.add(fgMesh)
         bumperGroup.add(barGroup)
         bumperGroup.userData.healthBar = fgMesh
         tableGroup.add(bumperGroup)
         flippers.bumpers.push(bumperGroup)
         bumperMeshes.push(bumperGroup)
      })
    }


    // --- Mothership (Boss) ---
    // Persistent group referenced by updateMothership, created once.
    const mothershipGroup = new THREE.Group()
    mothershipGroup.visible = false // Hidden by default
    
    // Rotator container for the ship body (to face flippers)
    const shipRotator = new THREE.Group()
    shipRotator.rotation.z = Math.PI // Rotate 180 degrees so top faces flippers (South)
    mothershipGroup.add(shipRotator)
    
    // 1. Main Saucer Body (Metallic Grey with Hull Texture)
    // Flattened sphere for top and bottom
    const hullTexture = textureLoader.load('/textures/alien_hull.png')
    hullTexture.colorSpace = THREE.SRGBColorSpace
    hullTexture.wrapS = THREE.RepeatWrapping
    hullTexture.wrapT = THREE.RepeatWrapping
    hullTexture.repeat.set(4, 2)
    
    const saucerGeo = new THREE.SphereGeometry(0.15, 32, 16)
    saucerGeo.scale(1, 0.3, 1) // Flatten Y
    const saucerMat = new THREE.MeshStandardMaterial({
        map: hullTexture,
        color: 0xaaaaaa, // Tint
        roughness: 0.4,
        metalness: 0.7,
        envMapIntensity: 1.0,
        bumpMap: hullTexture,
        bumpScale: 0.02
    })
    const saucer = new THREE.Mesh(saucerGeo, saucerMat)
    shipRotator.add(saucer)

    // 2. Glowing Engine Ring (Center)
    const ringGeo = new THREE.TorusGeometry(0.14, 0.015, 16, 64)
    ringGeo.rotateX(Math.PI / 2)
    const ringMat = new THREE.MeshBasicMaterial({ 
        color: 0x00ffff, // Cyan Glow
        side: THREE.DoubleSide
    })
    const ring = new THREE.Mesh(ringGeo, ringMat)
    shipRotator.add(ring)
    mothershipGroup.userData.ring = ring // For animation

    // 3. Cockpit Dome (Glass)
    const domeGeo = new THREE.SphereGeometry(0.06, 32, 16, 0, Math.PI * 2, 0, Math.PI / 2)
    const domeMat = new THREE.MeshStandardMaterial({
        color: 0xff00ff, // Magenta Glass
        roughness: 0.0,
        metalness: 0.1,
        transparent: true,
        opacity: 0.8,
        emissive: 0x440044,
        emissiveIntensity: 0.5
    })
    const dome = new THREE.Mesh(domeGeo, domeMat)
    dome.position.y = 0.03
    shipRotator.add(dome)
    mothershipGroup.userData.dome = dome // For animation

    // 4. Rotating Lights (Underneath)
    const lightsGroup = new THREE.Group()
    const lightGeo = new THREE.SphereGeometry(0.015, 8, 8)
    const lightMat = new THREE.MeshBasicMaterial({ color: 0xffaa00 })
    
    for (let l = 0; l < 8; l++) {
        const angle = (l / 8) * Math.PI * 2
        const rad = 0.1
        const lm = new THREE.Mesh(lightGeo, lightMat)
        lm.position.set(Math.cos(angle) * rad, -0.02, Math.sin(angle) * rad)
        lightsGroup.add(lm)
    }
    shipRotator.add(lightsGroup)
    mothershipGroup.userData.lightsGroup = lightsGroup
    
    // 5. Spinning Police Light (Top)
    // Red Cylinder Housing - Use 6 segments (Hex prism) for visibility of rotation
    const policeLightGeo = new THREE.CylinderGeometry(0.02, 0.02, 0.04, 6)
    const policeLightMat = new THREE.MeshStandardMaterial({
        color: 0xff0000,
        emissive: 0xff0000,
        emissiveIntensity: 0.6,
        metalness: 0.5,
        roughness: 0.2,
        flatShading: true // Make facets visible
    })
    const policeLight = new THREE.Mesh(policeLightGeo, policeLightMat)
    policeLight.position.y = 0.08 // Top of dome (dome y=0.03 + height)
    shipRotator.add(policeLight)
    
    // Add Internal "Reflector" (White box) to make spin obvious
    const reflector = new THREE.Mesh(
        new THREE.BoxGeometry(0.03, 0.03, 0.005), 
        new THREE.MeshBasicMaterial({ color: 0xffffff })
    )
    reflector.position.x = 0.01 // Offset to one side
    policeLight.add(reflector)

    // Second Reflector (Opposite side)
    const reflector2 = new THREE.Mesh(
        new THREE.BoxGeometry(0.03, 0.03, 0.005), 
        new THREE.MeshBasicMaterial({ color: 0xffffff })
    )
    reflector2.position.x = -0.01 // Opposite offset
    policeLight.add(reflector2)
    
    // Rotating Beacon 1 (SpotLight)
    const beacon = new THREE.SpotLight(0xff0000, 20.0, 10.0, Math.PI / 3, 0.5, 1)
    beacon.position.set(0, 0, 0) 
    
    const beaconTarget = new THREE.Object3D()
    beaconTarget.position.set(1, 0, 0) // Point outwards
    policeLight.add(beaconTarget)
    beacon.target = beaconTarget
    policeLight.add(beacon)

    // Rotating Beacon 2 (Opposite)
    const beacon2 = new THREE.SpotLight(0xff0000, 20.0, 10.0, Math.PI / 3, 0.5, 1)
    beacon2.position.set(0, 0, 0)
    
    const beaconTarget2 = new THREE.Object3D()
    beaconTarget2.position.set(-1, 0, 0) // Point opposite
    policeLight.add(beaconTarget2)
    beacon2.target = beaconTarget2
    policeLight.add(beacon2)

    mothershipGroup.userData.policeLight = policeLight
    
    // Health Bar Container (Keep existing logic)
    // Health Bar Container (Keep existing logic)
    const hbContainer = new THREE.Group()
    // Move to Upper Right: (+X, +Y) relative to ship center
    hbContainer.position.set(0.18, 0.18, 0.05) 
    mothershipGroup.add(hbContainer)
    
    // Health Bar Back
    const hbBack = new THREE.Mesh(
        new THREE.BoxGeometry(0.2, 0.03, 0.015), 
        new THREE.MeshStandardMaterial({ 
            color: 0x333333,
            roughness: 0.5,
            metalness: 0.5 
        })
    )
    hbContainer.add(hbBack)
    
    // Health Bar Fill
    const hbFill = new THREE.Mesh(
        new THREE.BoxGeometry(0.2, 0.03, 0.02), 
        new THREE.MeshStandardMaterial({ 
            color: 0x00ff00,
            emissive: 0x00aa00,
            emissiveIntensity: 0.5,
            roughness: 0.2,
            metalness: 0.8
        })
    )
    hbFill.position.z = 0.005 // Slightly in front
    // Easier: offset mesh so x=0 is left edge.
    hbFill.geometry.translate(0.1, 0, 0) // Pivot left
    hbFill.position.x = -0.1
    
    hbContainer.add(hbFill)
    mothershipGroup.userData.fillMesh = hbFill
    
    tableGroup.add(mothershipGroup)
    flippers.mothership = mothershipGroup // Store reference

    // Drop Targets - Colorful Rectangles
    if (config.drop_targets) {
      flippers.dropTargets = [] // Initialize array

      // Rainbow Colors
      const dropTargetColors = [0xff0000, 0xffaa00, 0xffff00, 0x00ff00, 0x00ffff, 0x0000ff, 0xff00ff]

      // 2D representation for top-down view
      // We can reuse the same geometry logic for 2D if we just scale Z to flat

      config.drop_targets.forEach((t, idx) => {
        const w = t.width * 0.6
        const h = 0.04 // Height above table (standard target height)
        const d = t.height * 1.2 // Thickness (depth in Y)
        
        // Cycle colors
        const targetColor = dropTargetColors[idx % dropTargetColors.length]

        // Load drop target texture
        const dropTargetTexture = textureLoader.load('/textures/drop_target.png')
        dropTargetTexture.colorSpace = THREE.SRGBColorSpace

        const targetMat = new THREE.MeshStandardMaterial({
          map: dropTargetTexture,
          color: targetColor,
          roughness: 0.2,
          metalness: 0.6,
          emissive: targetColor,
          emissiveIntensity: 0.4
        })

        // Simple Box for Drop Target
        const geometry = new THREE.BoxGeometry(w, d, h)
        // Center of BoxGeometry is (0,0,0).
        // If we want it to sit ON the table (Z=0), we shift it up by h/2
        // BUT: physics bodies are 2D. 3D representation is centered at body center.
        // Body center is (t.x, t.y).
        
        const target = new THREE.Mesh(geometry, targetMat)
        
        // Position: mapX/mapY converts normalized coords to world coords.
        // Physics engine treats t.x/t.y as Top-Left corner, but Three.js positions Mesh at Center.
        // We must offset by half dimensions to align visual with physics.
        target.position.set(mapX(t.x + t.width/2), mapY(t.y + t.height/2), h/2)
        target.castShadow = true
        target.receiveShadow = true

        // Add 2D representation for top-down view
        const target2DGeo = new THREE.PlaneGeometry(w, d)
        const target2DMat = new THREE.MeshBasicMaterial({
          color: targetColor,
          side: THREE.DoubleSide
        })
        const target2D = new THREE.Mesh(target2DGeo, target2DMat)
        target2D.position.set(mapX(t.x + t.width/2), mapY(t.y + t.height/2), 0.001) // Just above floor
        // Rotate to match "depth" (Y-axis) alignment? No, PlaneGeometry default is XY plane.
        // In top down (Z-up), this lies flat on XY plane? 
        // No, PlaneGeometry is in XY plane. We want it flat on floor (XY plane). Yes.
        
        // Wait, standard PlaneGeometry is XY. If we look down Z, it faces us.
        // Correct.
        
        tableGroup.add(target)
        tableGroup.add(target2D)
        flippers.dropTargets.push(target)
      })
    }

    // Rails - Chrome-finished guide tubes
    if (config.rails) {
      const railRadius = 0.008 // Thickness of rail tube
      const railHeight = 0.04 // Height above playfield
      const rail2DWidth = 0.016 // Width for 2D representation (2x radius for visibility)

      // Rail material - chrome finish
      const railMat = new THREE.MeshStandardMaterial({
        color: 0xcccccc,
        roughness: 0.2,
        metalness: 0.9,
        emissive: 0x444444,
        emissiveIntensity: 0.2
      })

      // 2D rail material for top-down view
      const rail2DMat = new THREE.MeshBasicMaterial({
        color: 0xcccccc,
        side: THREE.DoubleSide
      })

      config.rails.forEach((rail, index) => {
        const normOffsetX = Number(config.rail_x_offset || 0)
        const normOffsetY = Number(config.rail_y_offset || 0)
        const lengthScale = Number(config.guide_length_scale || 1.0)
        
        // Apply global offsets to raw coordinates
        const r1x = rail.p1.x + normOffsetX
        const r1y = rail.p1.y + normOffsetY
        const r2x = rail.p2.x + normOffsetX
        const r2y = rail.p2.y + normOffsetY
        
        // Calculate start and end positions in 3D space
        let x1 = mapX(r1x)
        let y1 = mapY(r1y)
        const x2 = mapX(r2x)
        const y2 = mapY(r2y)

        // Calculate distance between points
        let dx = x2 - x1
        let dy = y2 - y1
        const length = Math.sqrt(dx * dx + dy * dy)
        
        // Apply Length Scale (P1 moves towards P2)
        if (length > 0 && Math.abs(lengthScale - 1.0) > 0.001) {
             const scaledLen = length * lengthScale
             const ux = dx / length
             const uy = dy / length
             
             x1 = x2 - ux * scaledLen
             y1 = y2 - uy * scaledLen
             
             // Recalc dx, dy
             dx = x2 - x1
             dy = y2 - y1
        }

        // Create 3D cylinder geometry for the rail
        const railGeo = new THREE.CylinderGeometry(railRadius, railRadius, length, 16)

        // Rotate cylinder to be horizontal (cylinders default to vertical along Y-axis)
        railGeo.rotateZ(Math.PI / 2)

        const railMesh = new THREE.Mesh(railGeo, railMat)

        // Position at midpoint between p1 and p2
        railMesh.position.set(
          (x1 + x2) / 2,
          (y1 + y2) / 2,
          railHeight / 2
        )

        // Rotate to align with the rail direction
        const angle = Math.atan2(dy, dx)
        railMesh.rotation.z = angle

        railMesh.castShadow = true
        railMesh.receiveShadow = true

        // Create 2D representation for top-down view (flat rectangle on floor)
        const rail2DGeo = new THREE.PlaneGeometry(length, rail2DWidth)
        const rail2D = new THREE.Mesh(rail2DGeo, rail2DMat)

        // Position at same location as 3D rail but on the floor
        rail2D.position.set(
          (x1 + x2) / 2,
          (y1 + y2) / 2,
          0.001 // Just above floor to prevent z-fighting
        )

        // Rotate to align with rail direction
        rail2D.rotation.z = angle

        // Initially hidden (will be shown in 2D mode)
        rail2D.visible = false

        // Store rail metadata for editing
        railMesh.userData = {
          railIndex: index,
          type: 'rail',
          p1: rail.p1,
          p2: rail.p2,
          rail2D: rail2D  // Store reference to 2D representation
        }

        rail2D.userData = {
          railIndex: index,
          type: 'rail',
          p1: rail.p1,
          p2: rail.p2,
          rail3D: railMesh  // Store reference to 3D representation
        }

        tableGroup.add(railMesh)
        tableGroup.add(rail2D)
        railMeshes.push(railMesh)
      })
    }
  }
  // Flippers
  // Flippers
  // Use config.flipper_length (fraction of width) * table width (0.6)
  // Default flipper_length in physics is 0.2. 0.2 * 0.6 = 0.12 (matches previous hardcoded value)
  const flipperLength = (config && config.flipper_length) ? config.flipper_length * 0.6 : 0.12
  const flipperWidth = (config && config.flipper_width) ? config.flipper_width * 0.6 : 0.02
  const flipperTipWidth = (config && config.flipper_tip_width !== undefined) ? config.flipper_tip_width * 0.6 : flipperWidth
  const flipperHeight = 0.04
  
  // Create rounded flipper shape (Stadium/Capsule 2D shape with taper)
  const flipperShape = new THREE.Shape()
  const baseRadius = flipperWidth / 2
  const tipRadius = flipperTipWidth / 2
  
  // Calculate the length of the straight segment between the two semicircles
  const segLen = flipperLength - baseRadius - tipRadius
  
  if (segLen < 0) {
    // If length is too short for both radii, just create a simple capsule
    console.warn('Flipper length too short for given widths, using simple capsule')
    const avgRadius = (baseRadius + tipRadius) / 2
    const simpleLen = flipperLength - avgRadius * 2

    flipperShape.moveTo(0, -avgRadius)
    flipperShape.lineTo(simpleLen, -avgRadius)
    flipperShape.absarc(simpleLen, 0, avgRadius, -Math.PI/2, Math.PI/2, false)
    flipperShape.lineTo(0, avgRadius)
    flipperShape.absarc(0, 0, avgRadius, Math.PI/2, -Math.PI/2, false)
  } else {
    // Create tapered flipper shape
    // Start at bottom of base (pivot) semicircle
    flipperShape.moveTo(0, -baseRadius)

    // Line from base bottom to tip bottom (tapered)
    flipperShape.lineTo(baseRadius + segLen, -tipRadius)

    // Tip semicircle (right end) - arc around center at (baseRadius + segLen, 0)
    flipperShape.absarc(baseRadius + segLen, 0, tipRadius, -Math.PI/2, Math.PI/2, false)

    // Line from tip top back to base top (tapered)
    flipperShape.lineTo(0, baseRadius)

    // Base semicircle (left end/pivot) - arc around center at (0, 0)
    flipperShape.absarc(0, 0, baseRadius, Math.PI/2, -Math.PI/2, false)
  }

  const flipperGeo = new THREE.ExtrudeGeometry(flipperShape, {
    depth: flipperHeight,
    bevelEnabled: false
  })
  // Center the geometry vertically so z=0 is the middle? 
  // No, currently boxes are placed at z=0.02 (center) with height 0.04.
  // ExtrudeGeometry creates mesh from z=0 to z=depth.
  // We want it centered on Z axis relative to pivot?
  // Pivot is at z=0.02.
  // If we add mesh to pivot, and mesh is 0..0.04, it will be 0.02..0.06.
  // We want -0.02..0.02 relative to pivot.
  flipperGeo.translate(0, 0, -flipperHeight/2)

  // Standard Stern-style Red Rubber Flipper
  const flipperTexture = textureLoader.load('/textures/flipper_texture.png')
  flipperTexture.colorSpace = THREE.SRGBColorSpace
  flipperTexture.wrapS = THREE.RepeatWrapping
  flipperTexture.wrapT = THREE.RepeatWrapping
  flipperTexture.repeat.set(1, 1)

  const flipperMat = new THREE.MeshStandardMaterial({
    map: flipperTexture,
    // color: 0xffffff, // Use texture color directly
    roughness: 0.8, // Rubber is rough/matte
    metalness: 0.1, // Rubber is not metallic
    emissive: 0x110000,
    emissiveIntensity: 0.1
  })

  // Left Flipper
  const leftPivot = new THREE.Group()
  // Default fallback if config missing
  let lx = -0.26
  let ly = -0.48
  
  if (config && config.left_flipper_pos_x !== undefined) {
      // Physics pivot is at (x_min, y_max)
      // Apply flipper_spacing (additive for left flipper to move right)
      const spacing = config.flipper_spacing || 0
      lx = mapX(config.left_flipper_pos_x + spacing)
      ly = mapY(config.left_flipper_pos_y_max)
  }
  
  leftPivot.position.set(lx, ly, 0.02)
  tableGroup.add(leftPivot)
  
  const leftMesh = new THREE.Mesh(flipperGeo, flipperMat)
  leftMesh.position.set(-baseRadius, 0, 0) 
  leftPivot.add(leftMesh)
  flippers.left = leftPivot

  // Right Flipper - Clone geometry to avoid sharing
  const rightFlipperGeo = flipperGeo.clone()

  const rightPivot = new THREE.Group()
  // Default fallback
  let rx = 0.26
  let ry = -0.48
  
  if (config && config.right_flipper_pos_x_max !== undefined) {
      // Physics pivot is at (x_max, y_max)
      // Apply flipper_spacing (subtractive for right flipper to move left)
      const spacing = config.flipper_spacing || 0
      rx = mapX(config.right_flipper_pos_x_max - spacing)
      ry = mapY(config.right_flipper_pos_y_max)
  }
  
  rightPivot.position.set(rx, ry, 0.02)
  tableGroup.add(rightPivot)
  
  const rightMesh = new THREE.Mesh(rightFlipperGeo, flipperMat)
  // Right flipper mesh extends to the LEFT from pivot?
  // In physics.py: p2 = (-length, 0).
  // In Three.js here: we set position to (flipperLength / 2, 0, 0).
  // If pivot is at Right side, and we want it to extend Left...
  // The mesh is a box centered at its local origin.
  // If we want the pivot to be at one end...
  // Current code: leftMesh.position.set(flipperLength / 2, 0, 0) -> Pivot is at Left end, mesh extends Right. Correct.
  
  // For Right Flipper:
  // Physics: Pivot at Right end, extends Left.
  // Visual: rightMesh.position.set(flipperLength / 2, 0, 0).
  // This means Pivot is at Left end of the mesh, mesh extends Right.
  // But we want Pivot at Right end, mesh extends Left.
  // So we should set position to (-flipperLength / 2, 0, 0)?
  // Let's check existing code.
  // Existing: rightMesh.position.set(flipperLength / 2, 0, 0)
  // And rotation logic: flippers.right.rotation.z = THREE.MathUtils.degToRad(180 - flipperData.right_angle)
  // If angle is 0 (Resting is -30).
  // If we rotate by 180, it points Left.
  // So if mesh extends Right (default), rotating 180 makes it extend Left.
  // So the mesh setup is actually symmetric (both extend Right from pivot), and rotation handles the direction.
  // So we keep the mesh position as is.
  
  rightMesh.position.set(-baseRadius, 0, 0)
  rightPivot.add(rightMesh)
  flippers.right = rightPivot
  


  // Helper to create plunger with lips
  const createPlungerMesh = (color) => {
    const group = new THREE.Group()
    const mat = new THREE.MeshStandardMaterial({ color })
    
    // Base
    // Physics: width ~50px (0.075), height 40px (0.06)
    // Visual: width 0.08, length 0.04, height 0.04
    const baseGeo = new THREE.BoxGeometry(0.08, 0.04, 0.04)
    const base = new THREE.Mesh(baseGeo, mat)
    group.add(base)
    
    // Lips (Side guides)
    // Physics: width 10px (0.015), height 20px (0.03) above base
    // Position: +/- width/2
    const lipGeo = new THREE.BoxGeometry(0.015, 0.04, 0.03)
    
    const leftLip = new THREE.Mesh(lipGeo, mat)
    leftLip.position.set(-0.04 + 0.0075, 0, 0.035) // On top of base edge
    group.add(leftLip)
    
    const rightLip = new THREE.Mesh(lipGeo, mat)
    rightLip.position.set(0.04 - 0.0075, 0, 0.035)
    group.add(rightLip)
    
    return group
  }

  // Plunger (Right)
  const plunger = createPlungerMesh(0x888888)
  // Initial position (will be updated)
  plunger.position.set(mapX(0.925), mapY(0.95), 0.02)
  
  // Rotate based on launch_angle
  if (config && config.launch_angle) {
    // Physics: +angle = Right. Three.js: -rotation = Right (Clockwise)
    plunger.rotation.z = THREE.MathUtils.degToRad(-config.launch_angle)
  }
  
  tableGroup.add(plunger)
  flippers.plunger = plunger

  // Left Plunger (Kickback)
  const leftPlunger = createPlungerMesh(0x888888)
  leftPlunger.position.set(mapX(0.075), mapY(0.95), 0.02)
  tableGroup.add(leftPlunger)
  flippers.leftPlunger = leftPlunger
}

// Ball


const updateBalls = (ballData: any[]) => {
  if (!ballData) return
  
  // Get current combo for visual effects
  const combo = props.stats?.combo_count || 0

  // Track if ball count changed
  // const previousBallCount = balls.length
  // const newBallCount = ballData.length


  // Create new balls if needed
  while (balls.length < ballData.length) {
    const ball = new THREE.Mesh(ballGeo, ballMat.clone()) 
    ball.castShadow = true

    // OPTIMIZATION: Use Sprite instead of PointLight for glow
    // Real-time PointLights are extremely expensive in Forward Rendering (fills screen with light calculations)
    // A Sprite (billboard) is basically free and looks 90% the same for "glow"
    const spriteMat = new THREE.SpriteMaterial({ 
        map: getGlowTexture(), 
        color: 0xffffff, 
        transparent: true, 
        opacity: 0.0,
        blending: THREE.AdditiveBlending,
        depthWrite: false
    })
    const glowSprite = new THREE.Sprite(spriteMat)
    glowSprite.scale.set(0.15, 0.15, 1.0) // 2x ball size roughly
    ball.add(glowSprite)
    ballGlows.push(glowSprite)

    // Particle System Group (World Space)
    const pGroup = new THREE.Group()
    pGroup.userData = { 
        pool: [],
        lastPos: new THREE.Vector3(),
        velocity: new THREE.Vector3()
    }
    tableGroup.add(pGroup)
    ballParticles.push(pGroup) // Reuse ballParticles array for the new system

    tableGroup.add(ball)
    balls.push(ball)
  }
  
  // Remove excess balls
  while (balls.length > ballData.length) {
    const ball = balls.pop()
    ballGlows.pop()
    const pGroup = ballParticles.pop()
    tableGroup.remove(pGroup)
    tableGroup.remove(ball)
  }

  // Update ball positions and stats
  ballData.forEach((data, i) => {
    const tx = (data.x - 0.5) * 0.6
    const ty = (0.5 - data.y) * 1.2
    const currentPos = new THREE.Vector3(tx, ty, 0.03)
    
    // Calculate velocity for trail direction (opposite to movement)
    const pGroup = ballParticles[i]
    let prevPos = currentPos.clone() // Default to current if no history

    if (pGroup) {
        prevPos = pGroup.userData.lastPos.clone()
        // Simple velocity estimation
        pGroup.userData.velocity.subVectors(currentPos, pGroup.userData.lastPos).multiplyScalar(0.5) // Dampen
        pGroup.userData.lastPos.copy(currentPos)
    }

    balls[i].position.copy(currentPos)

    // Apply combo-based visual effects
    updateBallAppearance(balls[i], ballGlows[i], ballParticles[i], combo, currentPos, prevPos)
  })

  // Update tracked ball count for config watcher
  lastActiveBallCount.value = balls.length
}

// Update ball appearance and emit particles
const updateBallAppearance = (ball, glow, pGroup, combo, ballPos, prevPos) => {
  if (!ball || !ball.material) return

  const material = ball.material

  // Get current score for scaling effects
  const score = props.stats?.score || 0
  // Calculate score-based multiplier: ranges from 0 at score 0 to 1 at score 100,000+
  const scoreMultiplier = Math.min(1.0, score / 100000)

  // Visual settings based on combo
  let emitRate = 0 // Particles per frame
  let pColor = 0x888888
  let pOpacity = 0.4
  let pSize = 0.01
  let pGrowth = 1.05 // Expansion rate
  let pLifeDecay = 0.01 // Base decay (Slow and lingering)
  let pType = 'smoke' // smoke, sparkle, fire

  if (combo < 10) {
      // Basic Silver - No effects
      material.color.setHex(0xcccccc)
      material.emissive.setHex(0x000000)
      material.emissiveIntensity = 0
      if (glow.material) glow.material.opacity = 0
      emitRate = 0
  } else if (combo < 20) {
      // Level 1: Gold / Orange
      material.color.setHex(0xffaa00) // Gold
      material.emissive.setHex(0xff4400) // Orange glow
      material.emissiveIntensity = 0.5 
      if (glow.material) {
           glow.material.opacity = 0.5
           glow.material.color.setHex(0xffaa00)
      }
      
      emitRate = 0.2
      pColor = 0xaaaaaa
      pSize = 0.012
      pType = 'smoke'
      pOpacity = 0.03 * (0.2 + scoreMultiplier * 0.8)
      pLifeDecay = 0.02
      pGrowth = 1.015
  } else if (combo < 40) {
      // Level 2: TikTok Tech (Technicolor Glitch)
      // Cycle between Cyan and Magenta rapidly
      const time = Date.now()
      const phase = (time % 1000) / 1000 // 1 second cycle
      
      let targetColor
      let emitColor
      
      if (phase < 0.45) {
          targetColor = 0x00ffff // Cyan
          emitColor = 0x00ffff
      } else if (phase < 0.9) {
          targetColor = 0xff00ff // Magenta
          emitColor = 0xff00ff
      } else {
          targetColor = 0xffffff // White flash
          emitColor = 0xffffff
      }
      
      material.color.setHex(targetColor)
      material.emissive.setHex(targetColor)
      material.emissiveIntensity = 0.8
      
      if (glow.material) {
           glow.material.opacity = 0.7
           glow.material.color.setHex(targetColor)
      }
      
      emitRate = 0.6
      pColor = emitColor
      pOpacity = 0.08
      pSize = 0.018
      pGrowth = 1.02
      pLifeDecay = 0.015
      
  } else {
      // Level 3: ACID TRIP (High scale rainbow cycle)
      const time = Date.now() * 0.002 // Speed
      const hue = time % 1.0
      const color = new THREE.Color().setHSL(hue, 1.0, 0.5)
      
      material.color.copy(color)
      material.emissive.copy(color)
      material.emissiveIntensity = 1.0 // Maximum glow
      
      if (glow.material) {
           glow.material.opacity = 0.9
           glow.material.color.copy(color)
      }
      
      // Psychadelic trails
      emitRate = 1.5
      const trailHue = (hue + 0.5) % 1.0 // Complementary color smoke
      pColor = new THREE.Color().setHSL(trailHue, 1.0, 0.5).getHex()
      pOpacity = 0.15
      pSize = 0.025
      pGrowth = 1.04
      pLifeDecay = 0.01
  }
  
  // Update Glow Sprite
  // PointLight uses .intensity, Sprite uses material.opacity
  if (glow.isSprite) {
      // already set above via material.opacity
  } else {
       // Fallback if we revert to lights
      glow.intensity = glow.intensity || 0
  }

  // Apply Smoke Intensity Setting
  // If smoke is disabled (0), scale emitRate to 0
  const smokeIntensity = physicsConfig.value?.smoke_intensity ?? 1.0
  emitRate *= smokeIntensity

  // Emit Particles with Interpolation
  // PERF FIX: Throttle spawning to max 60fps to prevent "event storm" processing 
  // if socket messages backlog (e.g. after a frame drop/freeze).
  const now = Date.now()
  const lastSpawn = pGroup.userData.lastSpawnTime || 0
  if (now - lastSpawn > 16) { // Limit to ~60hz
      pGroup.userData.lastSpawnTime = now
      
      if (pGroup) {
          if (emitRate > 0) {
              spawnParticles(pGroup, emitRate, ballPos, prevPos, pColor, pOpacity, pSize, pGrowth, pLifeDecay)
          }
          animateParticleSystem(pGroup)
      }
  }
}

// Global particle geometry (reused)
const particleGeo = new THREE.SphereGeometry(1, 6, 6)

const spawnParticles = (pGroup, count, currentPos, prevPos, color, opacity, size, growth, decay) => {
    const pool = pGroup.userData.pool
    let spawned = 0
    
    // Determine how many particles to reuse/create
    const totalToSpawn = count
    
    // Spawn loop - Use FOR loop to guarantee termination
    for (let i = 0; i < totalToSpawn; i++) {
        let p = pool.find(p => !p.visible)
        
        // REDUCED LIMIT: 50 (was 300) to fix fill-rate issues
        if (!p && pool.length < 50) { 
            // Reuse global geometry!
            const mat = new THREE.MeshBasicMaterial({ transparent: true })
            p = new THREE.Mesh(particleGeo, mat)
            pGroup.add(p)
            pool.push(p)
        }

        // If still no particle (limit reached and all active), recycle the oldest one?
        // Or just skip. For now, let's recycle random/oldest to keep density up.
        if (!p && pool.length > 0) {
             // Find particle with lowest life (oldest)
             p = pool.reduce((prev, curr) => (prev.userData.life < curr.userData.life) ? prev : curr)
        }
        
        if (p) {
            // Interpolate position based on spawn index
            const t = i / totalToSpawn
            const pos = new THREE.Vector3().lerpVectors(prevPos, currentPos, t)
            
            resetParticle(p, pos, color, opacity, size, growth, decay)
        }
    }
}



// Cached glow texture to prevent recreation
let _glowTexture = null
const getGlowTexture = () => {
    if (_glowTexture) return _glowTexture
    
    const canvas = document.createElement('canvas')
    canvas.width = 32
    canvas.height = 32
    const ctx = canvas.getContext('2d')
    
    const grd = ctx.createRadialGradient(16, 16, 0, 16, 16, 16)
    grd.addColorStop(0, 'rgba(255, 255, 255, 1.0)')
    grd.addColorStop(0.4, 'rgba(255, 255, 255, 0.5)')
    grd.addColorStop(1.0, 'rgba(255, 255, 255, 0.0)')
    
    ctx.fillStyle = grd
    ctx.fillRect(0, 0, 32, 32)
    
    _glowTexture = new THREE.CanvasTexture(canvas)
    return _glowTexture
}

const resetParticle = (p, pos, color, opacity, size, growth, decay) => {
    p.position.copy(pos)
    // More random offset for natural smoke look
    p.position.x += (Math.random() - 0.5) * 0.02
    p.position.y += (Math.random() - 0.5) * 0.02
    p.position.z += (Math.random() - 0.5) * 0.01
    
    // Vary size slightly
    const randomSize = size * (0.8 + Math.random() * 0.4)
    p.scale.set(randomSize, randomSize, randomSize)
    
    p.material.color.setHex(color)
    p.material.opacity = opacity
    p.visible = true
    
    p.userData = {
        life: 1.0,
        decay: decay * (0.8 + Math.random() * 0.4), // Vary decay
        growth: growth,
        baseOpacity: opacity,
        velocity: new THREE.Vector3(
            (Math.random() - 0.5) * 0.01, 
            (Math.random() - 0.5) * 0.01, 
            0.005 + Math.random() * 0.01 // Generally upwards/outwards
        )
    }
}

// Main animation loop for particles
const animateParticleSystem = (pGroup) => {
    const pool = pGroup.userData.pool
    
    pool.forEach(p => {
        if (!p.visible) return
        
        // Update physics
        if (p.userData.velocity) {
             p.position.add(p.userData.velocity)
        }
        
        // Update rotation (for confetti)
        if (p.userData.rotationSpeed) {
            p.rotation.x += p.userData.rotationSpeed.x
            p.rotation.y += p.userData.rotationSpeed.y
            p.rotation.z += p.userData.rotationSpeed.z
        }
        
        // Grow (Legacy support for ball hits)
        if (p.userData.growth) {
             p.scale.multiplyScalar(p.userData.growth)
        }
        
        // Apply Drag/Gravity changes if needed
        // For confetti, we might want "flutter" which is complex, 
        // but basic rotation + slow gravity is usually enough.
        
        // Decay/Life
        if (p.userData.life !== undefined) {
            p.userData.life -= p.userData.decay || 0.01
            
            // Fade out
            if (p.userData.life < 0) {
                p.visible = false
            } else if (p.userData.life < 0.2) {
                p.material.opacity = p.userData.life * 5 // Fade out last 20%
            }
        }
        
        // Floor collision (simple)
        if (p.position.y < -0.8) {
            p.visible = false
        }
    })
}

const updateFlippers = (state) => {
  if (!state.flippers) return
  const flipperData = state.flippers
  const is2D = props.cameraMode === 'top-down'

  if (flippers.left) {
    // Negate angle because Physics +30 is Down, but Three.js +30 is Up
    flippers.left.rotation.z = THREE.MathUtils.degToRad(-flipperData.left_angle)
  }
  
  if (flippers.right) {
    // Physics angle is symmetric (-30 to 30).
    // In perspective mode: 180 - angle works correctly
    // In top-down mode: When looking down Z-axis, we need to negate like left flipper
    // because the Y-axis appears flipped relative to the screen
    if (is2D) {
      // Top-down view: Use negated angle like left flipper
      // But also add 180 to flip the flipper to point left instead of right
      flippers.right.rotation.z = THREE.MathUtils.degToRad(180 + flipperData.right_angle)
    } else {
      // Perspective view: Original formula
      // Visual mesh extends +X (Right).
      // We want it to point Left-Down (210 deg) when angle is -30.
      // 180 - (-30) = 210.
      // We want Left-Up (150 deg) when angle is 30.
      // 180 - 30 = 150.
      flippers.right.rotation.z = THREE.MathUtils.degToRad(180 - flipperData.right_angle)
    }
  }
  
  if (flippers.plunger && state.plunger) {
      // Both x and y are already normalized (0-1) from backend
      flippers.plunger.position.x = mapX(state.plunger.x)
      flippers.plunger.position.y = mapY(state.plunger.y)
  }

  if (flippers.leftPlunger && state.left_plunger) {
      // Both x and y are already normalized (0-1) from backend
      flippers.leftPlunger.position.x = mapX(state.left_plunger.x)
      flippers.leftPlunger.position.y = mapY(state.left_plunger.y)
  }
}

let animationId: number
const animate = () => {
  animationId = requestAnimationFrame(animate)
  if (renderer && scene && camera) {
    // Apply shake offset to camera position (temporarily)
    const basePos = { x: 0, y: -1.5, z: 2.5 } // Default position, should track actual camera pos if moved
    // Better: Apply offset to camera.position relative to its current "base"
    // But camera moves with keys. 
    // Let's just modify the lookAt target or add a shake group?
    // Simplest: Add shakeOffset to camera.position before render, remove after.
    
    const originalX = camera.position.x
    camera.position.x += shakeOffset.x
    
    // Animate UFO bumper lights continuously
    animateUFOLights()
    
    // Animate Mothership (Police Light & Pulse)
    animateMothership()
    
    // Animate Fireworks
    if ((window as any).fireworksGroup) animateParticleSystem((window as any).fireworksGroup)

    if (controls) controls.update()

    if (ballParticles[0]) {
        animateParticleSystem(ballParticles[0])
    }
    // Wait, updateBallAppearance calls animateParticleSystem for its own group.
    
    // Animate Sparks
    animateSparks()

    // Render scene
    // Render scene
    renderer.render(scene, camera)
    
    camera.position.x = originalX // Restore
  }
}

// Spark System
const triggerSparks = (pos) => {
    // Check if scene is valid (has add method)
    if (!scene || typeof scene.add !== 'function') {
        // Only warn once or just ignore? Warn helps debug.
        // console.warn('triggerSparks: scene is not ready', scene)
        return
    }
    // Ensure spark group exists
    if (!(window as any).sparkGroup) {
         const g = new THREE.Group()
         g.userData = { pool: [] }
         // Create pool of spark lines/points
         for(let i=0; i<50; i++) {
             // Elongated sparks (BufferGeometry line or scaled mesh)
             const geometry = new THREE.PlaneGeometry(0.02, 0.08)
             const material = new THREE.MeshBasicMaterial({ 
                 color: 0xffffaa, 
                 side: THREE.DoubleSide, 
                 transparent: true,
                 blending: THREE.AdditiveBlending
             })
             const p = new THREE.Mesh(geometry, material)
             p.visible = false
             g.add(p)
             g.userData.pool.push(p)
         }
         try {
             if (scene && typeof scene.add === 'function') {
                scene.add(g)
                ;(window as any).sparkGroup = g
             } else {
                console.error('triggerSparks: scene invalid during group creation', scene)
             }
         } catch(e) {
             console.error('triggerSparks: Error adding group', e)
         }
    }
    
    const pool = (window as any).sparkGroup.userData.pool
    const count = 8 + Math.floor(Math.random() * 8)
    
    for(let i=0; i<count; i++) {
        const p = pool.find(p => !p.visible)
        if (!p) break
        
        p.visible = true
        p.position.copy(pos)
        // Raise slightly above bumper
        p.position.z += 0.05
        
        // Random explosion direction
        const theta = Math.random() * Math.PI * 2
        const phi = Math.random() * Math.PI * 0.5 // Upward hemisphere
        const speed = 0.05 + Math.random() * 0.08
        
        p.userData = {
            velocity: new THREE.Vector3(
                Math.sin(phi) * Math.cos(theta) * speed,
                Math.sin(phi) * Math.sin(theta) * speed,
                Math.cos(phi) * speed
            ),
            gravity: 0.003,
            life: 1.0,
            decay: 0.04 + Math.random() * 0.04
        }
        
        // Orient spark to velocity direction
        p.lookAt(p.position.clone().add(p.userData.velocity))
        p.scale.set(1, 1, 1)
        p.material.opacity = 1.0
        p.material.color.setHex(0xffffaa) // Reset color
    }
}

// Animation loop addition for sparks
const animateSparks = () => {
    if ((window as any).sparkGroup) {
        (window as any).sparkGroup.userData.pool.forEach(p => {
            if (!p.visible) return
            
            p.userData.life -= p.userData.decay
            if (p.userData.life <= 0) {
                p.visible = false
                return
            }
            
            // Move
            p.position.add(p.userData.velocity)
            // Gravity
            p.userData.velocity.z -= p.userData.gravity
            // Fade
            p.material.opacity = p.userData.life
            // Shrink length?
            p.scale.y = p.userData.life 
        })
    }
}

// Continuous UFO light animation - Slow blinking when idle, fast when hit
const animateUFOLights = () => {
  if (!flippers.bumpers) return

  const time = Date.now() * 0.001
  const now = Date.now()

  flippers.bumpers.forEach((bumperGroup) => {
    const lights = bumperGroup.userData.lights
    const lightColors = bumperGroup.userData.lightColors
    const isActive = bumperGroup.userData.isActive
    const lastHitTime = bumperGroup.userData.lastHitTime

    // Animate bumper scale when hit
    if (lastHitTime) {
      const timeSinceHit = (now - lastHitTime) / 1000 // seconds
      
      // TRIGGER SPARKS if just hit (within first 50ms) and not yet sparked
      if (timeSinceHit < 0.05 && !bumperGroup.userData.hasSparked) {
          triggerSparks(bumperGroup.position)
          bumperGroup.userData.hasSparked = true
      }
      
      // Reset spark flag if enough time passed (debounce)
      if (timeSinceHit > 0.2) {
          bumperGroup.userData.hasSparked = false
      }

      const scaleDuration = 0.2 // 200ms animation

      if (timeSinceHit < scaleDuration) {
        // Scale up then back down with ease-out
        const progress = timeSinceHit / scaleDuration
        // Ease-out cubic
        const eased = 1 - Math.pow(1 - progress, 3)

        // Pop effect: scale up to 1.3x then back to 1.0
        let scale
        if (progress < 0.3) {
          // Quick scale up
          scale = 1.0 + (progress / 0.3) * 0.3
        } else {
          // Slower scale down
          scale = 1.3 - ((progress - 0.3) / 0.7) * 0.3
        }

        bumperGroup.scale.set(scale, scale, scale)
      } else {
        // Ensure scale is reset
        bumperGroup.scale.set(1, 1, 1)
      }
    } else {
      // Not hit, ensure normal scale
      bumperGroup.scale.set(1, 1, 1)
    }

    // Light blinking animation
    if (lights && lightColors) {
      lights.forEach((light, j) => {
        // Different blink speed based on state
        const blinkSpeed = isActive ? 15 : 1.5 // 15 Hz when hit, 1.5 Hz when idle
        const phaseOffset = j * 1.3
        const blinkCycle = (time * blinkSpeed + phaseOffset) % 1

        // Sharp on/off transition with smooth edges
        let blink
        if (blinkCycle < 0.4) {
          // ON - full brightness
          blink = 1.0
        } else if (blinkCycle < 0.5) {
          // Quick fade out
          blink = (0.5 - blinkCycle) / 0.1
        } else if (blinkCycle < 0.9) {
          // OFF
          blink = 0.0
        } else {
          // Quick fade in
          blink = (blinkCycle - 0.9) / 0.1
        }

        // Brighter when hit
        const maxIntensity = isActive ? 3.0 : 1.8
        light.material.emissiveIntensity = maxIntensity * blink

        // Bigger scale when hit
        const maxScale = isActive ? 1.5 : 1.2
        const scale = 0.8 + blink * (maxScale - 0.8)
        light.scale.set(scale, scale, scale)

        // Ensure correct colors (return from white flash)
        if (!isActive) {
          light.material.color.setHex(lightColors[j])
          light.material.emissive.setHex(lightColors[j])
        }
      })
    }

    // Dome glow pulses independently (slower)
    const domeMesh = bumperGroup.userData.domeMesh
    if (domeMesh) {
      if (isActive) {
        // Rapid pulse when hit
        const domeBlink = Math.sin(time * 20) * 0.5 + 0.5
        domeMesh.material.emissiveIntensity = 1.0 + domeBlink * 1.5
      } else {
        // Slow pulse when idle
        const domeBlink = Math.sin(time * 1.5) * 0.5 + 0.5
        domeMesh.material.emissiveIntensity = 0.2 + domeBlink * 0.4
      }
    }
  })
}

const animateMothership = () => {
    const group = flippers.mothership
    
    // Debug entry
    // console.log("AnimateMothership called", group ? "Group OK" : "No Group", group && group.visible ? "Visible" : "Hidden")

    if (!group || !group.visible) return
    
    const time = Date.now() * 0.001
    
    // Rotate Lights (Underneath)
    if (group.userData.lightsGroup) {
        group.userData.lightsGroup.rotation.y = time * 2.0 
    }
    
    // Pulse Ring
    if (group.userData.ring) {
        const pulse = Math.sin(time * 5) * 0.5 + 0.5
        group.userData.ring.material.opacity = 0.5 + pulse * 0.5
        // Cyan color pulse
        group.userData.ring.material.color.setHSL(0.5, 1.0, 0.5 + pulse * 0.5) 
    }

    // Pulse Dome
    if (group.userData.dome) {
        group.userData.dome.material.emissiveIntensity = 0.5 + Math.sin(time * 3) * 0.3 + 0.2
    }
      
    // Rotate Police Light (Fast Spin)
    if (group.userData.policeLight) {
        // Continuous rotation based on time (ensure smooth loop)
        // Rotate Y relative to the SHIP ROTATOR group (which is Z flipped).
        // Since logic is continuous time, direction depends on sign.
        const rot = -time * 10.0
        group.userData.policeLight.rotation.y = rot
    }
}

const initThree = () => {
  scene = new THREE.Scene()
  const bgTexture = new THREE.TextureLoader().load('/textures/starfield.png')
  bgTexture.colorSpace = THREE.SRGBColorSpace
  scene.background = bgTexture // Starfield background
  // scene.background = new THREE.Color(0x1a1a28) // Fallback

  // Initial size (will be updated by ResizeObserver)
  const width = container.value.clientWidth
  const height = container.value.clientHeight
  const aspect = width / height

  camera = new THREE.PerspectiveCamera(45, aspect, 0.1, 100)
  camera.position.set(0, -1.5, 0.9) 
  camera.lookAt(0, 0, 0)

  renderer = new THREE.WebGLRenderer({ 
      antialias: true,
      powerPreference: "high-performance",
      precision: "highp"
  })
  renderer.setSize(width, height)
  renderer.shadowMap.enabled = false // DISABLED: Performance bottleneck on high-res/zoom
  renderer.shadowMap.type = THREE.PCFSoftShadowMap 
  renderer.toneMapping = THREE.ACESFilmicToneMapping
  renderer.toneMappingExposure = 1.4 // Increased from 1.2 for brighter scene
  container.value.appendChild(renderer.domElement)

  // Enhanced ambient lighting - brighter
  const ambientLight = new THREE.AmbientLight(0x505060, 0.8) // Increased from 0.6
  scene.add(ambientLight)

  // Main directional light with better shadows - brighter
  const dirLight = new THREE.DirectionalLight(0xffffff, 1.5) // Increased from 1.2
  dirLight.position.set(1, -2, 3)
  dirLight.castShadow = true
  // OPTIMIZATION: 1024 shadow map is plenty for this view distance. 2048 is overkill/heavy.
  dirLight.shadow.mapSize.width = 1024 
  dirLight.shadow.mapSize.height = 1024
  dirLight.shadow.camera.near = 0.5
  dirLight.shadow.camera.far = 10
  scene.add(dirLight)
  
  // Accent light - purple/blue for atmosphere - brighter
  const accentLight = new THREE.PointLight(0x6600ff, 1.0, 3) // Increased from 0.8
  accentLight.position.set(0.2, 0.3, 0.5)
  scene.add(accentLight)

  // Secondary accent - cyan for depth - brighter
  const accentLight2 = new THREE.PointLight(0x00ffff, 0.8, 2.5) // Increased from 0.6
  accentLight2.position.set(-0.2, -0.3, 0.4)
  scene.add(accentLight2)

  // OrbitControls
  controls = new OrbitControls(camera, renderer.domElement)
  controls.enableDamping = true
  controls.dampingFactor = 0.05
  controls.screenSpacePanning = true
  controls.enableRotate = false 
  controls.enabled = false // Start disabled (Locked)

  // Mobile Gestures Configuration
  controls.touches = {
      ONE: (THREE as any).TOUCH.NONE, // Disable 1-finger interaction 
      TWO: THREE.TOUCH.DOLLY_PAN // 2-finger zoom/pan
  }
  scene.add(accentLight2)

  // Rim light from behind for definition - brighter
  const rimLight = new THREE.DirectionalLight(0x8888ff, 0.6) // Increased from 0.4
  rimLight.position.set(0, 2, -1)
  scene.add(rimLight)

  // Initial creation (likely empty config until prop updates)
  // Initialize physicsConfig from props
  if (props.config) {
      physicsConfig.value = props.config
  }

  createTable(props.config)
  
  // Ensure camera is updated to match config immediately
  updateCamera()

  // Set initial visibility based on camera mode
  updateVisibilityForCameraMode(props.cameraMode)

  // Start the animation loop
  animate()
}

  // Reactive state for overlay logic
  // activeBallCount moved to top with other refs
  const showGameOver = ref(false)
  const lastGamesPlayed = ref(null) // Local track of games played
  const isInitialMount = ref(true) // Track if component just mounted
  let gameOverTimeout = null

  onMounted(() => {
  console.log('Pinball3D Mounted. Initial Config:', props.config)
  initThree()
  
  // Setup ResizeObserver
  resizeObserver = new ResizeObserver(entries => {
    for (let entry of entries) {
      const { width, height } = entry.contentRect
      // console.warn(`📐 RESIZE DETECTED: ${width}x${height}, balls: ${balls.length}`)
      if (camera && renderer && width > 0 && height > 0 && 'aspect' in camera) {
        const oldAspect = camera.aspect
        camera.aspect = width / height
        camera.updateProjectionMatrix()
        
        // PERFORMANCE FIX: Fixed internal resolution scaling (User requested "enlarged regular view")
        // Calculate target resolution (upscale from a lower resolution if fullscreen)
        const targetHeight = Math.min(height, 1080) // Cap internal render height at 1080p
        const targetWidth = targetHeight * camera.aspect
        
        renderer.setSize(targetWidth, targetHeight, false) // false = don't update CSS size (let it stretch)
        

        
        // Ensure CSS style matches container (stretch to fill)
        // Use setProperty to be explicit and potentially override inline styles
        renderer.domElement.style.setProperty('width', '100%', 'important')
        renderer.domElement.style.setProperty('height', '100%', 'important')
        renderer.domElement.style.setProperty('display', 'block', 'important')
        renderer.domElement.style.setProperty('object-fit', 'contain') // Ensure aspect ratio is preserved if needed
        
        // Reset pixel ratio to 1.0 since we are handling scaling scaling manually
        renderer.setPixelRatio(1.0)
        
        // if (Math.abs(oldAspect - camera.aspect) > 0.01) {
        //   console.error(`⚠️ ASPECT RATIO CHANGED: ${oldAspect.toFixed(3)} → ${camera.aspect.toFixed(3)}`)
        // }
      }
    }
  })
  if (container.value) {
    resizeObserver.observe(container.value)
  }

  // Force initial resize/update after mount to ensure proper alignment
  // This fixes the issue where rails don't align until layout is changed
  setTimeout(() => {
    if (container.value && renderer && camera && 'aspect' in camera) {
      const rect = container.value.getBoundingClientRect()
      camera.aspect = rect.width / rect.height
      camera.updateProjectionMatrix()
      renderer.setSize(rect.width, rect.height)

      // Update visibility for current camera mode
      updateVisibilityForCameraMode(props.cameraMode)

      console.log('Pinball3D: Initial alignment update completed')
    }
  }, 100) // Small delay to ensure DOM is fully rendered

  // Use shared socket from props
  const socket = props.socket
  
  // Remove existing listeners to avoid duplicates if re-mounted?
  // Socket.io ensures one listener per event usually if using .on, but if we re-mount we might duplicate.
  // Ideally we should clean up in onUnmounted.
  
  const onConnect = () => {
    console.log('Pinball3D Socket Connected')
  }

  
  const updateDropTargets = (dropTargetStates: boolean[]) => {
    if (!flippers.dropTargets || !dropTargetStates) return
    
    // console.log('[updateDropTargets] States received:', dropTargetStates)
    // console.log('[updateDropTargets] Mesh count:', flippers.dropTargets.length)
    
    flippers.dropTargets.forEach((mesh, i) => {
      if (i < dropTargetStates.length) {
        const newVisible = dropTargetStates[i]
        if (mesh.visible !== newVisible) {
          // console.log(`[updateDropTargets] Target ${i}: ${mesh.visible} -> ${newVisible}`)
        }
        mesh.visible = newVisible
        // console.log(`[updateDropTargets] Target ${i} mesh.visible is now:`, mesh.visible, 'position:', mesh.position)
      }
    })
  }

  const updateBumpers = (state: { bumper_states?: boolean[], bumper_health?: number[] }) => {
    if (!flippers.bumpers || !state) return
    const bumperStates = state.bumper_states || []
    const bumperHealth = state.bumper_health || []
    
    flippers.bumpers.forEach((bumperGroup, i) => {
      // Health State Tracking (for events)
      const currentHealth = (i < bumperHealth.length) ? bumperHealth[i] : 100
      const prevHealth = bumperGroup.userData.lastHealth !== undefined ? bumperGroup.userData.lastHealth : 100
      bumperGroup.userData.lastHealth = currentHealth
      
      // Damage Smoke (< 50% Health)
      if (currentHealth < 50 && currentHealth > 0 && bumperGroup.visible) {
           const damageRatio = (50 - currentHealth) / 50.0 // 0.0 to 1.0 (at 0 health)
           // Chance to spawn smoke increases with damage (0.01 to 0.1 per frame)
           if (Math.random() < 0.05 + (damageRatio * 0.15)) {
               const pos = bumperGroup.position.clone()
               // Randomize pos slightly (top of bumper)
               pos.z += 0.05
               const pGroup = ballParticles[0]
               if (pGroup) {
                   // Smoke: Dark Gray, slow moving, grows, fades
                   spawnParticles(pGroup, 1, pos, pos, 0x555555, 0.2, 0.03 + (damageRatio * 0.02), 1.01, 0.02)
               }
           }
      }

      // Destruction / Explosion
      if (currentHealth <= 0 && prevHealth > 0) {
          // Explode!
          if (bumperGroup.visible) {
             const pos = bumperGroup.position.clone()
             // Spawn explosion particles
             const particleCount = 20
             const pGroup = ballParticles[0] // borrow a particle group or create a temp one?
             // Actually, we have a pool. Let's use spawnParticles helper if we can, or just manual
             // We'll use a specific explosion bloom
             
             // Simple "spark" explosion at bumper position
             if (pGroup) {
                 spawnParticles(pGroup, 30, pos, pos, 0xff5500, 1.0, 0.05, 1.02, 0.03) // Fire
                 spawnParticles(pGroup, 30, pos, pos, 0xffffff, 1.0, 0.02, 1.05, 0.05) // White sparks
             }
             bumperGroup.visible = false
             
             // Mark as destroyed and emit event
             if (!bumperGroup.userData.destroyed) {
                 bumperGroup.userData.destroyed = true
                 console.log(`[Pinball3D] Bumper ${i} destroyed! Emitting event...`)
                 emit('ship-destroyed')
             }
             
             // Trigger Audio-Visual FX
             if (SoundManager) SoundManager.playDestruction()
             triggerShake({ type: 'alien', strength: 0.5, direction: 'left' }) // Shake!
          }
      }
      
      // Respawn / Teleport
      if (currentHealth > 0 && prevHealth <= 0) {
          // Teleport in!
          if (!bumperGroup.visible) {
             bumperGroup.visible = true
             bumperGroup.scale.setScalar(0.01)
             bumperGroup.userData.respawnAnim = 0.0
             
             const pos = bumperGroup.position.clone()
             // Spawn teleport ring particles
             if (ballParticles[0]) {
                 spawnParticles(ballParticles[0], 20, pos, pos, 0x00ffff, 0.8, 0.04, 1.01, 0.02)
             }
          }
      }

      // Skip visual updates if dead (invisible)
      if (currentHealth <= 0) {
          if (bumperGroup.visible) bumperGroup.visible = false
          return 
      }
      
      // Respawn Animation (Scale up)
      if (bumperGroup.userData.respawnAnim !== undefined) {
          bumperGroup.userData.respawnAnim += 0.05
          if (bumperGroup.userData.respawnAnim >= 1.0) {
              bumperGroup.userData.respawnAnim = undefined
              bumperGroup.scale.setScalar(1.0)
          } else {
              // Elastic bounce in
              const t = bumperGroup.userData.respawnAnim
              const scale = 1.0 + Math.sin(t * Math.PI * 2) * (1.0 - t) * 0.5
              bumperGroup.scale.setScalar(Math.min(1.0, t) * scale) // Grow from 0
          }
      }

      if (i < bumperStates.length) {
        const active = Number(bumperStates[i]) > 0
        const domeMesh = bumperGroup.userData.domeMesh
        const ringMesh = bumperGroup.userData.ringMesh
        const lights = bumperGroup.userData.lights

        bumperGroup.userData.isActive = active

        if (active && !bumperGroup.userData.lastHitTime) {
          bumperGroup.userData.lastHitTime = Date.now()
        } else if (!active) {
          bumperGroup.userData.lastHitTime = null
        }
        
        // Shake Effect on Active
        if (active) {
            // Jitter position slightly
            const jitter = 0.005
            if (bumperGroup.userData.originalPos) {
                bumperGroup.position.x = bumperGroup.userData.originalPos.x + (Math.random() - 0.5) * jitter
                bumperGroup.position.y = bumperGroup.userData.originalPos.y + (Math.random() - 0.5) * jitter
            }
        } else {
            // Restore position
            if (bumperGroup.userData.originalPos) {
                bumperGroup.position.copy(bumperGroup.userData.originalPos)
            }
        }

        if (active) {
            if (domeMesh) {
              domeMesh.material.color.setHex(0xffffff)
              domeMesh.material.emissive.setHex(0xffffff)
            }
            if (ringMesh) {
              ringMesh.material.color.setHex(0xffffff)
              ringMesh.material.emissive.setHex(0xffffff)
              ringMesh.material.emissiveIntensity = 2.0
            }
            if (lights) {
              lights.forEach(light => {
                light.material.color.setHex(0xffffff)
                light.material.emissive.setHex(0xffffff)
              })
            }
        } else {
            if (domeMesh) {
              domeMesh.material.color.setHex(0xcccccc)
              domeMesh.material.emissive.setHex(0x666666)
            }
            if (ringMesh) {
              ringMesh.material.color.setHex(0x888888)
              ringMesh.material.emissive.setHex(0x444444)
              ringMesh.material.emissiveIntensity = 0.3
            }
            if (lights && bumperGroup.userData.lightColors) {
              lights.forEach((light, j) => {
                const color = bumperGroup.userData.lightColors[j]
                light.material.color.setHex(color)
                light.material.emissive.setHex(color)
              })
            }
        }

        // Scale Animation (Bounce)
        if (bumperGroup.userData.lastHitTime && bumperGroup.userData.respawnAnim === undefined) {
           const elapsed = Date.now() - bumperGroup.userData.lastHitTime
           const duration = 150
           if (elapsed < duration) {
               const progress = elapsed / duration
               const scale = 1.0 + Math.sin(progress * Math.PI) * 0.2
               bumperGroup.scale.setScalar(scale)
           } else {
               bumperGroup.scale.setScalar(1.0)
           }
        }
      }

      // Health Bar Update
      if (bumperGroup.userData.healthBar && i < bumperHealth.length) {
         const health = bumperHealth[i]
         const healthPct = Math.max(0, health / 100.0)
         bumperGroup.userData.healthBar.scale.x = healthPct
         
         if (healthPct > 0.5) bumperGroup.userData.healthBar.material.color.setHex(0x00ff00)
         else if (healthPct > 0.2) bumperGroup.userData.healthBar.material.color.setHex(0xffff00)
         else bumperGroup.userData.healthBar.material.color.setHex(0xff0000)
      }
    })
  }

  // Watch for Game Over Condition based on Games Played increment
  watch(() => props.stats?.games_played, (newCount) => {
      // Ignore if undefined
      if (newCount === undefined) return
      
      // Initialize if null
      if (lastGamesPlayed.value === null) {
          lastGamesPlayed.value = newCount
          isInitialMount.value = true // Mark as initial mount
          return
      }

      // Skip game over trigger on first real update after mount (view change scenario)
      if (isInitialMount.value) {
          isInitialMount.value = false
          lastGamesPlayed.value = newCount
          return
      }
      
      // TRIGGER: Game Over (Latch Open) when games_played increases
      if (newCount > lastGamesPlayed.value) {
          if (!showGameOver.value) {
              showGameOver.value = true
              
              if (gameOverTimeout) clearTimeout(gameOverTimeout)

              if (props.autoStartEnabled) {
                  gameOverTimeout = setTimeout(() => {
                      showGameOver.value = false
                  }, 3000)
              }
          }
          // Update local tracker
          lastGamesPlayed.value = newCount
      }
      else if (newCount < lastGamesPlayed.value) {
          // Reset tracker if server reset count (e.g. restart)
          lastGamesPlayed.value = newCount
      }
  })
  
  // Watch active balls to close the latch
  watch(activeBallCount, (newVal) => {
      if (newVal > 0 && showGameOver.value) {
           showGameOver.value = false
           if (gameOverTimeout) clearTimeout(gameOverTimeout)
      }
  })

  const updateMothership = (msState) => {
    // Mothership rendering update
    const group = flippers.mothership
    if (!group) return

    if (!msState || !msState.active) {
      group.visible = false
      return
    }

    // It's active!
    group.visible = true
    
    // Position
    if (msState.x !== undefined && msState.y !== undefined) {
        group.position.set(mapX(msState.x), mapY(msState.y), 0.05)
    }

    // --- Animation ---
    // Moved to animateMothership() for smooth 60fps playback

    // Health Bar
    if (group.userData.fillMesh && msState.max_health > 0) {
        let healthPct = msState.health / msState.max_health
        healthPct = Math.max(0, Math.min(1, healthPct))
        
        // Scale X
        group.userData.fillMesh.scale.x = healthPct
        
        // Color depends on health? Green -> Yellow -> Red
        const mat = group.userData.fillMesh.material
        if (healthPct > 0.5) mat.color.setHex(0x00ff00)
        else if (healthPct > 0.2) mat.color.setHex(0xffff00)
        else mat.color.setHex(0xff0000)
    }
  }

  const onGameState = (state) => {
    if (!state || !state.balls) return

    updateBalls(state.balls)
    activeBallCount.value = state.balls.length // Track active balls
    updateFlippers(state)
    updateDropTargets(state.drop_targets)
    updateBumpers(state)
    if (state.mothership) updateMothership(state.mothership)

    // Handle Sound & Visual Events
    if (state.events && state.events.length > 0) {
      state.events.forEach(event => {
          if (event.type === 'nudge') {
              triggerShake(event)
          }
      })
      
      // console.log("Received events:", state.events)
      
      // Calculate dynamic pitch based on multiplier and combo
      let pitch = 1.0
      if (props.stats) {
        const multiplier = props.stats.score_multiplier || 1
        const combo = props.stats.combo_count || 0
        const GUITAR_THRESHOLD = 10
        
        // Check for 10x combo milestone (plays jingle and switches scale)
        SoundManager.checkComboMilestone(combo)

        if (combo > 0) {
            // Get the current musical scale (changes every 10x combo)
            const currentScale = SoundManager.getCurrentScale()
            const scaleIndex = SoundManager.currentScaleIndex || 0
            
            // Each scale starts at a higher base pitch (+12% per scale)
            // Fix: Start at 1.12 so root note triggers music threshold (>1.05)
            const scaleBasePitch = 1.12 + (scaleIndex * 0.12)

            // Cycle through 8 notes of the scale
            const localNoteStep = (combo - 1) % 8;
            const noteIndex = Math.min(Math.floor(localNoteStep), currentScale.notes.length - 1)
            const semitones = currentScale.notes[noteIndex]

            pitch = scaleBasePitch * Math.pow(2, semitones / 12)
            pitch = Math.min(pitch, 8.0)
        } else {
             pitch = 1.0;
        }

      }

      state.events.forEach(event => {
        if (event.type === 'collision') {
          // console.log('[Sound Event]', event.label, 'pitch:', pitch.toFixed(2))
          if (event.label === 'bumper') {
            SoundManager.playBumper(pitch)
          } else if (event.label === 'rail') {
             SoundManager.playRailHit(pitch)
          } else if (event.label === 'wall') {
             SoundManager.playWallHit(0.5, pitch)
          } else if (event.label === 'drop_target') {
            SoundManager.playDropTarget(pitch)
          } else if (event.label === 'flipper') {
             SoundManager.playFlipperHit(pitch) 
          }
        }
      })
    }
  }

  // Socket setup with validation
  console.log('[Pinball3D onMounted] Socket:', socket, 'Type:', typeof socket)
  
  if (!socket) {
    console.warn('[Pinball3D] No socket provided, skipping event listeners')
  } else if (typeof socket.on !== 'function') {
    console.error('[Pinball3D] Socket.on is not a function. Socket value:', socket)
  } else {
    try {
      // If already connected
      if (socket.connected) {
        onConnect()
      }

      // Setup socket event listeners  
      if (typeof socket.on === 'function') {
        socket.on('connect', onConnect)
        socket.on('game_state', onGameState)
        socket.on('stuck_ball', onStuckBall)
        console.log('[Pinball3D] Socket event listeners registered')
      } else {
        console.warn('[Pinball3D] socket.on is not a function, skipping event listeners')
      }

      // Store cleanup function
      (container.value as any)._cleanupSocket = () => {
        if (socket && typeof socket.off === 'function') {
          socket.off('connect', onConnect)
          socket.off('game_state', onGameState)
          socket.off('stuck_ball', onStuckBall)
        }
      }
    } catch (error) {
      console.error('[Pinball3D] Failed to setup socket listeners:', error)
    }
  }

  
  window.addEventListener('keydown', handleKeydown)
})

// View Mode State
// Removed internal viewMode state in favor of props.cameraMode

const updateCamera = () => {
  if (!camera) return
  
  if (props.cameraMode === 'top-down') {
    // Top-Down Orthographic-like view
    // Position high up on Z axis, looking down
    // Center of table is (0,0,0)
    camera.position.set(0, 0, 1.8) // Reduced from 5 to 1.8 to fit table better
    camera.zoom = 1.0 // Reset zoom
    camera.lookAt(0, 0, 0)
    camera.updateProjectionMatrix()
    
    // Ensure controls target is reset so it doesn't drift
    if (controls) {
        controls.target.set(0, 0, 0)
        controls.update()
    }

    // Note: Don't override rotation after lookAt() - it sets the rotation for us
    // Looking down the Z-axis from +Z toward origin
    // mapY inverts physics Y (0=top, 1=bottom) to Three.js Y (+0.6=top, -0.6=bottom)
    // This creates the correct orientation when viewed from above
    // (zoom reset handles "too large" issue if coming from zoomed-in perspective)
  } else {
    // Perspective View (Restore from config or default)
    if (physicsConfig.value && physicsConfig.value.camera_x !== undefined) {
       const cx = mapX(physicsConfig.value.camera_x)
       const cy = mapY(physicsConfig.value.camera_y)
       const cz = physicsConfig.value.camera_z
       const pinch = (physicsConfig.value.camera_pitch || 45) * (Math.PI / 180)
       const zoom = physicsConfig.value.camera_zoom || 1.0
       
       // Calculate camera position based on pitch and zoom
       // Zoom > 1 means closer (smaller distance)
       const baseDistance = Math.sqrt(cy * cy + cz * cz)
       const distance = baseDistance / zoom
       
       const adjustedY = -distance * Math.cos(pinch)
       const adjustedZ = distance * Math.sin(pinch)
       
       camera.position.set(cx, adjustedY, adjustedZ)
       camera.lookAt(0, 0, 0)
    } else {
       // Default
       camera.position.set(0, -1.5, 0.9)
       camera.lookAt(0, 0, 0)
    }
  }
  if (camera) {
      cameraDebug.value = {
          x: camera.position.x,
          y: camera.position.y,
          z: camera.position.z
      }
  }
}

// Watch for cameraMode changes
watch(() => props.cameraMode, (newMode) => {
    console.log('Pinball3D: cameraMode changed to', newMode)
    updateCamera()
    updateVisibilityForCameraMode(newMode)

    // Force renderer update to ensure everything is properly aligned
    if (renderer && camera) {
        camera.updateProjectionMatrix()

        // Trigger a resize to recalculate dimensions
        if (renderer && camera && container.value && 'aspect' in camera) {
            const rect = container.value.getBoundingClientRect()
            renderer.setSize(rect.width, rect.height)
            camera.aspect = rect.width / rect.height
            camera.updateProjectionMatrix()
        }
    }
})

// Watch for combo/multiplier changes that might cause DOM reflow
// This fixes the issue where rails misalign when combo toast appears
watch(() => [props.stats?.combo_count, props.stats?.score_multiplier], () => {
    // Defer the update to after DOM has updated
    setTimeout(() => {
        if (renderer && camera && container.value && 'aspect' in camera) {
            const rect = container.value.getBoundingClientRect()
            if (rect.width > 0 && rect.height > 0) {
                camera.aspect = rect.width / rect.height
                camera.updateProjectionMatrix()
            }
        }
    }, 0)
}, { deep: true })

// Function to update visibility of 3D vs 2D elements based on camera mode
const updateVisibilityForCameraMode = (mode: string) => {
    const is2D = mode === 'top-down'

    // Update bumpers: show/hide 3D dome vs 2D circle
    if (flippers.bumpers) {
        flippers.bumpers.forEach(bumperGroup => {
            const domeMesh = bumperGroup.userData.domeMesh
            const ringMesh = bumperGroup.userData.ringMesh
            const lights = bumperGroup.userData.lights
            const bumper2D = bumperGroup.userData.bumper2D

            if (domeMesh) domeMesh.visible = !is2D
            if (ringMesh) ringMesh.visible = !is2D
            if (lights) {
                lights.forEach(light => {
                    light.visible = !is2D
                })
            }
            if (bumper2D) bumper2D.visible = is2D
        })
    }

    // Update rails: show/hide 3D cylinders vs 2D flat lines
    if (railMeshes && railMeshes.length > 0) {
        railMeshes.forEach(railMesh => {
            // Show 3D cylinder in perspective mode, hide in 2D mode
            railMesh.visible = !is2D

            // Show 2D flat line in 2D mode, hide in perspective mode
            const rail2D = railMesh.userData.rail2D
            if (rail2D) {
                rail2D.visible = is2D
            }
        })
    }

    // Update drop targets: in 2D mode they should already be visible as flat planes
    // The 3D boxes are positioned at h/2 (above ground) so they're visible in both modes
    // But we can make them more visible in 2D by ensuring proper material
    if (flippers.dropTargets) {
        flippers.dropTargets.forEach(target => {
            // Drop targets work in both modes, but we can adjust if needed
            // For now, leave them as-is since they're boxes that look ok from above
        })
    }
}

// Watch for flipper zone visibility changes
watch(() => props.showFlipperZones, (newValue) => {
    zoneMeshes.forEach(mesh => {
        mesh.visible = newValue
    })
})

// Watch for config changes from parent (must be after createTable is defined)
// Watch for config changes from parent (must be after createTable is defined)
// updateTable removed as it was unused and broken

const activateControls = () => {
    if (controls && !controlsActive.value) {
        controls.enabled = true
        controlsActive.value = true
        // Optional: Reset if needed, or just unlock
    }
}

// Cache last table config string to detect changes
const lastTableConfigStr = ref("")
const lastCameraConfig = ref<{x?: number, y?: number, z?: number, pitch?: number, zoom?: number}>({})
const lastActiveBallCount = ref(0) // Track ball count to prevent rebuild during multiball

// Watch for config changes from parent (must be after createTable is defined)
watch(() => props.config, (newConfig) => {
    if (!newConfig) return
    if (isDragging.value) return

    // console.log('[Pinball3D] Config watcher fired')

    // 1. Check Table Configuration Logic (Rails, Bumpers, Flippers, etc)
    // We create a "signature" of the table configuration to detect changes
    // This is necessary because 'oldConfig' might be the same reference as 'newConfig' for deep watches
    
    // Create a copy without camera properties to avoid rebuilding table on camera move
    const tableConfig = { ...newConfig }
    delete tableConfig.camera_x
    delete tableConfig.camera_y
    delete tableConfig.camera_z
    delete tableConfig.camera_pitch
    delete tableConfig.camera_zoom
    
    // We also exclude some runtime state if present in config (though usually distinct)
    
    const tableConfigStr = JSON.stringify(tableConfig)
    
    console.log(`[Config Watch] New Hash Len: ${tableConfigStr.length}, Old Hash Len: ${lastTableConfigStr.value.length}`)
    // console.log(`[Config Watch] New Hash: ${tableConfigStr.substring(0, 50)}...`)
    
    if (tableConfigStr !== lastTableConfigStr.value) {
        // SAFETY: Don't rebuild table during multiball transitions
        // If ball count just changed, defer the table rebuild
        const currentBallCount = balls.length
        if (currentBallCount !== lastActiveBallCount.value && currentBallCount > 0) {
            console.log('[Config Watch] BLOCKED table rebuild during multiball transition')
            console.log('[Config Watch] Ball count changed from', lastActiveBallCount.value, 'to', currentBallCount)
            // Update the config string so we don't rebuild next time either
            lastTableConfigStr.value = tableConfigStr
            lastActiveBallCount.value = currentBallCount
            return
        }

        console.log('[Config Watch] Table configuration changed, rebuilding table!')
        console.log('[Config Watch] Previous config hash:', lastTableConfigStr.value.substring(0, 50))
        console.log('[Config Watch] New config hash:', tableConfigStr.substring(0, 50))
        createTable(newConfig)
        lastTableConfigStr.value = tableConfigStr
        
        // Also update Last Flipper Values for other logic if used
        lastFlipperValues.length = newConfig.flipper_length
        lastFlipperValues.width = newConfig.flipper_width
        lastFlipperValues.tipWidth = newConfig.flipper_tip_width
        
        // updateCamera() // REMOVED: Don't reset camera on table edit
    }

    // Update physicsConfig reference so updateCamera uses fresh values when called
    physicsConfig.value = newConfig

    // 2. Check Camera Configuration Logic
    // Update Camera Position if in perspective mode AND camera params changed
    if (props.cameraMode === 'perspective') {
        let cameraChanged = false
        
        const currentCam = {
            x: newConfig.camera_x,
            y: newConfig.camera_y,
            z: newConfig.camera_z,
            pitch: newConfig.camera_pitch,
            zoom: newConfig.camera_zoom
        }
        
        // Compare against last known applied camera config
        if (
            currentCam.x !== lastCameraConfig.value.x ||
            currentCam.y !== lastCameraConfig.value.y ||
            currentCam.z !== lastCameraConfig.value.z ||
            currentCam.pitch !== lastCameraConfig.value.pitch ||
            currentCam.zoom !== lastCameraConfig.value.zoom
        ) {
            cameraChanged = true
            lastCameraConfig.value = currentCam
        }
        
        if (cameraChanged) {
            updateCamera()
        }
    }
}, { deep: true })



// Nudge Animation (Camera Shake)
const lastNudgeTime = ref(0) // Start at 0, will update on first real nudge
const isInitialLoad = ref(true)

watch(() => props.nudgeEvent, (newVal, oldVal) => {
  // Skip initial mount/load where oldVal is undefined
  if (isInitialLoad.value) {
    isInitialLoad.value = false
    // Initialize lastNudgeTime from props if it exists
    if (newVal?.time) {
      lastNudgeTime.value = newVal.time
    }
    return
  }

  // Only trigger on new nudges (timestamp increased)
  if (newVal && newVal.time && newVal.time > lastNudgeTime.value) {
    lastNudgeTime.value = newVal.time
    triggerShake(newVal.direction)
  }
}, { deep: true })

const shakeOffset = { x: 0, y: 0 }
let shakeFrame = 0

const triggerShake = (eventData) => {
  // console.log('Pinball3D: triggerShake called', eventData)
  
  // Default values
  let intensity = 0.2
  let maxFrames = 10
  let dir = 1
  let isAlien = false
  
  // Handle different input forms
  // Handle different input forms
  if (typeof eventData === 'string') {
      dir = eventData.toLowerCase() === 'left' ? -1 : 1
  } else if (eventData && typeof eventData === 'object') {
      // Handle server event (intensity, direction object) or local prop (direction string)
      if (eventData.direction && typeof eventData.direction === 'string') {
          dir = eventData.direction.toLowerCase() === 'left' ? -1 : 1
      }
      
      if (eventData.type === 'alien' || (eventData.intensity && eventData.intensity > 1.0)) {
          isAlien = true
          intensity = eventData.strength || eventData.intensity || 1.0 
          maxFrames = 60 
      } else if (eventData.intensity) {
          intensity = eventData.intensity
      }
  }

  // Shake animation loop
  let frame = 0
  
  const shake = () => {
    if (frame >= maxFrames) {
      shakeOffset.x = 0
      shakeOffset.y = 0 // Reset Y too
      return
    }
    
    // Oscillate
    const decay = 1 - (frame / maxFrames)
    
    if (isAlien) {
        // Chaotic shake x/y
        shakeOffset.x = (Math.random() - 0.5) * intensity * decay
        shakeOffset.y = (Math.random() - 0.5) * intensity * decay
    } else {
        // Standard horizontal shake
        shakeOffset.x = Math.sin(frame * 1.5) * intensity * decay * dir
    }
    
    frame++
    requestAnimationFrame(shake)
  }
  shake()
}

// Confetti for High Score
let fireworksInterval: ReturnType<typeof setInterval> | null = null

const triggerFireworks = () => {
    console.log('🎆 triggerFireworks called')
    
    // Clear any existing interval to prevent duplicates
    if (fireworksInterval) {
        clearInterval(fireworksInterval)
        fireworksInterval = null
    }

    if (!props.stats.is_high_score) {
        console.log('🎆 Exiting - is_high_score is false')
        return
    }

    // Ensure persistent group exists
    if (!(window as any).fireworksGroup) {
        console.log('🎆 Creating fireworks group')
         const g = new THREE.Group()
         g.userData = { pool: [], lastPos: new THREE.Vector3(), velocity: new THREE.Vector3() }
         
         // Init pool - use flattened planes for confetti look
         for(let i=0; i<300; i++) {
             // Use PlaneGeometry for confetti
             const geometry = new THREE.PlaneGeometry(0.04, 0.02)
             const material = new THREE.MeshBasicMaterial({ side: THREE.DoubleSide, transparent: true })
             const p = new THREE.Mesh(geometry, material)
             p.visible = false
             g.add(p)
             g.userData.pool.push(p)
         }
         
         if (scene) {
             scene.add(g)
             console.log('🎆 Fireworks group added to scene')
         } else {
             console.error('🎆 ERROR: scene is undefined!')
         }
         (window as any).fireworksGroup = g
    } else {
        console.log('🎆 Fireworks group already exists')
    }

    const launchConfetti = () => {
        const fGroup = (window as any).fireworksGroup
        if (!fGroup) return

        // "Broken T-Shirt Cannon" Effect
        // 1. Spastic count (sometimes 0, sometimes 50)
        // 2. Clumpy bursts
        // 3. Poots out with diverse velocity
        
        // Randomly skip frames to simulate sputtering
        if (Math.random() > 0.4) return 
        
        // Burst size variability
        const count = Math.floor(Math.random() * 20) + 5
        const pool = fGroup.userData.pool
        
        // Cannon Source: Moving slightly or fixed?
        // Let's make it look like it's shooting from the top-center "cannon"
        // but the cannon itself is shaking (random offset)
        const cannonBase = new THREE.Vector3(0, 0.6, 0.5) 
        const cannonJitter = new THREE.Vector3(
            (Math.random() - 0.5) * 0.1, 
            0, 
            (Math.random() - 0.5) * 0.1
        )
        const spawnPos = cannonBase.add(cannonJitter)

        for(let i=0; i<count; i++) {
             const p = pool.find(p => !p.visible)
             if (!p) break
             
             p.visible = true
             
             // Position: Clumped at cannon mouth
             p.position.copy(spawnPos)
             p.position.x += (Math.random() - 0.5) * 0.05
             p.position.z += (Math.random() - 0.5) * 0.05
             
             // Random Rotation
             p.rotation.set(Math.random()*Math.PI, Math.random()*Math.PI, Math.random()*Math.PI)
             
             // Random Color
             const colors = [0xFF0000, 0x00FF00, 0x0000FF, 0xFFFF00, 0xFF00FF, 0x00FFFF, 0xFFFFFF, 0xFFA500, 0xFF69B4]
             p.material.color.setHex(colors[Math.floor(Math.random() * colors.length)])
             p.material.opacity = 1.0
             
             // Velocity: "Poot" force
             // Outward (random spread) + slight Upward + Gravity take over later
             const force = 0.02 + Math.random() * 0.03
             const angle = (Math.random() - 0.5) * 2.0 // Spread angle
             
             p.userData = {
                 velocity: new THREE.Vector3(
                    Math.sin(angle) * force, // Spread X
                    (Math.random() * 0.02) - 0.01, // Slight Y float/drop
                    Math.cos(angle) * force + 0.01 // Forward/Back Z? Actually pure random spread in X/Z plane looks better for "falling out"
                 ),
                 rotationSpeed: new THREE.Vector3(
                    (Math.random() - 0.5) * 0.3,
                    (Math.random() - 0.5) * 0.3,
                    (Math.random() - 0.5) * 0.3
                 ),
                 life: 1.5 + Math.random(),
                 decay: 0.005 
             }
             
             // Override velocity for "broken cannon" feel:
             // Sometimes it just falls out (low velocity)
             if (Math.random() > 0.7) {
                 p.userData.velocity.set(
                     (Math.random() - 0.5) * 0.005,
                     -0.01, // Just drop
                     (Math.random() - 0.5) * 0.005
                 )
             }
        }
    }

    // Initial "poof" explosion before broken cannon starts sputtering
    const triggerExplosionPuff = () => {
        const fGroup = (window as any).fireworksGroup
        if (!fGroup) return
        
        console.log('💥 Explosion puff triggered!')
        const pool = fGroup.userData.pool
        const cannonPos = new THREE.Vector3(0, 0.6, 0.5)
        
        // Burst 40-60 particles outward in all directions
        const burstCount = 40 + Math.floor(Math.random() * 20)
        
        for (let i = 0; i < burstCount; i++) {
            const p = pool.find(p => !p.visible)
            if (!p) break
            
            p.visible = true
            p.position.copy(cannonPos)
            
            // Random rotation
            p.rotation.set(Math.random() * Math.PI, Math.random() * Math.PI, Math.random() * Math.PI)
            
            // Smoke/explosion colors (grey, white, orange, yellow)
            const explosionColors = [0x888888, 0xFFFFFF, 0xFF6600, 0xFFAA00, 0x444444]
            p.material.color.setHex(explosionColors[Math.floor(Math.random() * explosionColors.length)])
            p.material.opacity = 1.0
            
            // Explosive outward velocity in sphere pattern
            const theta = Math.random() * Math.PI * 2
            const phi = Math.random() * Math.PI
            const force = 0.05 + Math.random() * 0.05
            
            p.userData = {
                velocity: new THREE.Vector3(
                    Math.sin(phi) * Math.cos(theta) * force,
                    Math.sin(phi) * Math.sin(theta) * force * 0.5, // Less Y spread
                    Math.cos(phi) * force
                ),
                rotationSpeed: new THREE.Vector3(
                    (Math.random() - 0.5) * 0.5,
                    (Math.random() - 0.5) * 0.5,
                    (Math.random() - 0.5) * 0.5
                ),
                life: 0.8 + Math.random() * 0.4, // Short-lived explosion particles
                decay: 0.02
            }
        }
    }

    // Trigger explosion first, then start broken cannon
    triggerExplosionPuff()
    
    // Small delay before broken cannon starts sputtering (post-explosion)
    setTimeout(() => {
        launchConfetti()
        
        // Safety check before creating interval
        if (fireworksInterval) clearInterval(fireworksInterval)
        
        fireworksInterval = setInterval(() => {
            // Only continue if it's a high score AND game is over (or just happened)
            if (!props.stats.is_high_score || !props.stats.game_over) {
                clearInterval(fireworksInterval)
                fireworksInterval = null
                return
            }
            launchConfetti()
        }, 100)
    }, 300)
}

watch(() => props.stats.is_high_score, (val) => {
    // console.log('🎉 is_high_score watcher fired:', val)
    if (val) {
        triggerFireworks()
    } else {
        if (fireworksInterval) {
            clearInterval(fireworksInterval)
            fireworksInterval = null
        }
    }
})

watch(() => props.stats.game_over, (val) => {
    console.log('🏁 game_over watcher fired:', val)
    if (val && props.stats.is_high_score) {
        triggerFireworks()
    } else {
        if (!val && fireworksInterval) {
            clearInterval(fireworksInterval)
            fireworksInterval = null
        }
    }
})

onUnmounted(() => {
  if (container.value && (container.value as any)._cleanupSocket) {
      (container.value as any)._cleanupSocket()
  }
  window.removeEventListener('keydown', handleKeydown)
  // Cleanup Three.js
  if (animationId) cancelAnimationFrame(animationId)
  
  window.removeEventListener('keydown', handleKeydown)
  
  if (fireworksInterval) clearInterval(fireworksInterval)
  if ((window as any).fireworksGroup && scene && typeof scene.remove === 'function') {
      scene.remove((window as any).fireworksGroup)
  }

  if (tableGroup) {
    // Dispose table resources
    tableGroup.traverse((obj) => {
      if ('geometry' in obj && obj.geometry) (obj.geometry as THREE.BufferGeometry).dispose()
      if ('material' in obj && obj.material) {
        if (Array.isArray(obj.material)) {
          obj.material.forEach(mat => (mat as THREE.Material).dispose())
        } else {
          (obj.material as THREE.Material).dispose()
        }
      }
    })
  }
  
  if (renderer) {
      renderer.dispose()
      renderer.forceContextLoss()
      renderer.domElement = null
  }
  
  if (scene) {
      scene.clear()
  }
  
  renderer = null
  scene = null
  camera = null
  
  if (resizeObserver) {
    resizeObserver.disconnect()
  }
})

const handleKeydown = (e) => {
  if (!camera) return

  // Dismiss Game Over immediately on Launch (Space)
  if (e.code === 'Space' && showGameOver.value) {
      console.log("Manual Launch Detected - Hiding Game Over Overlay Immediately")
      showGameOver.value = false
      if (gameOverTimeout) clearTimeout(gameOverTimeout)
  }
  
  const speed = 0.1
  // Prevent default scrolling for camera keys
  // Prevent default scrolling for camera keys
  if (['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'PageUp', 'PageDown'].includes(e.code)) {
    e.preventDefault()
    
    // Switch to manual mode so zoom doesn't reset position
    activateControls()

    switch(e.code) {
      case 'ArrowUp':
        camera.position.y += speed
        break
      case 'ArrowDown':
        camera.position.y -= speed
        break
      case 'ArrowLeft':
        camera.position.x -= speed
        break
      case 'ArrowRight':
        camera.position.x += speed
        break
      case 'PageUp':
        camera.position.z += speed
        break
      case 'PageDown':
        camera.position.z -= speed
        break
    }

    camera.lookAt(0, 0, 0)
    cameraDebug.value = {
        x: camera.position.x,
        y: camera.position.y,
        z: camera.position.z
    }
    
    // Show debug overlay and reset timeout
    showDebug.value = true
    if (debugTimeout) clearTimeout(debugTimeout)
    debugTimeout = setTimeout(() => {
      showDebug.value = false
    }, 2000)
  }
}
</script>

<style scoped>
.pinball-container {
  width: 100%;
  height: 100%;
  position: relative;
  overflow: hidden;
  background: #000;
  border: 1px solid transparent; /* Prepare for border transition */
  transition: border-color 0.3s ease;
}

.debug-overlay {
  position: absolute;
  top: 10px;
  left: 10px;
  background: rgba(0, 0, 0, 0.7);
  color: #00ff00;
  padding: 10px;
  border-radius: 5px;
  font-family: monospace;
  font-size: 12px;
  pointer-events: none;
  z-index: 100;
}

.multiball-indicator {
  display: none;
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  background: rgba(255, 0, 0, 0.9);
  color: white;
  padding: 20px 40px;
  border-radius: 10px;
  font-family: monospace;
  font-size: 24px;
  font-weight: bold;
  pointer-events: none;
  z-index: 999;
  box-shadow: 0 0 30px rgba(255, 0, 0, 0.8);
}

.permanent-debug-panel {
  display: none;
  position: absolute;
  bottom: 10px;
  right: 10px;
  background: rgba(0, 0, 0, 0.85);
  color: #0f0;
  padding: 8px 12px;
  border-radius: 5px;
  font-family: monospace;
  font-size: 11px;
  pointer-events: none;
  z-index: 100;
  line-height: 1.4;
  border: 1px solid #0f0;
}

.permanent-debug-panel div {
  margin: 2px 0;
}

.stuck-ball-dialog {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.8);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 100;
}

.dialog-content {
  background: #222;
  border: 2px solid #ff0000;
  padding: 20px;
  border-radius: 10px;
  text-align: center;
  color: white;
  box-shadow: 0 0 20px rgba(255, 0, 0, 0.5);
}

.dialog-content h2 {
  margin-top: 0;
  color: #ff4444;
}

.timer {
  font-size: 48px;
  font-weight: bold;
  margin: 20px 0;
  color: #ffaa00;
}

.buttons {
  display: flex;
  gap: 20px;
  justify-content: center;
}

.confirm-btn, .cancel-btn {
  padding: 10px 20px;
  font-size: 18px;
  border: none;
  border-radius: 5px;
  cursor: pointer;
}

.confirm-btn {
  background: #4caf50;
  color: white;
}

.cancel-btn {
  background: #f44336;
  color: white;
}

.editor-controls {
    position: absolute;
    bottom: 10px;
    justify-self: center;
    left: auto;
    z-index: 4000;
    display: flex;
    justify-content: center;
    gap: 10px;
    background: rgba(0, 0, 0, 0.7);
    padding: 10px;
    border-radius: 5px;
    pointer-events: auto; /* Ensure clickable */
}

.controls-row {
    display: flex;
    gap: 10px;
    flex-wrap: wrap; /* Allow wrapping */
    align-items: center;
    justify-content: space-between; /* Space between fullscreen (left) and other buttons (right) */
    pointer-events: auto; /* Ensure clickable */
}

.fullscreen-btn {
    background: rgba(0, 0, 0, 0.8);
    color: white;
    border: 1px solid #777;
    padding: 8px 10px;
    cursor: pointer;
    border-radius: 4px;
    display: flex;
    align-items: center;
    justify-content: center;
    min-width: 40px;
    margin-right: auto; /* Push to far left */
}

.fullscreen-btn:hover {
    background: rgba(0, 120, 215, 0.8);
    border-color: #0078d7;
}

.fullscreen-btn svg {
    display: block;
}

.edit-actions {
    display: flex;
    flex-direction: row;
    justify-content: space-evenly;
    gap: 15px;
    pointer-events: auto;
}

.editor-controls button, .switch-view-btn {
    background: rgba(0, 0, 0, 0.8); /* Darker background */
    color: white;
    border: 1px solid #777;
    padding: 8px 12px; /* Larger hit area */
    cursor: pointer;
    border-radius: 4px;
    font-size: 14px; /* Larger text */
    white-space: nowrap;
    flex-shrink: 0;
    min-width: fit-content;
    z-index: 1000; /* Ensure on top */
}



.editor-controls button:hover, .switch-view-btn:hover {
    background: rgba(0, 0, 0, 0.8);
}

.sound-toggle-btn {
    position: absolute;
    top: 1px;
    right: 0;
    background: rgba(0, 0, 0, 0.6);
    border: none;
    border-radius: 50%;
    width: 40px;
    height: 40px;
    font-size: 20px;
    cursor: pointer;
    z-index: 2005; /* Above Game Over overlay */
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    transition: background 0.2s;
}

.sound-toggle-btn:hover {
    background: rgba(0, 0, 0, 0.8);
}

.settings-backdrop {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    z-index: 199;
    background: transparent;
}

.sound-settings-overlay {
    position: absolute;
    top: 40px;
    right: 5px;
    z-index: 1001;
}

.editor-controls button.active {
    order: 1;
    background: #4caf50;
    border-color: #4caf50;
}

.editor-controls button:disabled {
    opacity: 0.5;
    cursor: not-allowed;
}

.selected-info {
    color: #aaa;
    font-size: 12px;
    text-align: center;
}

.edit-buttons {
    display: flex;
    gap: 8px;
    margin-top: 5px;
}

.loading-placeholder {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: radial-gradient(circle at center, #1a1a1a 0%, #000 100%);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #888;
  font-family: 'Segoe UI', sans-serif;
  z-index: 50;
  backdrop-filter: blur(10px);
}

.spinner {
  width: 60px;
  height: 60px;
  border: 4px solid rgba(255, 255, 255, 0.1);
  border-top: 4px solid #4caf50;
  border-right: 4px solid #2e7d32;
  border-radius: 50%;
  animation: spin 1s cubic-bezier(0.68, -0.55, 0.27, 1.55) infinite;
  margin-bottom: 20px;
  box-shadow: 0 0 15px rgba(76, 175, 80, 0.5);
}

.loading-text {
  font-size: 1.5em;
  font-weight: 800;
  letter-spacing: 4px;
  text-transform: uppercase;
  background: linear-gradient(90deg, #4caf50, #81c784, #4caf50);
  background-clip: text;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  animation: shimmer 2s infinite linear;
}

@keyframes shimmer {
  0% { background-position: -200% center; }
  100% { background-position: 200% center; }
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

@keyframes pulse-text {
  from { opacity: 0.6; }
  to { opacity: 1; }
}


.overlay-screen {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  z-index: 3000; /* Base z-index for overlays */
  pointer-events: none; /* Let clicks pass through if needed */
}

/* Training Overlay - Highest priority */
.training-overlay {
  background: rgba(0, 0, 0, 0.7);
  color: white;
  z-index: 3100; /* Above Game Over */
}

.tilted-overlay {
  background: rgba(255, 0, 0, 0.3);
  color: #ff3333;
  text-shadow: 0 0 10px #ff0000;
  animation: shake 0.3s infinite;
}

.tilted-overlay h1 {
  font-size: 5em;
  font-weight: 900;
  transform: rotate(-10deg);
  border: 4px solid #ff3333;
  padding: 10px 40px;
  background: rgba(0,0,0,0.8);
}

.game-over-overlay {
  background: rgba(0, 0, 0, 0.85);
  color: white;
  pointer-events: auto;
}

.game-over-overlay h1 {
  font-size: 4em;
  color: #ff5555;
  margin-bottom: 20px;
  text-shadow: 0 0 20px rgba(255, 0, 0, 0.5);
  animation: blink 1s infinite;
}

@keyframes shake {
  0% { transform: translate(1px, 1px) rotate(0deg); }
  10% { transform: translate(-1px, -2px) rotate(-1deg); }
  20% { transform: translate(-3px, 0px) rotate(1deg); }
  30% { transform: translate(3px, 2px) rotate(0deg); }
  40% { transform: translate(1px, -1px) rotate(1deg); }
  50% { transform: translate(-1px, 2px) rotate(-1deg); }
  60% { transform: translate(-3px, 1px) rotate(0deg); }
  70% { transform: translate(3px, 1px) rotate(-1deg); }
  80% { transform: translate(-1px, -1px) rotate(1deg); }
  90% { transform: translate(1px, 2px) rotate(0deg); }
  100% { transform: translate(1px, -2px) rotate(-1deg); }
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.game-over-overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.85);
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  z-index: 3000;
  animation: fadeIn 0.5s ease-out;
}

.game-over-text {
  font-size: 4rem;
  font-weight: 900;
  color: #ff3333;
  text-shadow: 0 0 20px rgba(255, 0, 0, 0.5);
  margin-bottom: 20px;
  animation: pulse 2s infinite;
}

.high-score-text {
  font-size: 3rem;
  font-weight: 800;
  color: #FFD700;
  text-shadow: 0 0 20px rgba(255, 215, 0, 0.8), 0 0 40px rgba(255, 100, 0, 0.5);
  margin-bottom: 20px;
  animation: pulse 1s infinite alternate;
}

.final-score {
  font-size: 2.5rem;
  color: #ffffff;
  font-family: 'Courier New', monospace;
  text-shadow: 0 0 10px rgba(255, 255, 255, 0.3);
}

/* Fullscreen Optimizations */
.game-over-overlay.is-fullscreen .game-over-text {
  font-size: 8rem;
  margin-bottom: 40px;
  text-shadow: 0 0 40px rgba(255, 0, 0, 0.8);
}

.game-over-overlay.is-fullscreen .high-score-text {
  font-size: 6rem;
  margin-bottom: 40px;
  text-shadow: 0 0 40px rgba(255, 215, 0, 1), 0 0 80px rgba(255, 100, 0, 0.8);
}

.game-over-overlay.is-fullscreen .final-score {
  font-size: 5rem;
  text-shadow: 0 0 20px rgba(255, 255, 255, 0.5);
}


@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes pulse {
  0% { transform: scale(1); }
  50% { transform: scale(1.05); }
  100% { transform: scale(1); }
}

/* High Score Table Styles */
.high-score-table-container {
    margin-top: 20px;
    background: rgba(0, 0, 0, 0.4);
    border-radius: 12px;
    padding: 15px;
    backdrop-filter: blur(5px);
    border: 1px solid rgba(255, 255, 255, 0.1);
    max-height: 40vh;
    overflow-y: auto;
    width: 90%;
}

.high-score-table {
    width: 100%;
    border-collapse: collapse;
    color: #eee;
    font-family: 'Roboto Mono', monospace;
    font-size: 0.9em;
}

.high-score-table th {
    text-align: left;
    padding: 8px;
    border-bottom: 2px solid rgba(255, 255, 255, 0.2);
    color: #4caf50;
    text-transform: uppercase;
    font-size: 0.8em;
    letter-spacing: 1px;
}

.high-score-table td {
    padding: 8px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.high-score-table tr.highlight {
    background: rgba(76, 175, 80, 0.2);
    color: #fff;
    font-weight: bold;
    animation: flash 2s infinite;
}

@keyframes flash {
    0%, 100% { background: rgba(76, 175, 80, 0.2); }
    50% { background: rgba(76, 175, 80, 0.5); }
}

.model-name-truncate {
    max-width: 150px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    display: block; /* Ensure it respects width */
}

/* Scrollbar for table */
.high-score-table-container::-webkit-scrollbar {
    width: 6px;
}
.high-score-table-container::-webkit-scrollbar-track {
    background: rgba(0,0,0,0.1);
}
.high-score-table-container::-webkit-scrollbar-thumb {
    background: rgba(255,255,255,0.2);
    border-radius: 3px;
}

.close-overlay-container {
    margin-top: 20px;
}

.close-overlay-btn {
    background: rgba(255, 255, 255, 0.2);
    border: 1px solid rgba(255, 255, 255, 0.4);
    color: white;
    padding: 10px 20px;
    font-size: 1.2rem;
    cursor: pointer;
    border-radius: 5px;
    transition: background 0.2s;
}

.close-overlay-btn:hover {
    background: rgba(255, 255, 255, 0.4);
}
</style>
