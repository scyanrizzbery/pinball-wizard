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
            :railGlowIntensity="railGlowIntensity"
            :railGlowRadius="railGlowRadius"
            @update-smoke-intensity="(val: number) => smokeIntensity = val"
            @update-rail-glow="(val: number) => railGlowIntensity = val"
            @update-rail-glow-radius="(val: number) => railGlowRadius = val"
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

    <!-- Matrix Intro Overlay -->
    <div v-if="matrixIntroVisible" class="matrix-intro-overlay" :class="{ 'is-fullscreen': isOverlayFullscreen }">
        
        <!-- Terminal / Glitch Mode -->
        <div v-if="currentFailScreen === 'terminal'" class="matrix-terminal">
            <div v-for="(line, i) in matrixTerminalLines" :key="i" class="terminal-line" :class="{ 'glitch-text': matrixGlitchActive }">
                {{ line }}
            </div>
        </div>

        <!-- BSOD Mode -->
        <div v-else-if="currentFailScreen === 'bsod'" class="bsod-screen">
            <div class="bsod-content">
                <p class="bsod-header">A fatal exception 0E has occurred at 0028:C0034B23 in VXD VMM(01) + 000034B23. The current application will be terminated.</p>
                <p>Press any key to terminate the current application.</p>
                <p>Press CTRL+ALT+DEL again to restart your computer. You will lose any unsaved information in all applications.</p>
            </div>
        </div>

        <!-- Red Hat Mode -->
        <div v-else-if="currentFailScreen === 'redhat'" class="linux-screen">
            <div class="linux-content">
                <p>Red Hat Linux release 9 (Shrike)</p>
                <p>Kernel 2.4.20-8 on an i686</p>
                <br>
                <p>[<span style="color: #00ff00">OK</span>] Mounting local filesystems: </p>
                <p>[<span style="color: #00ff00">OK</span>] Checking root filesystem</p>
                <p>[<span style="color: #ff0000">FAILED</span>] Mounting /proc filesystem</p>
                <p>INIT: Switching to runlevel: 3</p>
                <p>INIT: Sending processes the TERM signal</p>
                <p>Kernel panic - not syncing: Attempted to kill init!</p>
            </div>
        </div>

        <!-- BSD Mode -->
        <div v-else-if="currentFailScreen === 'bsd'" class="linux-screen">
            <div class="linux-content">
                <p>FreeBSD/amd64 Bootstrap Loader, Revision 1.1</p>
                <p>Loading /boot/defaults/loader.conf</p>
                <p>/boot/kernel/kernel text=0x13c36f0 data=0x156eb8 syms=[0x8+0x1406c8+0x8+0x15da49]</p>
                <br>
                <p>Fatal trap 12: page fault while in kernel mode</p>
                <p>cpuid = 0; apic id = 00</p>
                <p>fault virtual address = 0xdeadbeef</p>
                <p>fault code = supervisor read data, page not present</p>
                <p>instruction pointer = 0x20:0xc095f333</p>
                <p>stack pointer = 0x28:0xe6c34b68</p>
                <p>Automatic reboot in 15 seconds - press a key on the console to abort</p>
            </div>
        </div>

    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, computed, nextTick } from 'vue'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import SoundManager from '../utils/SoundManager'
import GameSettings from './GameSettings.vue'
import { MatrixShader } from '../utils/MatrixShader'
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
    forceMatrix?: boolean;
}>(), {
    cameraMode: 'perspective',
    autoStartEnabled: false,
    showFlipperZones: false,
    connectionError: false,
    isFullscreen: false
})

// Safe Theme Detection (Computed)
// Prevents mutation of props.config and avoids state leakage between layouts
const currentTheme = computed(() => {
    if (!props.config) return null
    
    // 1. Explicit theme in config (if backend provided it)
    if (props.config.theme) return props.config.theme
    
    // 2. Fallback: Auto-detect from layout ID/Name
    let layoutId = props.config.current_layout_id
    if (!layoutId && props.config.name) {
        layoutId = props.config.name.toLowerCase().replace(/ /g, '_')
    }
    
    if (layoutId && (layoutId.includes('mario') || layoutId === 'super_mario')) {
        return 'mario'
    }
    
    return null
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
const floorMesh = ref<THREE.Mesh | null>(null)
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
let railsGroup: THREE.Group
let ballGeo: THREE.SphereGeometry, ballMat: THREE.MeshStandardMaterial
let zoneMeshes: THREE.Mesh[] = [] // Store zone meshes for show/hide

// Ball effects for combo-based visuals
let ballGlows: any[] = []
let ballTrails: { mesh: THREE.Mesh, positions: THREE.Vector3[] }[] = [] // { mesh: THREE.Mesh, positions: THREE.Vector3[] }
let ballParticles: any[] = []
let mushrooms: any[] = [] // Active mushroom power-ups

// Physics Config (to sync dimensions)
let physicsConfig = ref<PhysicsConfig | null>(null)
// Store previous flipper values for change detection (not reactive)
let lastFlipperValues = {
    length: null as number | null,
    width: null as number | null,
    tipWidth: null as number | null
}
const cameraDebug = ref({ x: 0, y: 0, z: 0 })
// Shared Materials
const sharedRailGlowMat = new THREE.MeshBasicMaterial({
    color: 0x00ffff, // Pure Cyan Glow
    transparent: true,
    opacity: 0.6, // Default (1.5 intensity -> 0.6 opacity)
    blending: THREE.AdditiveBlending,
    depthWrite: false,
    side: THREE.FrontSide
})

const sharedRailCoreMat = new THREE.MeshBasicMaterial({
    color: 0xffffff,
})

const showDebug = ref(false)
const showSettings = ref(false)
const smokeIntensity = ref(0.5)
const railGlowIntensity = ref(1.5) // Default high glow
const railGlowRadius = ref(0.5) // Default moderate radius

const updateRailMaterial = () => {
    // scale opacity by radius to prevent "super bright tight lines"
    // Heuristic: As radius gets smaller, we lower opacity to soften it.
    // As radius gets bigger, we increase opacity (up to a limit) to keep it visible.
    
    // Formula: Intensity is the main dial (0-10).
    // Radius (0-1.5) scales the density.
    
    // Base opacity from intensity (0-10 mapped to 0-0.8)
    let baseOp = railGlowIntensity.value * 0.08
    
    // Radius factor: If radius is small (<0.5), dampen heavily.
    // If radius is large (>1.0), boost slightly or keep flat.
    // Let's use linear scaling for simplicity: 
    // effective_opacity = baseOp * radius
    // Normalized to 1.0 radius being "standard".
    
    const radiusFactor = Math.max(0.2, railGlowRadius.value) // Clamp min to avoid 0 opacity if radius is tiny but non-zero
    
    sharedRailGlowMat.opacity = Math.min(1.0, baseOp * radiusFactor)
}

watch(railGlowIntensity, updateRailMaterial)
watch(railGlowRadius, (newVal) => {
    updateRailMaterial()
    if (props.config && props.config.rails) {
        createRails(props.config.rails)
    }
})

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

// Watch for Score/Ball updates to update 3D Scoreboard
watch(() => props.stats, (newStats) => {
    if (!newStats || !tableGroup || !tableGroup.userData.updateScoreboard) return
    
    // Call the update function stored on the mesh user data
    // Use balls_remaining if available, else balls (lives)
    const ballCount = newStats.balls_remaining !== undefined ? newStats.balls_remaining : (newStats.balls || 0)
    tableGroup.userData.updateScoreboard(newStats.score || 0, ballCount, newStats.high_score || 0)
}, { deep: true })

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

const getMushroomTexture = () => {
    const canvas = document.createElement('canvas')
    canvas.width = 64
    canvas.height = 64
    const ctx = canvas.getContext('2d')
    if (!ctx) return new THREE.CanvasTexture(canvas)

    // Background (Transparent)
    ctx.clearRect(0, 0, 64, 64)

    // Stalk (White/Tan)
    ctx.fillStyle = '#f8dcb4' 
    ctx.beginPath()
    ctx.roundRect(22, 32, 20, 30, 5)
    ctx.fill()
    // Eyes
    ctx.fillStyle = '#000000'
    ctx.fillRect(26, 38, 4, 8)
    ctx.fillRect(34, 38, 4, 8)

    // Cap (Red) - Semi-circle
    ctx.fillStyle = '#e60012'
    ctx.beginPath()
    ctx.arc(32, 32, 28, Math.PI, 0) // Top half
    ctx.fill()
    
    // Spots (White)
    ctx.fillStyle = '#ffffff'
    // Top Middle
    ctx.beginPath()
    ctx.arc(32, 16, 8, 0, Math.PI * 2)
    ctx.fill()
    // Left Side
    ctx.beginPath()
    ctx.arc(8, 36, 8, 0, Math.PI * 2)
    ctx.fill()
    // Right Side
    ctx.beginPath()
    ctx.arc(56, 36, 8, 0, Math.PI * 2)
    ctx.fill()

    const texture = new THREE.CanvasTexture(canvas)
    // Pixel Art settings
    texture.magFilter = THREE.NearestFilter
    texture.minFilter = THREE.NearestFilter
    texture.colorSpace = THREE.SRGBColorSpace
    return texture
  }

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
const dragState: { 
    initialP1: Point | null, 
    initialP2: Point | null, 
    initialC1: Point | null, 
    initialC2: Point | null, 
    initialPos: Point | null 
} = { 
    initialP1: null, 
    initialP2: null, 
    initialC1: null, 
    initialC2: null, 
    initialPos: null 
}
const connectedDragStates = new Map<number, any>()
const connectedDragIndices = ref<number[]>([])

const findConnectedRails = (rootIndex: number): number[] => {
    if (!props.config.rails) return [rootIndex]
    
    const visited = new Set<number>()
    const queue = [rootIndex]
    visited.add(rootIndex)
    
    const isConn = (p1: Point, p2: Point) => {
        const dx = p1.x - p2.x
        const dy = p1.y - p2.y
        return (dx*dx + dy*dy) < 0.0001 // ~0.01 unit threshold distance
    }
    
    while (queue.length > 0) {
        const currIdx = queue.shift()!
        const curr = props.config.rails[currIdx]
        if (!curr) continue
        
        props.config.rails.forEach((other, idx) => {
            if (visited.has(idx)) return
            
            // Check all 4 combos of endpoints
            if (isConn(curr.p1, other.p1) || isConn(curr.p1, other.p2) ||
                isConn(curr.p2, other.p1) || isConn(curr.p2, other.p2)) {
                visited.add(idx)
                queue.push(idx)
            }
        })
    }
    
    return Array.from(visited)
}

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

const addCurve = () => {
    // Add a curved rail (Bézier)
    const newRail = {
        p1: { x: 0.3, y: 0.3 },
        p2: { x: 0.7, y: 0.7 },
        c1: { x: 0.3, y: 0.6 }, // Control Point 1
        c2: { x: 0.7, y: 0.4 }  // Control Point 2
    }
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
        
        const createHandle = (pos: {x: number, y: number}, pointName: string, color: number = 0x00ff00) => {
            const geometry = new THREE.SphereGeometry(0.02, 16, 16)
            const material = new THREE.MeshBasicMaterial({ 
                color: index === selectedRailIndex.value ? 0xff0000 : color 
            })
            const mesh = new THREE.Mesh(geometry, material)
            mesh.position.set(pos.x, pos.y, 0.05) // Slightly above rail
            mesh.userData = { railIndex: index, point: pointName, isHandle: true }
            scene.add(mesh)
            railHandles.push(mesh)
            return mesh
        }
        
        createHandle(p1, 'p1')
        createHandle(p2, 'p2')

        // If curved, add control point handles and guide lines
        if (rail.c1 && rail.c2) {
             const c1 = mapToWorld(rail.c1.x, rail.c1.y)
             const c2 = mapToWorld(rail.c2.x, rail.c2.y)
             
             createHandle(c1, 'c1', 0x00ffff) // Cyan for controls
             createHandle(c2, 'c2', 0x00ffff)
             
             // Draw Guide Lines (P1->C1, P2->C2)
             const material = new THREE.LineBasicMaterial({ color: 0x555555, depthTest: false })
             
             // P1 -> C1
             const points1 = [new THREE.Vector3(p1.x, p1.y, 0.05), new THREE.Vector3(c1.x, c1.y, 0.05)]
             const geo1 = new THREE.BufferGeometry().setFromPoints(points1)
             const line1 = new THREE.Line(geo1, material)
             line1.userData = { railIndex: index, point: 'guide', isHandle: false }
             scene.add(line1)
             railHandles.push(line1 as any)

             // P2 -> C2
             const points2 = [new THREE.Vector3(p2.x, p2.y, 0.05), new THREE.Vector3(c2.x, c2.y, 0.05)]
             const geo2 = new THREE.BufferGeometry().setFromPoints(points2)
             const line2 = new THREE.Line(geo2, material)
             line2.userData = { railIndex: index, point: 'guide', isHandle: false }
             scene.add(line2)
             railHandles.push(line2 as any)
        } else {
             // Straight rail: Add Midpoint Handle for creating curves
             const midX = (p1.x + p2.x) / 2
             const midY = (p1.y + p2.y) / 2
             
             // Handle for Midpoint
             const geometry = new THREE.SphereGeometry(0.015, 16, 16) // Slightly smaller
             const material = new THREE.MeshBasicMaterial({ color: 0xffff00 }) // Yellow
             const mesh = new THREE.Mesh(geometry, material)
             mesh.position.set(midX, midY, 0.05)
             mesh.userData = { railIndex: index, point: 'midpoint', isHandle: true }
             
             scene.add(mesh)
             railHandles.push(mesh)
        }

        // --- Add (+) Segment Handles (Only for Selected Rail) ---
        if (index === selectedRailIndex.value) {
            // Helper to create icon handle
            const createIconHandle = (pos: {x: number, y: number}, type: 'plus' | 'minus') => {
                const group = new THREE.Group()
                group.position.set(pos.x, pos.y, 0.05)
                
                // Background Sphere
                // Background Button (Cylinder/Coin) for better Icon alignment
                const bgGeo = new THREE.CylinderGeometry(0.012, 0.012, 0.005, 32)
                const color = type === 'plus' ? 0x0088ff : 0xff0000 
                const bgMat = new THREE.MeshBasicMaterial({ color: color })
                const bgMesh = new THREE.Mesh(bgGeo, bgMat)
                bgMesh.rotation.x = Math.PI / 2
                group.add(bgMesh)
                
                // Icon Geometry (White) - Place on top of cylinder face
                const iconMat = new THREE.MeshBasicMaterial({ color: 0xffffff })
                // Cylinder half-height is 0.0025. Place slightly above.
                const iconZ = 0.003
                
                if (type === 'plus') {
                    // Horizontal bar
                    const hBar = new THREE.Mesh(new THREE.BoxGeometry(0.016, 0.004, 0.002), iconMat)
                    hBar.position.z = iconZ
                    group.add(hBar)
                    // Vertical bar
                    const vBar = new THREE.Mesh(new THREE.BoxGeometry(0.004, 0.016, 0.002), iconMat)
                    vBar.position.z = iconZ
                    group.add(vBar)
                } else {
                    // Minus: Horizontal bar
                    const hBar = new THREE.Mesh(new THREE.BoxGeometry(0.016, 0.004, 0.002), iconMat)
                    hBar.position.z = iconZ
                    group.add(hBar)
                }
                
                scene.add(group)
                
                // Important: Add GROUP to railHandles for cleanup (scene.remove)
                railHandles.push(group as any)
                
                return group
            }

            const createPlusHandle = (pos: {x: number, y: number}, endType: 'p1' | 'p2') => {
                 // Calculate direction for placement
                 // Simply place them "outwards" from the endpoints
                 // D = P2 - P1 (direction of rail)
                 const dx = p2.x - p1.x
                 const dy = p2.y - p1.y
                 const len = Math.sqrt(dx*dx + dy*dy) || 1
                 const udx = dx / len
                 const udy = dy / len
                 
                 // Offset: 0.05 units away
                 const offset = 0.05
                 
                 const hx = endType === 'p2' ? pos.x + udx * offset : pos.x - udx * offset
                 const hy = endType === 'p2' ? pos.y + udy * offset : pos.y - udy * offset
                 
                 const group = createIconHandle({x: hx, y: hy}, 'plus')
                 
                 // Apply userData to all children and add them to raycast list
                 const handleType = endType === 'p2' ? 'add_segment_p2' : 'add_segment_p1'
                 const uData = { railIndex: index, point: handleType, isHandle: true }
                 
                 group.userData = uData 
                 group.children.forEach(child => {
                     child.userData = uData
                     railHandles.push(child as THREE.Mesh)
                 })
            }
            createPlusHandle(p1, 'p1')
            createPlusHandle(p2, 'p2')

            // --- Add (-) Delete Handle ---
            // Place near midpoint
            const mx = (p1.x + p2.x) / 2
            const my = (p1.y + p2.y) / 2
            
            // Offset perpendicular to rail direction
            const dx = p2.x - p1.x
            const dy = p2.y - p1.y
            const len = Math.sqrt(dx*dx + dy*dy) || 1
            const nx = -dy / len
            const ny = dx / len
            
            const rx = mx + nx * 0.04
            const ry = my + ny * 0.04
            

            
            const group = createIconHandle({x: rx, y: ry}, 'minus')
            const uData = { railIndex: index, point: 'remove_rail', isHandle: true }
            
            group.children.forEach(child => {
                 child.userData = uData
                 railHandles.push(child as THREE.Mesh)
            })
        }
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

// Helper to update visual mesh for a rail after data change
const updateRailVisuals = (index: number) => {
    const rail = props.config.rails[index]
    const railMesh = railMeshes[index]
    if (!rail || !railMesh) return

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
    
    if (rail.c1 && rail.c2) {
        // --- CURVED RAIL UPDATE ---
        const c1x = mapX(rail.c1.x + nOffsetX)
        const c1y = mapY(rail.c1.y + nOffsetY)
        const c2x = mapX(rail.c2.x + nOffsetX)
        const c2y = mapY(rail.c2.y + nOffsetY)
        
        const curve = new THREE.CubicBezierCurve3(
            new THREE.Vector3(x1, y1, 0.02), // railHeight/2 (0.04/2)
            new THREE.Vector3(c1x, c1y, 0.02),
            new THREE.Vector3(c2x, c2y, 0.02),
            new THREE.Vector3(x2, y2, 0.02)
        )
        
        // Update Geometry
        if (railMesh.geometry) railMesh.geometry.dispose()
        railMesh.geometry = new THREE.TubeGeometry(curve, 20, 0.008, 8, false)
        
        // Reset position/rotation (Tube is absolute coords)
        railMesh.position.set(0, 0, 0)
        railMesh.rotation.set(0, 0, 0)

    } else {
        // --- STRAIGHT RAIL UPDATE ---
        railMesh.position.set((x1 + x2) / 2, (y1 + y2) / 2, railMesh.position.z)
        railMesh.rotation.z = Math.atan2(y2 - y1, x2 - x1)
        
        // Update Scale X to match new length (since we rotated geometry Z 90deg, X is length)
        // We need initial length or just assume geometry was unit? 
        // No, geometry has fixed length.
        if ((railMesh.geometry as any).parameters) {
             const initLen = (railMesh.geometry as any).parameters.height // Cylinder height is the length
             railMesh.scale.x = length / initLen
        }
    }
    
    // Update 2D Rail
    const rail2D = railMesh.userData.rail2D
    if (rail2D) {
       rail2D.position.set((x1 + x2) / 2, (y1 + y2) / 2, rail2D.position.z)
       rail2D.rotation.z = Math.atan2(y2 - y1, x2 - x1)
       if (rail2D.geometry.parameters) {
            const initLen2D = rail2D.geometry.parameters.width
            rail2D.scale.x = length / initLen2D
       }
    }
}

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
    // Check handles (points)
    // Filter out guide lines which are visual only
    const intersects = raycaster.intersectObjects(railHandles).filter(res => res.object.userData.point !== 'guide')
    
    if (intersects.length > 0) {
        const hit = intersects[0].object
        selectedRailIndex.value = hit.userData.railIndex
        selectedType.value = 'rail'
        selectedBumperIndex.value = -1
        
        // Check for "Remove Rail" handle
        if (hit.userData.point === 'remove_rail') {
            const idx = hit.userData.railIndex
            if (idx >= 0 && idx < props.config.rails.length) {
                const newRails = [...props.config.rails]
                newRails.splice(idx, 1)
                
                selectedRailIndex.value = -1 // Deselect
                selectedType.value = null
                
                emit('update-rail', newRails)
            }
            return
        }

        // Check for "Add Segment" handles
        if (hit.userData.point === 'add_segment_p1' || hit.userData.point === 'add_segment_p2') {
             // Create New Rail
             const parentRail = props.config.rails[hit.userData.railIndex]
             if (!parentRail) return
             
             // Offset for new segment (normalized coordinates)
             const newLen = 0.1
             
             let newRail;
             
             if (hit.userData.point === 'add_segment_p2') {
                 // Extend from P2 [P1 -> P2] -> [P2 -> P2+offset]
                 const dx = parentRail.p2.x - parentRail.p1.x
                 const dy = parentRail.p2.y - parentRail.p1.y
                 const len = Math.sqrt(dx*dx + dy*dy) || 1
                 const ux = dx/len
                 const uy = dy/len
                 
                 newRail = {
                     p1: { x: parentRail.p2.x, y: parentRail.p2.y },
                     p2: { x: parentRail.p2.x + ux * newLen, y: parentRail.p2.y + uy * newLen }
                 }
             } else {
                 // Extend from P1 [P1-offset -> P1] -> [P1 -> P2]
                 const dx = parentRail.p2.x - parentRail.p1.x
                 const dy = parentRail.p2.y - parentRail.p1.y
                 const len = Math.sqrt(dx*dx + dy*dy) || 1
                 const ux = dx/len
                 const uy = dy/len
                 
                 newRail = {
                     p1: { x: parentRail.p1.x - ux * newLen, y: parentRail.p1.y - uy * newLen },
                     p2: { x: parentRail.p1.x, y: parentRail.p1.y }
                 }
             }
             
             const newRails = [...props.config.rails, newRail]
             selectedRailIndex.value = newRails.length - 1
             selectedType.value = 'rail'
             emit('update-rail', newRails)
             return
        }

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
            if (rail) {
                // Initialize single rail drag state (for endpoints)
                dragState.initialP1 = { ...rail.p1 }
                dragState.initialP2 = { ...rail.p2 }
                if (rail.c1) dragState.initialC1 = { ...rail.c1 }
                if (rail.c2) dragState.initialC2 = { ...rail.c2 }
                
                // Clear connected drag state
                connectedDragIndices.value = []
                connectedDragStates.clear()
            } else {
                console.warn('[Pinball3D] Drag Start: Invalid rail index', selectedRailIndex.value)
                isDragging.value = false
                return
            }
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
        dragPlane.setFromNormalAndCoplanarPoint(new THREE.Vector3(0, 0, 1), bodyIntersects[0].point)
        const target = new THREE.Vector3()
        raycaster.ray.intersectPlane(dragPlane, target)
        
        if (target) {
            const norm = mapFromWorld(target.x, target.y)
            dragStartPos.x = norm.x
            dragStartPos.y = norm.y
            
            // --- CONNECTED RAIL LOGIC ---
            // Find connected rails
            const connected = findConnectedRails(selectedRailIndex.value)
            connectedDragIndices.value = connected
            connectedDragStates.clear()
            
            connected.forEach(idx => {
                const r = props.config.rails[idx]
                if (r) {
                    const state = {
                        p1: { ...r.p1 },
                        p2: { ...r.p2 },
                        c1: r.c1 ? { ...r.c1 } : null,
                        c2: r.c2 ? { ...r.c2 } : null
                    }
                    connectedDragStates.set(idx, state)
                }
            })
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
        if (selectedType.value === 'rail') {
            const rail = props.config.rails[selectedRailIndex.value]
            if (rail) {
                if (dragPoint.value === 'body') {
                    // --- MULTI RAIL DRAG ---
                    const dx = normPos.x - dragStartPos.x
                    const dy = normPos.y - dragStartPos.y
                    
                    connectedDragIndices.value.forEach(idx => {
                         const r = props.config.rails[idx]
                         const initState = connectedDragStates.get(idx)
                         if (r && initState) {
                             r.p1.x = initState.p1.x + dx
                             r.p1.y = initState.p1.y + dy
                             r.p2.x = initState.p2.x + dx
                             r.p2.y = initState.p2.y + dy
                             
                             if (r.c1 && initState.c1) {
                                 r.c1.x = initState.c1.x + dx
                                 r.c1.y = initState.c1.y + dy
                             }
                             if (r.c2 && initState.c2) {
                                 r.c2.x = initState.c2.x + dx
                                 r.c2.y = initState.c2.y + dy
                             }
                             updateRailVisuals(idx)
                         }
                    })

                } else if (dragPoint.value === 'midpoint') {
                    // Convert straight rail to curved rail
                    if (!rail.c1) rail.c1 = { x: normPos.x, y: normPos.y }
                    if (!rail.c2) rail.c2 = { x: normPos.x, y: normPos.y }
                    rail.c1.x = normPos.x; rail.c1.y = normPos.y; 
                    rail.c2.x = normPos.x; rail.c2.y = normPos.y; 
                    
                    updateRailVisuals(selectedRailIndex.value) 
                } else {
                    // Handle single point dragging
                    if (rail[dragPoint.value]) {
                        rail[dragPoint.value].x = normPos.x
                        rail[dragPoint.value].y = normPos.y
                        updateRailVisuals(selectedRailIndex.value)
                    }
                }
                
                updateRailHandles()
            }
        } else if (selectedType.value === 'bumper') {
            const bumper = props.config.bumpers[selectedBumperIndex.value]
            if (bumper && dragState.initialPos) {
                const dx = normPos.x - dragStartPos.x
                const dy = normPos.y - dragStartPos.y
                bumper.x = dragState.initialPos.x + dx
                bumper.y = dragState.initialPos.y + dy
                
                const mesh = bumperMeshes[selectedBumperIndex.value]
                if (mesh) {
                     // Recalc collision geometry visuals if needed? 
                     // Bumpers are groups, usually we assume model space 0,0 and move group.
                     const world = mapToWorld(bumper.x, bumper.y)
                     mesh.position.set(world.x, world.y, mesh.position.z)
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

// --- Mario Theme Textures ---
const getQuestionBlockTexture = () => {
    const canvas = document.createElement('canvas');
    canvas.width = 128;
    canvas.height = 128;
    const ctx = canvas.getContext('2d');
    if (!ctx) return new THREE.Texture();

    // Background (Gold/Orange)
    ctx.fillStyle = '#ffaa00';
    ctx.fillRect(0, 0, 128, 128);
    
    // Inner Box (Lighter)
    ctx.fillStyle = '#ffcc00';
    ctx.fillRect(8, 8, 112, 112);
    
    // Question Mark (Brown/Shadow)
    ctx.fillStyle = '#aa5500';
    ctx.font = 'bold 80px "Courier New", monospace';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText('?', 64, 64);
    
    // Bolts
    ctx.fillStyle = '#aa5500';
    ctx.fillRect(12, 12, 10, 10);
    ctx.fillRect(106, 12, 10, 10);
    ctx.fillRect(12, 106, 10, 10);
    ctx.fillRect(106, 106, 10, 10);

    const tex = new THREE.CanvasTexture(canvas);
    tex.colorSpace = THREE.SRGBColorSpace;
    return tex;
};

const getBrickBlockTexture = () => {
    const canvas = document.createElement('canvas');
    canvas.width = 128;
    canvas.height = 128;
    const ctx = canvas.getContext('2d');
    if (!ctx) return new THREE.Texture();

    // Base Brown
    ctx.fillStyle = '#b84e00'; // Darker Rust
    ctx.fillRect(0, 0, 128, 128);

    // Brick Pattern
    ctx.fillStyle = '#ff8822'; // Lighter Orange-Brown
    // Top Row
    ctx.fillRect(4, 4, 58, 28);
    ctx.fillRect(66, 4, 58, 28);
    // Middle Row
    ctx.fillRect(4, 36, 28, 28);
    ctx.fillRect(36, 36, 56, 28);
    ctx.fillRect(96, 36, 28, 28);
    // Bottom Row
    ctx.fillRect(4, 68, 58, 28);
    ctx.fillRect(66, 68, 58, 28);
    // Very Bottom
    ctx.fillRect(4, 100, 28, 24);
    ctx.fillRect(36, 100, 56, 24);
    ctx.fillRect(96, 100, 28, 24);

    // Mortar lines are the gaps left behind
    
    const tex = new THREE.CanvasTexture(canvas);
    tex.colorSpace = THREE.SRGBColorSpace;
    // Nearest filter for pixel look
    tex.minFilter = THREE.NearestFilter;
    tex.magFilter = THREE.NearestFilter;
    return tex;
};

const getKoopaShellTexture = () => {
    const canvas = document.createElement('canvas');
    canvas.width = 128;
    canvas.height = 128;
    const ctx = canvas.getContext('2d');
    if (!ctx) return new THREE.Texture();

    // Green Shell
    ctx.fillStyle = '#00aa00';
    ctx.fillRect(0, 0, 128, 128);
    
    // Hexagon plates pattern
    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 4;
    ctx.beginPath();
    ctx.moveTo(64, 10);
    ctx.lineTo(110, 40);
    ctx.lineTo(110, 88);
    ctx.lineTo(64, 118);
    ctx.lineTo(18, 88);
    ctx.lineTo(18, 40);
    ctx.closePath();
    ctx.stroke();
    
    // Center point
    ctx.beginPath();
    ctx.arc(64, 64, 5, 0, Math.PI*2);
    ctx.fillStyle = '#fff';
    ctx.fill();

    const tex = new THREE.CanvasTexture(canvas);
    tex.colorSpace = THREE.SRGBColorSpace;
    return tex;
};

const getCoinTexture = () => {
    const canvas = document.createElement('canvas');
    canvas.width = 64;
    canvas.height = 64;
    const ctx = canvas.getContext('2d');
    if (!ctx) return new THREE.Texture();

    // Gold Coin
    ctx.fillStyle = '#ffcc00';
    ctx.beginPath();
    ctx.ellipse(32, 32, 28, 30, 0, 0, Math.PI * 2);
    ctx.fill();
    
    // Shine / Highlight
    ctx.fillStyle = '#ffffaa';
    ctx.beginPath();
    ctx.ellipse(24, 24, 8, 12, -0.5, 0, Math.PI * 2);
    ctx.fill();
    
    // Border
    ctx.strokeStyle = '#aa5500';
    ctx.lineWidth = 4;
    ctx.beginPath();
    ctx.ellipse(32, 32, 28, 30, 0, 0, Math.PI * 2);
    ctx.stroke();

    // Inner Line
    ctx.strokeStyle = '#aa5500';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.ellipse(32, 32, 20, 22, 0, 0, Math.PI * 2);
    ctx.stroke();

    const tex = new THREE.CanvasTexture(canvas);
    tex.colorSpace = THREE.SRGBColorSpace;
    return tex;
};

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

    railsGroup = new THREE.Group()
    tableGroup.add(railsGroup)
  railMeshes.length = 0
  bumperMeshes.length = 0
  
  // Clear existing balls and flippers so they are recreated in the new group
  balls = []
  
  // Clear ball effects arrays
  ballGlows = []
  ballTrails = []
  ballParticles = []
  coins = [] // Clear coins

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


  // Coin Resources (Mario Theme)
  const coinTex = getCoinTexture()
  coinMat = new THREE.MeshBasicMaterial({ 
      map: coinTex,
      transparent: true,
      side: THREE.DoubleSide
  })
  
  flippers = { left: null, right: null, upper: [], dropTargets: [], bumpers: [] }
  zoneMeshes = [] // Clear zone meshes array

// Floor - Brighter playfield with Texture Support
  // Extended Floor to match Apron (Total Height 1.44)
  // Top: 0.6, Bottom: -0.84. Center: -0.12.
  // Determine layout ID for texture lookup
  let layoutId = null
  if (config) {
      if (config.current_layout_id) {
          layoutId = config.current_layout_id
      } else if (config.name) {
          layoutId = config.name.toLowerCase().replace(/ /g, '_')
      }
      
      // DEBUG: Theme State
      console.log('[createTable] Theme:', config.theme)
      console.log('[createTable] Layout ID:', layoutId)
      
      // Fallback: Force Mario theme if layout seems to be Mario
      // Also check config.theme here to set isMario correctly
  }

  // Use computed theme to avoid mutation and leakage
  const isMario = currentTheme.value === 'mario'

  // Floor Geometry
  // Standard Extended: Top: 0.6, Bottom: -0.84. Center: -0.12. Height: 1.44
  // Mario Fixed: Top: 0.6, Bottom: -0.6 (Playfield only) + Separate Apron
  let floorGeo
  let floorY
  
  if (isMario) {
      // Shorter floor, stops at apron bar
      floorGeo = new THREE.PlaneGeometry(0.6, 1.2)
      floorY = 0
  } else {
      // Standard extended floor
      floorGeo = new THREE.PlaneGeometry(0.6, 1.44)
      floorY = -0.12
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

      // Adjust texture repeat to cover new longer floor correctly?
      // Usually texture is designed for playfield (1.2 height).
      // If we stretch it to 1.44, it might distort.
      // But usually apron covers the bottom part.
      
      // Fix for Close Encounters: The generated image is practically square (1:1) but the table is 1:2.4.
      // This causes the art to look squished horizontally (tall/thin).
      // We need to "zoom in" horizontally by showing only a slice of the texture width.
      // If we show 0.5 of the texture width mapped to the full table width, the pixels appear 2x wider.
      if (layoutId === 'close_encounters') {
          // Center the texture
          texture.center.set(0.5, 0.5)
          // Scale it.
          // repeat.x < 1 zooms in horizontally (stretches horizontal pixels).
          // repeat.y = 1 keeps vertical as is.
          texture.repeat.set(0.6, 1.0) 
          // 0.6 is a guess. If image is 1:1 and table is 1:2 ~ 0.5 ratio
      }

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
  floorMesh.value = floor
  floor.receiveShadow = true
  // FIX Z-FIGHTING: Raise floor slightly above cabinet top (which is at Z=0)
  floor.position.set(0, floorY, 0.005) 
  tableGroup.add(floor)

  // Mario Special: Add Black Apron Mesh if needed
  if (isMario) {
      const apronGeo = new THREE.PlaneGeometry(0.6, 0.24)
      const apronMat = new THREE.MeshBasicMaterial({ color: 0x000000 })
      const apron = new THREE.Mesh(apronGeo, apronMat)
      // Center at -0.72 (Start -0.6, End -0.84)
      apron.position.set(0, -0.72, 0.005)
      tableGroup.add(apron)
  }

  // Walls - Brushed Metal Texture
  // Walls - Dynamic or Default Brushed Metal
  let wallTexturePath = '/textures/wall_texture.png'
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
  
  // Adjusted Walls to wrap around extended Apron
  // Table Top Y = 0.6  (mapY(0.0))
  // Table Bottom Y = -0.84 (mapY(1.2)) -> Length 1.44
  // Center Y = (0.6 + -0.84) / 2 = -0.12
  const wallLength = 1.44
  const wallCenterY = -0.12

  // Left Wall
  const w1 = new THREE.Mesh(new THREE.BoxGeometry(0.02, wallLength, wallHeight), wallMat)
  w1.position.set(-0.31, wallCenterY, wallHeight/2)
  tableGroup.add(w1)
  
  // Right Wall
  const w2 = new THREE.Mesh(new THREE.BoxGeometry(0.02, wallLength, wallHeight), wallMat)
  w2.position.set(0.31, wallCenterY, wallHeight/2)
  tableGroup.add(w2)
  
  // Top Wall
  const w3 = new THREE.Mesh(new THREE.BoxGeometry(0.64, 0.02, wallHeight), wallMat)
  w3.position.set(0, 0.61, wallHeight/2)
  tableGroup.add(w3)

  // Bottom Wall (Completing the perimeter)
  // Side walls end at -0.84. Center this at -0.85 (0.02 thick) to cap.
  const w4 = new THREE.Mesh(new THREE.BoxGeometry(0.64, 0.02, wallHeight), wallMat)
  w4.position.set(0, -0.85, wallHeight/2)
  tableGroup.add(w4)

  // --- Deep Cabinet (Main Body) ---
  // A large box below the playfield to give it weight and realism.
  // Dimensions match the full outer perimeter (Walls + Floor).
  // Width: 0.64 (0.6 floor + 0.02*2 walls)
  // Length: 1.48 (1.44 floor + 0.02*2 walls)
  // Depth: 1/4 of previous (0.5 / 4 = 0.125)
  // Material: Same as walls
  
  const cabinetHeight = 0.125
  const cabinetGeo = new THREE.BoxGeometry(0.64, 1.48, cabinetHeight)
  
  // Use plain black material for Cabinet and Backbox (User requested no texture)
  const cabinetMat = new THREE.MeshStandardMaterial({
      color: 0x050505, // Almost black
      roughness: 0.8,
      metalness: 0.1
      // No map
  })
  
  const cabinet = new THREE.Mesh(cabinetGeo, cabinetMat)
  
  // Floor is at Z=0. Cabinet top should be at Z=0.
  // So Center Z = -cabinetHeight / 2
  
  cabinet.position.set(0, -0.12, -cabinetHeight / 2)
  tableGroup.add(cabinet)

  // --- Wedge Head Backbox ---
  // Sitting at the back of the machine, standing up.
  // Inverted Trapezoid: Wider at top.
  // Bottom Width: 0.65 (slightly wider than cabinet)
  // Top Width: 0.75
  // Height: 0.7 * (2/3) ≈ 0.47
  // Depth: 0.25 (thickness)
  
  const bbShape = new THREE.Shape()
  const bbBottomW = 0.65 / 2
  const bbTopW = 0.75 / 2
  const bbH = 0.56 // Increased height (~20%)
  
  // Draw Trapezoid (Front Face)
  bbShape.moveTo(-bbBottomW, 0)
  bbShape.lineTo(bbBottomW, 0)
  bbShape.lineTo(bbTopW, bbH)
  bbShape.lineTo(-bbTopW, bbH)
  bbShape.lineTo(-bbBottomW, 0)
  
  const bbGeo = new THREE.ExtrudeGeometry(bbShape, {
      depth: 0.25,
      bevelEnabled: true,
      bevelThickness: 0.01,
      bevelSize: 0.01,
      bevelSegments: 2
  })
  
  const bbMesh = new THREE.Mesh(bbGeo, cabinetMat) // Use plain black
  
  // Correction: UP (+Z) and Tilt Back (+Y)
  bbMesh.rotation.x = Math.PI / 2 - 0.1 
  
  // Position
  // Origin (Z=0) is Back. End (Z=depth) is Front.
  // Front Face approx Y=0.62.
  // Origin Y = 0.62 + depth.
  // Raise Z to 0.1 to sit on top of walls (Flush with cabinet "rails").
  
  bbMesh.position.set(0, 0.62 + 0.25, 0.1)
  tableGroup.add(bbMesh)
  
  // --- ScoreBoard Texture Logic ---
  const sbCanvas = document.createElement('canvas')
  sbCanvas.width = 512
  sbCanvas.height = 256
  const sbCtx = sbCanvas.getContext('2d')
  const sbTexture = new THREE.CanvasTexture(sbCanvas)
  sbTexture.colorSpace = THREE.SRGBColorSpace

  let backglassImage = null
  // layoutId is already defined at top of createTable

  if (config) {
      if (config.current_layout_id) {
          layoutId = config.current_layout_id
      } else if (config.name) {
          layoutId = config.name.toLowerCase().replace(/ /g, '_')
      }
      console.log('DEBUG: Backglass Logic - Config name:', config.name, 'Layout ID:', layoutId)
  }

  if (layoutId) {
       const img = new Image()
       const url = `/textures/${layoutId}_backglass.png`
       console.log('DEBUG: Attempting to load backglass:', url)
       img.src = url
       img.onload = () => {
           console.log(`DEBUG: SUCCESS Loaded backglass for: ${layoutId}`)
           backglassImage = img
           drawScoreboard(props.stats?.score || 0, props.stats?.balls || 3, props.stats?.high_score || 0)
       }
       img.onerror = (e) => {
           console.error(`DEBUG: FAILED to load backglass for: ${layoutId}`, e)
       }
  }

  const drawScoreboard = (score: number, ball: number, highScore: number = 0) => {
      if (!sbCtx) return
      
      // Background
      if (backglassImage) {
          try {
            sbCtx.drawImage(backglassImage, 0, 0, 512, 256)
            // Add semi-transparent overlay for readability if needed, 
            // or just rely on text shadow/boxes.
            // Let's add slight darken for text areas
          } catch (e) {
              sbCtx.fillStyle = '#000000' 
              sbCtx.fillRect(0, 0, 512, 256)
          }
      } else {
          sbCtx.fillStyle = '#000000' 
          sbCtx.fillRect(0, 0, 512, 256)
      }
      
      sbCtx.shadowColor = '#000000'
      sbCtx.shadowBlur = 4 // Sharper shadow for readability against art
      sbCtx.shadowOffsetX = 2
      sbCtx.shadowOffsetY = 2
      
      // --- Styled Text Helper ---
      const drawDigitalText = (label, value, x, y, width = 180, align = 'left', color = '#ffaa00') => {
          // Background Box dimensions
          const boxW = width
          const boxH = 60 // Significantly reduced height (was 80)
          
          let boxX = x
          if (align === 'right') boxX = x - boxW
          if (align === 'center') boxX = x - boxW / 2
          
          // Draw semi-transparent background "glass" for the display
          sbCtx.fillStyle = 'rgba(0, 0, 0, 0.5)' // Even more transparent
          sbCtx.strokeStyle = '#555'
          sbCtx.lineWidth = 1
          // Round rect simulation
          sbCtx.fillRect(boxX, y, boxW, boxH)
          sbCtx.strokeRect(boxX, y, boxW, boxH)
          
          sbCtx.textAlign = align === 'center' ? 'center' : 'left'
          if (align === 'right') sbCtx.textAlign = 'right'
          
          // Label
          sbCtx.shadowBlur = 0
          sbCtx.fillStyle = '#cc8800'
          sbCtx.font = 'bold 12px "Courier New", monospace' // Tiny label
          // Position relative to box
          let labelX = x + 10 
          if (align === 'right') labelX = x - 10
          if (align === 'center') labelX = x
          
          sbCtx.fillText(label, labelX, y + 18)
          
          // Value (Glowing Digital Look)
          sbCtx.shadowColor = color
          sbCtx.shadowBlur = 8 // tighter glow
          sbCtx.fillStyle = '#ffffff' // White core
          sbCtx.font = 'bold 28px "Courier New", monospace' // Much smaller value (was 36)
          
          let valX = x + 10
          if (align === 'right') valX = x - 10
          if (align === 'center') valX = x
          
          sbCtx.fillText(value, valX, y + 45)
      }

      // 1. Main Score - Top Left
      // Moved UP to 40. Box height 60 ends at 100.
      const scoreStr = Math.floor(score).toLocaleString()
      drawDigitalText("SCORE", scoreStr, 20, 40, 180, 'left', '#ffaa00')
      
      // 2. High Score - Bottom Left
      // Moved DOWN to 180. Box height 60 ends at 240.
      const highScoreStr = Math.floor(highScore).toLocaleString()
      drawDigitalText("HIGH SCORE", highScoreStr, 20, 180, 180, 'left', '#ff4400')
      
      // 3. Balls - Bottom Right
      // Moved DOWN to 180.
      const boxW = 120 // Smaller box
      const boxH = 60
      const bx = 370 // Shifted right
      const by = 180
      
      sbCtx.fillStyle = 'rgba(0, 0, 0, 0.5)'
      sbCtx.strokeStyle = '#555'
      sbCtx.lineWidth = 1
      sbCtx.fillRect(bx, by, boxW, boxH)
      sbCtx.strokeRect(bx, by, boxW, boxH)
      
      sbCtx.shadowBlur = 0
      sbCtx.fillStyle = '#cc8800'
      sbCtx.textAlign = 'center'
      sbCtx.font = 'bold 12px "Courier New", monospace'
      sbCtx.fillText("BALLS", bx + boxW/2, by + 18)
      
      // Ball Icons
      const ballRadius = 8 // Tiny balls
      const ballSpacing = 25
      // Center the balls in the box
      const totalW = (ball - 1) * ballSpacing
      const startX = bx + boxW/2 - totalW/2
      const startY = by + 40
      
      for (let i = 0; i < ball; i++) {
          sbCtx.shadowBlur = 3
          sbCtx.shadowColor = '#ffffff'
          sbCtx.beginPath()
          sbCtx.arc(startX + (i * ballSpacing), startY, ballRadius, 0, Math.PI * 2)
          sbCtx.fillStyle = '#e0e0e0' 
          sbCtx.fill()
          // Shine
          sbCtx.shadowBlur = 0
          sbCtx.beginPath()
          sbCtx.arc(startX + (i * ballSpacing) - 2, startY - 2, ballRadius/3, 0, Math.PI * 2)
          sbCtx.fillStyle = '#ffffff'
          sbCtx.fill()
      }
      
      // Force texture update
      sbTexture.needsUpdate = true
  }
  
  // Initial Draw
  drawScoreboard(0, 3, 0)
  
  // Force redraw after a moment to ensure fonts load
  setTimeout(() => drawScoreboard(0, 3, 0), 500)

  // Add Backglass (Dynamic Scoreboard)
  const glassGeo = new THREE.PlaneGeometry(0.65, 0.48) // Increased screen height
  
  // Use MeshBasicMaterial with DoubleSide for maximum visibility
  const glassMat = new THREE.MeshBasicMaterial({ 
      map: sbTexture,
      color: 0xffffff,
      side: THREE.DoubleSide
  })
  const glass = new THREE.Mesh(glassGeo, glassMat)
  glass.receiveShadow = false // Prevent shadow artifacts
  glass.castShadow = false
  
  // Position on the face
  bbMesh.add(glass)
  // bbMesh Extrusion depth is 0.25 (Front Face).
  // Increase gap to avoid Z-fighting/Moiré
  glass.position.set(0, bbH / 2, 0.27)

  // ADDED: Real Light Source for "Incandescent" feel
  // Reduced intensity to prevent glare on playfield
  const headLight = new THREE.PointLight(0xffaa00, 0.6, 2.0)
  headLight.position.set(0, bbH / 2, 0.5) 
  bbMesh.add(headLight)
  
  // --- Steel Legs ---
  // L-Bracket Legs extending to floor.
  // Floor assumed approx Z = -0.8 (75-80cm height)
  // Legs overlap cabinet corners.
  
  const legMat = new THREE.MeshStandardMaterial({
      color: 0xeeeeee,
      metalness: 1.0,
      roughness: 0.2
  })
  
  const legShape = new THREE.Shape()
  const legW = 0.06 // 6cm wide flange
  const legT = 0.004 // 4mm thick
  
  // "Inner Corner" at 0,0. Extends OUTWARDS.
  legShape.moveTo(0, 0)
  legShape.lineTo(legW, 0)
  legShape.lineTo(legW, legT)
  legShape.lineTo(legT, legT)
  legShape.lineTo(legT, legW)
  legShape.lineTo(0, legW)
  legShape.lineTo(0, 0)
  
  // Extrude length: 0.8m
  const legGeo = new THREE.ExtrudeGeometry(legShape, {
      depth: 0.8,
      bevelEnabled: false
  })
  
  // Helper to place leg
  const createLeg = (x: number, y: number, rotZ: number) => {
      const leg = new THREE.Mesh(legGeo, legMat)
      // Geometry is drawn in XY plane, depth in Z.
      // 0 to 0.8 Z.
      // We want Top of Leg at Z=0 (approx). Bottom at -0.8.
      // But Extrude goes 0 -> +depth.
      // So we rotate geometry or mesh? 
      // If we leave basic orientation:
      // Mesh at Z=-0.8. shape 0->0.8 goes slightly past 0?
      // Actually standard Extrude goes +Z.
      
      // We want leg to go DOWN.
      // If we put mesh at Z=0, it goes UP.
      // So Position at Z=-0.8. It goes UP to 0. Perfect.
      
      leg.position.set(x, y, -0.8)
      leg.rotation.z = rotZ
      return leg
  }
  
  // Corner Positions (Cabinet Outer Bounds)
  // Width 0.64 -> x +/- 0.32
  // Length 1.48 (Center -0.12) -> Top 0.62, Bottom -0.86
  // Leg Thickness Offset to wrap AROUND
  const lOff = legT 
  
  // Front Left (-0.32, -0.86)
  // Needs to wrap corner. Shape is +X, +Y.
  // Rot 0 aligns with cabinet corner.
  // Offset to push Inner Corner to Cabinet Corner.
  const legFL = createLeg(-0.32 - lOff, -0.86 - lOff, 0)
  tableGroup.add(legFL)
  
  // Front Right (0.32, -0.86)
  // Rot 90 (PI/2). Matches +X -> +Y.
  const legFR = createLeg(0.32 + lOff, -0.86 - lOff, Math.PI / 2)
  tableGroup.add(legFR)
  
  // Back Right (0.32, 0.62)
  // Rot 180 (PI). Matches +X -> -X.
  const legBR = createLeg(0.32 + lOff, 0.62 + lOff, Math.PI)
  tableGroup.add(legBR)
  
  // Back Left (-0.32, 0.62)
  // Rot -90 (-PI/2). Matches +X -> -Y.
  const legBL = createLeg(-0.32 - lOff, 0.62 + lOff, -Math.PI / 2)
  tableGroup.add(legBL)
  
  // Watch for stats updates to redraw scoreboard
  // We attach this to a specific watcher or just general stats watcher.
  // We can add a specialized watcher right here if we want, or use the global one.
  // But strictly `createTable` runs once (mostly). We recreate texture.
  
  // Store the draw function globally in component scope?
  // Or just rely on the fact that we can't easily export this closure?
  // Solution: Store the update function on the mesh or tableGroup userData so we can call it?
  // Or better, define `drawScoreboard` outside `createTable`?
  // Let's attach it to tableGroup.userData for now, and have the main watcher call it.
  
  tableGroup.userData.updateScoreboard = drawScoreboard

  
  // Wait, Shape is 0 to 0.7. Center is 0.35.



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
      // MARIO THEME: Question Blocks
      if (isMario) {
          const qBlockTex = getQuestionBlockTexture();
          const qBlockGeo = new THREE.BoxGeometry(0.06, 0.06, 0.06);
          const qBlockMat = new THREE.MeshStandardMaterial({
              map: qBlockTex,
              roughness: 0.3,
              metalness: 0.1
          });

          config.bumpers.forEach((b, i) => {
             const bumperGroup = new THREE.Group();
             
             // Visual Box
             const block = new THREE.Mesh(qBlockGeo, qBlockMat);
             // Center is at 0,0,0. Lift it so bottom is at z=0?
             // Or float it? Mario blocks float.
             // Bumper physics assumes z=0 for collision?
             // Let's float it at z=0.04 (center) so it's 0.01 to 0.07 off ground.
             block.position.z = 0.03; 
             block.castShadow = true;
             
             // Add a slow rotation animation? handled in animate?
             // For now just static
             
             bumperGroup.add(block);
             
             // Shadow/Floor decal?
             const shadowGeo = new THREE.PlaneGeometry(0.06, 0.06);
             const shadowMat = new THREE.MeshBasicMaterial({ color: 0x000000, transparent: true, opacity: 0.3 });
             const shadow = new THREE.Mesh(shadowGeo, shadowMat);
             shadow.position.z = 0.001;
             bumperGroup.add(shadow);
             
             bumperGroup.position.set(mapX(b.x), mapY(b.y), 0);
             
             bumperGroup.userData = {
                 bumperIndex: i,
                 type: 'bumper',
                 isMarioBlock: true, // Tag for potential animation
                 blockMesh: block,
                 isActive: false,
                 originalPos: new THREE.Vector3(mapX(b.x), mapY(b.y), 0)
             };
             
             tableGroup.add(bumperGroup);
             flippers.bumpers.push(bumperGroup);
             bumperMeshes.push(bumperGroup);
          });
      } else {
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

      if (isMario) {
         // MARIO THEME: Brick Blocks
         const brickTex = getBrickBlockTexture()
         const brickMat = new THREE.MeshStandardMaterial({
             map: brickTex,
             roughness: 0.8,
             metalness: 0
         })

         config.drop_targets.forEach((t) => {
            const w = t.width
            const h = 0.04 
            const d = t.height 

            // Box Geometry
            const geometry = new THREE.BoxGeometry(w, d, h)
            const target = new THREE.Mesh(geometry, brickMat)
            
            // Align position
            target.position.set(mapX(t.x + t.width/2), mapY(t.y + t.height/2), h/2)
            target.castShadow = true
            target.receiveShadow = true
            
            tableGroup.add(target)
            flippers.dropTargets.push(target)
         })

      } else {
      // Themed Colors (Close Encounters: Neon Orange & Cyan)
      const dropTargetColors = [0xffaa00, 0x00ffff] // Alternate Orange/Cyan

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
          roughness: 0.1, // Shiny plastic
          metalness: 0.6,
          emissive: targetColor,
          emissiveIntensity: 0.8 // Strong glow
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
    }

    // Rails - Chrome-finished guide tubes
    if (config.rails) {
      const railRadius = 0.008 // Thickness of rail tube
      const railHeight = 0.04 // Height above playfield
      const rail2DWidth = 0.016 // Width for 2D representation (2x radius for visibility)

      // Rail material - Pure Neon Core (Flat, no metal)
      const railMat = new THREE.MeshBasicMaterial({
        color: 0xffffff, // Pure White Plasma Core
      })
      
      // Rail Glow Material (Fake Bloom)
      const railGlowMat = new THREE.MeshBasicMaterial({
        color: 0x00ffff, // Pure Cyan Glow
        transparent: true,
        opacity: 0.4,
        blending: THREE.AdditiveBlending, // Additive for light-like effect
        depthWrite: false, // Don't occlude
        side: THREE.FrontSide
      })

      // 2D rail material for top-down view
      const rail2DMat = new THREE.MeshBasicMaterial({
        color: 0x00ffff,
        side: THREE.DoubleSide
      })

      createRails(config.rails)
    }

    // --- Apron (Visual Bottom Cover) ---

    // --- Apron (Visual Bottom Cover) ---
    // Covers the drain area below the flippers
    // "Farther down" -> Start Y 0.98 (More gap from flippers)
    // "Full Width" -> mapX(1.0)
    // "Height of walls" -> depth 0.1 (matching wallHeight)
    
    const apronShape = new THREE.Shape()
    const apronStartY = 0.98
    const apronEndY = 1.2
    
    // Start Top-Left
    apronShape.moveTo(mapX(0.0), mapY(apronStartY)) 
    // Line to Top-Right (Full Width)
    apronShape.lineTo(mapX(1.0), mapY(apronStartY)) 
    // Line to Bottom-Right
    apronShape.lineTo(mapX(1.0), mapY(apronEndY))
    // Line to Bottom-Left
    apronShape.lineTo(mapX(0.0), mapY(apronEndY))
    // Close
    apronShape.lineTo(mapX(0.0), mapY(apronStartY))

    // Cutout for Drain
    const drainHole = new THREE.Path()
    drainHole.moveTo(mapX(0.42), mapY(1.0))
    drainHole.lineTo(mapX(0.58), mapY(1.0))
    drainHole.lineTo(mapX(0.55), mapY(1.15)) // Tapered
    drainHole.lineTo(mapX(0.45), mapY(1.15))
    drainHole.lineTo(mapX(0.42), mapY(1.0))
    apronShape.holes.push(drainHole)

    const apronGeo = new THREE.ExtrudeGeometry(apronShape, { 
      depth: 0.1, // Match wallHeight
      bevelEnabled: true,
      bevelThickness: 0.005,
      bevelSize: 0.005,
      bevelSegments: 2
    })
    
    // Apron Material
    const apronMat = new THREE.MeshStandardMaterial({
      color: 0x111111, // Dark plastic/glass
      roughness: 0.6, // Matte to reduce glare
      metalness: 0.1, // Dielectric (Glass-like)
      emissive: 0x000000,
      transparent: true,
      opacity: 0.4 // More see-through
    })

    const apron = new THREE.Mesh(apronGeo, apronMat)
    apron.position.z = 0.0
    tableGroup.add(apron)

    // Instruction Cards (White/Yellow rectangles on Apron)
    // Adjust Z to sit on top of new 0.1 height. 
    // 0.1 + bevel (~0.005) + clearance
    const cardZ = 0.106 
    
    const cardGeo = new THREE.PlaneGeometry(0.12, 0.15) // Taller cards for bigger apron
    const cardMat = new THREE.MeshBasicMaterial({ color: 0xffffdd, side: THREE.DoubleSide })
    
    const leftCard = new THREE.Mesh(cardGeo, cardMat)
    leftCard.position.set(mapX(0.20), mapY(1.09), cardZ) 
    tableGroup.add(leftCard)
    
    const rightCard = new THREE.Mesh(cardGeo, cardMat)
    rightCard.position.set(mapX(0.80), mapY(1.09), cardZ)
    tableGroup.add(rightCard)
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
  let pColor = 0xAAAAAA // Lighter grey for mist
  let pOpacity = 0.15 // Lower opacity for see-through mist
  let pSize = 0.04 // Larger size for soft mist
  let pGrowth = 1.03 // Slower expansion
  let pLifeDecay = 0.008 // Lingers longer
  let pType = 'smoke' // smoke, sparkle, fire

  if (combo < 10) {
      if (currentTheme.value === 'mario') {
         // MARIO DEFAULT - Koopa Shell
         if (!material.userData.isShell) {
             const shellTex = getKoopaShellTexture();
             material.map = shellTex;
             material.color.setHex(0xffffff); // Use texture
             material.emissive.setHex(0x001100); 
             material.emissiveIntensity = 0.2;
             material.metalness = 0.1;
             material.roughness = 0.6;
             material.userData.isShell = true;
         }
         
         // Star Mode (Multiball)
         const activeBalls = props.stats?.balls || 1;
         if (activeBalls > 1 || balls.length > 1) {
             const time = Date.now() * 0.005;
             const hue = time % 1.0;
             const rainbow = new THREE.Color().setHSL(hue, 1.0, 0.5);
             
             material.emissive.copy(rainbow);
             material.emissiveIntensity = 1.0;
             material.color.copy(rainbow);
             
             if (glow.material) {
                 glow.material.opacity = 0.8;
                 glow.material.color.copy(rainbow);
             }
             
             // Rainbow Trail
             pColor = rainbow.getHex();
             emitRate = 2.0;
             pSize = 0.06;
         }
         
      } else {
        // Basic Silver - No effects
        material.color.setHex(0xcccccc)
        material.emissive.setHex(0x000000)
        material.emissiveIntensity = 0
        if (glow.material) glow.material.opacity = 0
        emitRate = 0
      }
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
      pColor = 0xcccccc
      pSize = 0.045
      pType = 'smoke'
      pOpacity = 0.1
      pLifeDecay = 0.01
      pGrowth = 1.025
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
      pSize = 0.05
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
      pColor = new THREE.Color().setHSL(trailHue, 1.0, 0.7).getHex() // Lighter color
      pOpacity = 0.12
      pSize = 0.06
      pGrowth = 1.03
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

// --- Extracted Rail Creation Logic ---
const createRails = (rails: any[]) => {
    if (!rails) return
    
    // Clear existing rails
    if (railsGroup) {
        railsGroup.clear()
        if (tableGroup) tableGroup.remove(railsGroup)
    }
    
    railsGroup = new THREE.Group()
    if (tableGroup) tableGroup.add(railsGroup)

    const railRadius = 0.008
    const railHeight = 0.05
    // Rail material - Pure Neon Core (Flat, no metal)
    // REFACTOR: Use shared material for color cycling
    const railMat = sharedRailCoreMat

    const rail2DWidth = 0.015
    const rail2DMat = new THREE.MeshBasicMaterial({ color: 0x00ffff }) // Cyan for 2D

    rails.forEach((rail, index) => {
        // Calculate world coordinates
        // Apply Offset if defined
        const normOffsetX = Number(props.config.rail_x_offset || 0)
        const normOffsetY = Number(props.config.rail_y_offset || 0)
        const lengthScale = Number(props.config.guide_length_scale || 1.0)
        
        // Define Glow Material locally if not found
        // const railGlowMat = new THREE.MeshBasicMaterial({ ... })
        // REFACTOR: Use shared material for slider control
        const railGlowMat = sharedRailGlowMat

        let x1 = mapX(rail.p1.x + normOffsetX)
        let y1 = mapY(rail.p1.y + normOffsetY)
        let x2 = mapX(rail.p2.x + normOffsetX)
        let y2 = mapY(rail.p2.y + normOffsetY)

        let dx = x2 - x1
        let dy = y2 - y1
        const length = Math.sqrt(dx * dx + dy * dy)
        let railMesh, rail2D

        if (rail.c1 && rail.c2) {
             // --- CURVED RAIL (Cubic Bezier) ---
             const c1x = mapX(rail.c1.x + normOffsetX)
             const c1y = mapY(rail.c1.y + normOffsetY)
             const c2x = mapX(rail.c2.x + normOffsetX)
             const c2y = mapY(rail.c2.y + normOffsetY)
             
             // Create Curve
             const curve = new THREE.CubicBezierCurve3(
                 new THREE.Vector3(x1, y1, railHeight / 2),
                 new THREE.Vector3(c1x, c1y, railHeight / 2),
                 new THREE.Vector3(c2x, c2y, railHeight / 2),
                 new THREE.Vector3(x2, y2, railHeight / 2)
             )
             
             // 3D Tube Geometry
             const tubeGeo = new THREE.TubeGeometry(curve, 20, railRadius, 8, false)
             railMesh = new THREE.Mesh(tubeGeo, railMat)
             railMesh.castShadow = true
             railMesh.receiveShadow = true
             
             // GLOW MESH (Tube)
             const glowTubeGeo = new THREE.TubeGeometry(curve, 20, railRadius * railGlowRadius.value, 8, false)
             const glowMesh = new THREE.Mesh(glowTubeGeo, railGlowMat)
             railMesh.add(glowMesh) // Attach to main rail
             
             // 2D Representation (Projected on Floor)
             const curve2D = new THREE.CubicBezierCurve3(
                 new THREE.Vector3(x1, y1, 0.001),
                 new THREE.Vector3(c1x, c1y, 0.001),
                 new THREE.Vector3(c2x, c2y, 0.001),
                 new THREE.Vector3(x2, y2, 0.001)
             )
             const tube2DGeo = new THREE.TubeGeometry(curve2D, 20, rail2DWidth/2, 8, false)
             rail2D = new THREE.Mesh(tube2DGeo, rail2DMat)
             rail2D.visible = false

        } else {
            // --- STRAIGHT RAIL (Legacy Cylinder) ---
            if (length > 0 && Math.abs(lengthScale - 1.0) > 0.001) {
                 const scaledLen = length * lengthScale
                 const ux = dx / length
                 const uy = dy / length
                 
                 x1 = x2 - ux * scaledLen
                 y1 = y2 - uy * scaledLen
                 
                 dx = x2 - x1
                 dy = y2 - y1
            }
    
            const railGeo = new THREE.CylinderGeometry(railRadius, railRadius, length, 16)
            railGeo.rotateZ(Math.PI / 2) // Standardize orientation
            
            railMesh = new THREE.Mesh(railGeo, railMat)
            
            
            // GLOW MESH (Cylinder)
            const glowRailGeo = new THREE.CylinderGeometry(railRadius * railGlowRadius.value, railRadius * railGlowRadius.value, length, 16)
            glowRailGeo.rotateZ(Math.PI / 2) // Match orientation
            
            const glowMesh = new THREE.Mesh(glowRailGeo, railGlowMat)
            railMesh.add(glowMesh)
            
            // Position set later
            railMesh.position.set((x1 + x2) / 2, (y1 + y2) / 2, railHeight / 2)
            
            const angle = Math.atan2(dy, dx)
            railMesh.rotation.z = angle
            railMesh.castShadow = true
            railMesh.receiveShadow = true
    
            const rail2DGeo = new THREE.PlaneGeometry(length, rail2DWidth)
            rail2D = new THREE.Mesh(rail2DGeo, rail2DMat)
            rail2D.position.set((x1 + x2) / 2, (y1 + y2) / 2, 0.001)
            rail2D.rotation.z = angle
            rail2D.visible = false
        }

        railMesh.userData = {
          railIndex: index,
          type: 'rail',
          p1: rail.p1,
          p2: rail.p2,
          c1: rail.c1, 
          c2: rail.c2,
          rail2D: rail2D
        }

        rail2D.userData = {
          railIndex: index,
          type: 'rail',
          p1: rail.p1,
          p2: rail.p2,
          c1: rail.c1,
          c2: rail.c2,
          rail3D: railMesh
        }

        tableGroup.add(railMesh)
        tableGroup.add(rail2D)
        railMeshes.push(railMesh)
    })
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
  
    // --- Rail Color Cycling (Neon Rainbow) ---
    // Cycle every 5 seconds (5000ms)
    // HSL: Hue 0-1
    const now = Date.now() // Assuming 'now' refers to current time
    const cycleSpeed = 0.0002
    const hue = (now * cycleSpeed) % 1.0
    // Assuming sharedRailGlowMat is defined elsewhere and accessible
    if (typeof sharedRailGlowMat !== 'undefined' && sharedRailGlowMat.color) {
        sharedRailGlowMat.color.setHSL(hue, 1.0, 0.5)
    }
    if (typeof sharedRailCoreMat !== 'undefined' && sharedRailCoreMat.color) {
        // Core is very bright (almost white) but tinted with the color
        sharedRailCoreMat.color.setHSL(hue, 1.0, 0.9)
    }
    
    // Also update 2D rails color so they match (if visible)
    // Note: iterating all meshes every frame might be overkill, but 2D rails are few.
    // Better: shared material? 
    // Actually, `createRails` uses `rail2DMat`. We can make that shared or update it here.
    // For now, let's keep it simple: just the glow cycles.

  if (renderer && scene && camera) {
    // Apply shake offset to camera position (temporarily)
    const basePos = { x: 0, y: -1.5, z: 2.5 } // Default position, should track actual camera pos if moved
    // Better: Apply offset to camera.position relative to its current "base"
    // But camera moves with keys. 
    // Let's just modify the lookAt target or add a shake group?
    // Simplest: Add shakeOffset to camera.position before render, remove after.
    
    const originalX = camera.position.x
    camera.position.x += shakeOffset.x
    
    // MARIO SHELL SPIN
    if (currentTheme.value === 'mario' && balls) {
        const spin = Date.now() * 0.02
        balls.forEach(b => {
             if (b) {
                 // Force upright spin (sliding shell look)
                 b.rotation.set(0, 0, -spin)
             }
        })
        animateMushrooms() // Update Power-Ups
    }

    // Animate Matrix Shader
    if (floorMesh.value && floorMesh.value.userData.isMatrix) {
        const mat = floorMesh.value.material as THREE.ShaderMaterial;
        if (mat.uniforms && mat.uniforms.time) {
            mat.uniforms.time.value += 0.05;
        }
    }

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

    // Animate Coins
    animateCoins()

    // Render scene
    // Render scene
    renderer.render(scene, camera)
    
    camera.position.x = originalX // Restore
  }
}

// --- Matrix Mode Watcher ---
watch([() => props.stats?.combo_count, () => props.forceMatrix], ([count, force]) => {
    if (!floorMesh.value) return;
    const currentCount = count || 0;
    
    // Trigger if combo is high OR debug force is active
    const shouldActivate = currentCount >= 100 || force === true;

    if (shouldActivate) {
        if (!floorMesh.value.userData.isMatrix) {
            // Save original material if not saved
            if (!floorMesh.value.userData.originalMat) {
                floorMesh.value.userData.originalMat = floorMesh.value.material;
            }
            
            // Create Matrix Shader Material
            const mat = new THREE.ShaderMaterial({
                uniforms: {
                    time: { value: 0 },
                    resolution: { value: new THREE.Vector2(1, 1) }, // Aspect ratio
                    color: { value: new THREE.Color(0x00ff00) }
                },
                vertexShader: MatrixShader.vertexShader,
                fragmentShader: MatrixShader.fragmentShader
            });
            
            // Store it for later restoration
            floorMesh.value.userData.matrixMat = mat;
            
            // Apply it initially
            floorMesh.value.material = mat;
            floorMesh.value.userData.isMatrix = true;
            
            // Activate Matrix Sound Mode
            SoundManager.setMatrixMode(true);
            const constructPromise = SoundManager.playModemSequence();
            
            // Trigger Visual Intro
            playMatrixIntro(constructPromise);
        }
    } else {
        // Reset if condition lost
        if (floorMesh.value.userData.isMatrix) {
            // Restore original material
            if (floorMesh.value.userData.originalMat) {
                floorMesh.value.material = floorMesh.value.userData.originalMat;
            }
            floorMesh.value.userData.isMatrix = false;
            
            // Deactivate Matrix Sound Mode
            SoundManager.setMatrixMode(false);
            stopMatrixIntro();
        }
    }
});

// --- Matrix Intro Logic ---
const matrixIntroVisible = ref(false);
const currentFailScreen = ref('terminal'); // 'terminal', 'bsod', 'redhat', 'bsd'
const isOverlayFullscreen = ref(false);
const matrixTerminalLines = ref<string[]>([]);
const matrixGlitchActive = ref(false);
let matrixIntroTimer: ReturnType<typeof setTimeout> | null = null;
let matrixGlitchInterval: ReturnType<typeof setInterval> | null = null;

const playMatrixIntro = async (constructPromise?: Promise<void>) => {
    matrixIntroVisible.value = true;
    currentFailScreen.value = 'terminal';
    isOverlayFullscreen.value = false;
    matrixGlitchActive.value = false;
    matrixTerminalLines.value = [];

    // Audio done signal
    let audioFinished = false;
    if (constructPromise) {
        constructPromise.then(() => { audioFinished = true; });
    } else {
        audioFinished = true; // Fallback if no promise
    }

    // Helper: Wait for ms, but stop early if audio finishes
    const interruptibleWait = (ms: number) => new Promise<void>(resolve => {
        if (audioFinished) { resolve(); return; }
        
        const checkInterval = 100;
        let elapsed = 0;
        const timer = setInterval(() => {
            elapsed += checkInterval;
            if (audioFinished || elapsed >= ms) {
                clearInterval(timer);
                resolve();
            }
        }, checkInterval);
    });

    const typeLine = (text: string, delay: number) => new Promise<void>(resolve => {
        if (text) {
             matrixTerminalLines.value.push(text);
             if (matrixTerminalLines.value.length > 20) matrixTerminalLines.value.shift();
        }
        // Use interruptible wait for the delay too, so we rush text if audio finishes
        interruptibleWait(delay).then(resolve);
    });

    // --- PHASE 1: DIALUP / FAIL PARADE ---
    // Start with some terminal text waiting for connection
    await typeLine("> INITIALIZING CONNECTION...", 500);
    await typeLine("> DIALING 555-0690...", 2000); // Extended wait
    await typeLine("> RINGING...", 2500); 
    await typeLine("> CONNECTING...", 2000); 
    await typeLine("> NEGOTIATING BAUD RATE...", 2000); 
    await typeLine("> VERIFYING ENCRYPTION KEYS...", 2000); 
    await typeLine("> ESTABLISHING SECURE LINK...", 1500);

    // SWITCH TO FULLSCREEN (Hacking in)
    isOverlayFullscreen.value = true;

    // If audio is not done, start Fail Parade (now happens later in the sequence)
    if (!audioFinished) {
        currentFailScreen.value = 'bsod';
        await interruptibleWait(3500); // Extended fail screen time
    }
    
    if (!audioFinished) {
        currentFailScreen.value = 'redhat';
        await interruptibleWait(3500);
    }

    if (!audioFinished) {
        currentFailScreen.value = 'bsd';
        await interruptibleWait(3500);
    }
    
    // Resume Terminal for final handshake
    currentFailScreen.value = 'terminal';
    if (!audioFinished) {
        await typeLine("> HANDSHAKE COMPLETE", 500);
        await typeLine("> LOGGING IN AS: NEO", 500);
        await typeLine("> PASSWORD: **********", 300);
    }

    // FILLER: CORE DUMP until Audio Ends (Fills the gap before Construct)
    while (!audioFinished) {
        const sector = Math.floor(Math.random() * 0xFFFF).toString(16).toUpperCase().padStart(4, '0');
        matrixTerminalLines.value.push(`> DUMPING PHYSICAL MEMORY: 0x${sector}`);
        if (matrixTerminalLines.value.length > 20) matrixTerminalLines.value.shift();
        await interruptibleWait(100);
    }

    // Ensure we wait for Audio trigger here (if it hasn't finished yet)
    if (constructPromise) {
        await constructPromise;
    }
    
    // --- PHASE 2: THE CONSTRUCT (White Room) ---
    // At this point, Construct Audio has started.
    currentFailScreen.value = 'terminal';
    await typeLine("> UPLOADING CONSTRUCT...", 100);
    
    if (floorMesh.value) {
        // Flash to white
        floorMesh.value.material = new THREE.MeshBasicMaterial({ color: 0xffffff });
    }
    
    // MULTIBALL TRIGGER: Spawn 3 balls for the Construct
    for (let i = 0; i < 3; i++) {
        if (props.socket) {
            console.log(`[Matrix] Spawning Ball ${i+1}...`);
            props.socket.emit('relaunch_ball');
        }
        await new Promise(r => setTimeout(r, 400)); // Stagger launches
    }
    
    // Hold White Room for a bit
    await new Promise(r => setTimeout(r, 4000));

    // --- PHASE 3: SYSTEM FAILURE / GLITCH ---
    await typeLine("!!! SYSTEM FAILURE !!!", 500);
    await typeLine("Segmentation fault (core dumped)", 200);
    
    startMatrixGlitch();
    
    // Hold Glitch for 8s
    await new Promise(r => setTimeout(r, 8000));

    // --- PHASE 4: ENTER MATRIX ---
    matrixIntroVisible.value = false;
    isOverlayFullscreen.value = false;
    stopMatrixGlitch();
    
    // THE CONSTRUCT (White Room) persists for 10 seconds
    await new Promise(r => setTimeout(r, 10000));

    // --- PHASE 5: REVERT TO NORMAL ---
    if (floorMesh.value && floorMesh.value.userData.originalMat) {
        floorMesh.value.material = floorMesh.value.userData.originalMat;
        floorMesh.value.userData.isMatrix = false;
    }
    
    SoundManager.setMatrixMode(false);
    stopMatrixIntro();
};

const startMatrixGlitch = () => {
    matrixGlitchActive.value = true;
    matrixGlitchInterval = setInterval(() => {
        const hex = Array(8).fill(0).map(() => Math.floor(Math.random() * 255).toString(16).padStart(2, '0')).join(' ');
        const addr = "0x" + Math.floor(Math.random() * 0xFFFFFFFF).toString(16).padStart(8, '0');
        matrixTerminalLines.value.push(`${addr}: ${hex} ${hex}`);
        if (matrixTerminalLines.value.length > 25) matrixTerminalLines.value.shift();
    }, 50);
};

const stopMatrixIntro = () => {
    matrixIntroVisible.value = false;
    currentFailScreen.value = 'terminal';
    isOverlayFullscreen.value = false;
    stopMatrixGlitch();
    if (matrixIntroTimer) clearTimeout(matrixIntroTimer);
};

const stopMatrixGlitch = () => {
    matrixGlitchActive.value = false;
    if (matrixGlitchInterval) clearInterval(matrixGlitchInterval);
};

// --- Watcher for Rails ---
// Ensure 3D view updates when rails are modified (e.g. after drag-and-drop or undo)
watch(() => props.config?.rails, (newRails) => {
    if (newRails) {
        // Remove existing rail meshes
        railMeshes.forEach(mesh => {
            if (mesh.parent) mesh.parent.remove(mesh)
            if (mesh.geometry) mesh.geometry.dispose()
        })
        railMeshes.length = 0
        
        // Remove existing rail handles
        clearRailHandles()
        
        // Rebuild
        createRails(newRails)
        
        // Re-create handles if in edit mode
        if (props.isEditMode) {
            updateRailHandles()
        }
    }
}, { deep: true })

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

// COIN LOGIC
let coins = []
let coinMat = null
const coinGeo = new THREE.PlaneGeometry(0.12, 0.12) // Slightly larger than bumper

const spawnCoin = (pos) => {
    if (!coinMat) return

    const coin = new THREE.Mesh(coinGeo, coinMat)
    coin.position.copy(pos)
    
    // Random initial rotation (facig camera mostly)
    coin.rotation.x = Math.PI / 2 // Flat? No, upright facing camera.
    // In top-down (Z up), upright means standing on X axis?
    // Actually in 3D, let's make it spin on Z axis (flat) or upright?
    // Mario coins spin on vertical axis. In our Z-up world, that's Z.
    // But they face the camera.
    // Let's make them face +Y (back of table) or camera? 
    // Camera is at -1.5 Y. 
    coin.rotation.x = Math.PI / 4 // Angled up
    
    coin.userData = {
        velocity: new THREE.Vector3(0, 0, 0.08), // Pop up fast
        life: 1.0,
        spinSpeed: 0.2
    }
    
    tableGroup.add(coin)
    coins.push(coin)
}

const animateCoins = () => {
    if (!coins.length) return
    
    // Removing items while iterating is tricky, filter afterwards
    coins.forEach(c => {
         c.position.add(c.userData.velocity)
         c.userData.velocity.z -= 0.003 // Gravity
         
         c.rotation.z += c.userData.spinSpeed
         
         c.userData.life -= 0.02
         if (c.userData.life < 0) {
             c.visible = false
         } else if (c.userData.life < 0.3) {
             c.material.opacity = c.userData.life * 3.3
         } else {
             c.material.opacity = 1.0
         }
    })
    
    // Cleanup
    const active = coins.filter(c => c.visible)
    const dead = coins.filter(c => !c.visible)
    
    dead.forEach(d => {
        tableGroup.remove(d)
        // geometry is shared, material is shared. OK.
    })
    
    coins = active
}

const playCoinSound = () => {
    try {
        const AudioContext = window.AudioContext || (window as any).webkitAudioContext
        if (!AudioContext) return
        
        const audioContext = new AudioContext()
        const gainNode = audioContext.createGain()
        gainNode.connect(audioContext.destination)
        gainNode.gain.value = 0.01 // Soft volume
        
        const oscillator = audioContext.createOscillator()
        oscillator.connect(gainNode)
        oscillator.type = "square"
        
        // Correct Interval (B -> E)
        // B5
        oscillator.frequency.setValueAtTime(987.77, audioContext.currentTime)
        // E6
        oscillator.frequency.setValueAtTime(1318.51, audioContext.currentTime + 0.08)
        
        oscillator.start()
        oscillator.stop(audioContext.currentTime + 0.8)
    } catch (e) {
        console.warn('Audio play failed', e)
    }
}

const playBreakSound = () => {
    try {
        const AudioContext = window.AudioContext || (window as any).webkitAudioContext
        if (!AudioContext) return
        
        const ctx = new AudioContext()
        
        // Noise Buffer
        const bufferSize = ctx.sampleRate * 0.1 // 100ms
        const buffer = ctx.createBuffer(1, bufferSize, ctx.sampleRate)
        const data = buffer.getChannelData(0)
        for (let i = 0; i < bufferSize; i++) {
            data[i] = Math.random() * 2 - 1
        }
        
        const noise = ctx.createBufferSource()
        noise.buffer = buffer
        
        // Lowpass Filter for "Thud/Crush"
        const filter = ctx.createBiquadFilter()
        filter.type = 'lowpass'
        filter.frequency.setValueAtTime(1000, ctx.currentTime)
        filter.frequency.exponentialRampToValueAtTime(100, ctx.currentTime + 0.1)
        
        const gain = ctx.createGain()
        gain.gain.setValueAtTime(0.3, ctx.currentTime)
        gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.1)
        
        noise.connect(filter)
        filter.connect(gain)
        gain.connect(ctx.destination)
        
        noise.start()
    } catch (e) {
        console.warn('Audio play failed', e)
    }
}


const playPowerUpSound = () => {
    try {
        const AudioContext = window.AudioContext || (window as any).webkitAudioContext
        if (!AudioContext) return
        
        const ctx = new AudioContext()
        const gain = ctx.createGain()
        gain.connect(ctx.destination)
        gain.gain.value = 0.05

        const now = ctx.currentTime
        const notes = [440, 554.37, 659.25, 880, 1108.73, 1318.51] // A major arpeggio
        
        notes.forEach((freq, i) => {
            const osc = ctx.createOscillator()
            osc.connect(gain)
            osc.type = 'square'
            osc.frequency.setValueAtTime(freq, now + i * 0.08)
            osc.start(now + i * 0.08)
            osc.stop(now + i * 0.08 + 0.1)
        })
    } catch(e) {
        console.warn('Audio play failed', e)
    }
}

const spawnMushroom = (pos: THREE.Vector3) => {
    const tex = getMushroomTexture()
    const mat = new THREE.SpriteMaterial({ map: tex })
    const sprite = new THREE.Sprite(mat)
    sprite.position.copy(pos)
    sprite.scale.set(0.08, 0.08, 1) // Size of a ball roughly
    
    // Initial velocity
    sprite.userData = {
        velocity: new THREE.Vector3((Math.random() - 0.5) * 0.05, -0.05, 0), // Fall down, drift slightly
        life: 5.0, // 5 seconds to grab
        active: true
    }
    
    tableGroup.add(sprite)
    mushrooms.push(sprite)
}

const animateMushrooms = () => {
    // Iterate backwards to safe remove
    for (let i = mushrooms.length - 1; i >= 0; i--) {
        const m = mushrooms[i]
        
        // Move
        m.position.add(m.userData.velocity)
        // Gravity? No, just drift down
        
        // Bounds check (remove if off screen)
        if (m.position.y < -1.0) {
            tableGroup.remove(m)
            mushrooms.splice(i, 1)
            continue
        }
        
        // Collision with Ball
        let hit = false
        balls.forEach(ball => {
            if (hit) return
            const dist = m.position.distanceTo(ball.position)
            if (dist < 0.1) {
                // COLLECTED!
                hit = true
                playPowerUpSound()
                
                // Grow Effect (Visual Only)
                if (!ball.userData.originalScale) {
                    ball.userData.originalScale = ball.scale.clone()
                }
                
                // Scale up
                // Double size = Scale 2 of original.
                // Assuming original is approx 1,1,1
                ball.scale.copy(ball.userData.originalScale).multiplyScalar(2.0)
                
                // Set reset timer
                if (ball.userData.growTimer) clearTimeout(ball.userData.growTimer)
                ball.userData.growTimer = setTimeout(() => {
                    if (ball && ball.userData.originalScale) {
                        ball.scale.copy(ball.userData.originalScale)
                    }
                }, 10000) // 10 Seconds
            }
        })
        
        if (hit) {
            tableGroup.remove(m)
            mushrooms.splice(i, 1)
        }
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

    // MARIO COIN TRIGGER
    if (isActive && !bumperGroup.userData.wasActive) {
        if (currentTheme.value === 'mario') {
             // Spawn Coin above bumper
             const spawnPos = bumperGroup.position.clone()
             spawnPos.z += 0.1 
             spawnCoin(spawnPos)
             playCoinSound()
             
             // 10% Chance for Mushroom
             if (Math.random() < 0.1) {
                 spawnMushroom(spawnPos)
             }
        }
    }
    bumperGroup.userData.wasActive = isActive

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
          // Trigger Break Sound on Disappear (Mario only)
           if (currentTheme.value === 'mario' && !newVisible && mesh.visible) {
               playBreakSound()
               
               // Optional: Add brick particles?
               const pos = mesh.position.clone()
               if (ballParticles[0]) {
                   // Brown/Red brick debris
                   spawnParticles(ballParticles[0], 10, pos, pos, 0xA0522D, 1.0, 0.05, 1.02, 0.05)
               }
           }
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
  
  // Defaul values (Softer Shake)
  let intensity = 0.05 // Reduced from 0.2
  let maxFrames = 5    // Reduced from 10
  let dir = 1
  let isAlien = false
  
  // Handle different input forms
  if (typeof eventData === 'string') {
      dir = eventData.toLowerCase() === 'left' ? -1 : 1
  } else if (eventData && typeof eventData === 'object') {
     // ... (keep existing logic but scale down overrides if needed)
      if (eventData.direction && typeof eventData.direction === 'string') {
          dir = eventData.direction.toLowerCase() === 'left' ? -1 : 1
      }
      
      if (eventData.type === 'alien' || (eventData.intensity && eventData.intensity > 1.0)) {
          isAlien = true
          intensity = (eventData.strength || eventData.intensity || 1.0) * 0.5 // Scale down alien too
          maxFrames = 20 
      } else if (eventData.intensity) {
          intensity = eventData.intensity * 0.25 // Scale incoming intensity
      }
  }

  // Shake animation loop
  let frame = 0
  
  const shake = () => {
    if (frame >= maxFrames) {
      shakeOffset.x = 0
      shakeOffset.y = 0 
      return
    }
    
    // Smooth Sine Wave Oscillation
    // Frame 0..maxFrames -> 0..PI
    const progress = frame / maxFrames
    const decay = 1 - progress
    const wave = Math.sin(progress * Math.PI * 2) // One full sine wave? Or dampening spring?
    // Let's do simple alternating push
    const offset = (frame % 2 === 0 ? 1 : -1) * intensity * decay * dir
    
    // Just overwrite existing simplistic logic
    if (isAlien) {
        shakeOffset.x = (Math.random() - 0.5) * intensity * decay
        shakeOffset.y = (Math.random() - 0.5) * intensity * decay
    } else {
        shakeOffset.x = offset
        shakeOffset.y = 0
        // Add slight vertical bump for realism
        shakeOffset.y = Math.abs(offset) * 0.2
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

watch(() => [props.stats.game_over, props.showHighScores], ([gameOver, showScores]) => {
    // console.log('🏁 game_over/showHighScores watcher fired:', gameOver, showScores)
    if ((gameOver || showScores) && props.stats.is_high_score) {
        triggerFireworks()
    } else {
        if (!gameOver && !showScores && fireworksInterval) {
            clearInterval(fireworksInterval)
            fireworksInterval = null
        }
    }

    // Auto-scroll to highlighted high score
    if (gameOver || showScores) {
        nextTick(() => {
            const container = document.querySelector('.high-score-table-container')
            const highlighted = container?.querySelector('.highlight')
            if (container && highlighted) {
                console.log("Scrolling high score into view")
                highlighted.scrollIntoView({ block: 'center', behavior: 'smooth' })
            }
        })
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
// Expose methods for parent component to access via template refs
defineExpose({
    addRail,
    addCurve,
    addBumper,
    deleteSelectedObject
})
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

/* Matrix Intro */
.matrix-intro-overlay {
    position: absolute; /* Specific to Playfield Container */
    top: 0; 
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0, 0, 0, 0); /* Transparent */
    pointer-events: none; /* Allow clicking through */
    color: #00ff00;
    font-family: 'Courier New', monospace;
    padding: 20px;
    z-index: 9999;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    justify-content: center; /* Center Vertically in Playfield */
    align-items: center;     /* Center Horizontally in Playfield */
}

.matrix-intro-overlay.is-fullscreen {
    position: fixed; /* Switch to Viewport Fullscreen */
    width: 100vw;
    height: 100vh;
}

.matrix-terminal {
    width: 90%;
    max-width: 800px;
    text-align: center; /* Center text lines */
}

.terminal-line {
    white-space: pre-wrap;
    text-shadow: 0 0 5px #00ff00;
    margin-bottom: 5px;
    font-size: clamp(14px, 2.5vw, 24px); /* Responsive Font */
    line-height: 1.2;
}

.glitch-text {
    color: #aaffaa;
    text-shadow: 2px 0 #ff0000, -2px 0 #0000ff;
    animation: glitch-skew 0.1s infinite;
}

@keyframes glitch-skew {
    0% { transform: skew(0deg); }
    20% { transform: skew(-10deg); }
    40% { transform: skew(10deg); }
    60% { transform: skew(-5deg); }
    80% { transform: skew(5deg); }
    100% { transform: skew(0deg); }
}

/* Fail Screens */
.bsod-screen {
    position: fixed; /* Covers specific Viewport/App */
    top: 0; left: 0; 
    width: 100vw; 
    height: 100vh;
    background: rgba(0, 0, 170, 0.4); /* High Transparency Blue */
    color: white;
    font-family: 'Lucida Console', 'Courier New', monospace;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
    padding: 20px;
    z-index: 10000;
    text-shadow: 0 0 5px rgba(255,255,255,0.5);
}

.bsod-content {
    max-width: 800px;
    width: fit-content;
    font-size: clamp(16px, 2vw, 24px);
    line-height: 1.5;
    background: rgba(0,0,170, 0.2); /* Slight box highlight */
    padding: 20px;
    border-radius: 10px;
}

.bsod-header {
    margin-bottom: 20px;
    background: rgba(170, 0, 0, 0.5); /* Red highlight on blue */
    padding: 5px;
    display: inline-block;
}

.linux-screen {
    position: fixed; /* Covers specific Viewport/App */
    top: 0; left: 0; 
    width: 100vw; 
    height: 100vh;
    background: rgba(0, 0, 0, 0.4); /* High Transparency Black */
    color: #cccccc;
    font-family: 'Courier New', monospace;
    padding: 20px;
    z-index: 10000;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    justify-content: center; /* Center vertically */
    align-items: center;     /* Center horizontally */
}

.linux-content {
    font-size: clamp(14px, 1.8vw, 20px);
    line-height: 1.3;
    width: fit-content; /* Shrink to content */
    min-width: 300px;
    max-width: 900px;
    text-align: left;   /* Keep boot text left aligned */
    text-shadow: 1px 1px 2px black;
}
</style>
