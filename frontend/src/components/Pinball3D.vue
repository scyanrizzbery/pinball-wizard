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

    <div v-if="stats && stats.is_training"
      style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.7); display: flex; flex-direction: column; align-items: center; justify-content: center; z-index: 10; color: white;">
      <h2>TRAINING IN PROGRESS</h2>
      <p style="font-size: 1.2em; font-weight: bold; color: #4caf50;">{{ Math.round(stats.training_progress * 100) }}%</p>
      <p>Step {{ formatNumber(stats.current_step) }} / {{ formatNumber(stats.total_steps) }}</p>
      <div style="width: 60%; height: 8px; background: #555; border-radius: 4px; overflow: hidden; margin-top: 10px;">
        <div
          :style="{ width: (stats.training_progress * 100) + '%', height: '100%', background: '#4caf50', transition: 'width 0.3s' }">
        </div>
      </div>
    </div>

    <!-- Tilted Overlay -->
    <div v-if="stats && stats.is_tilted === true" class="overlay-screen tilted-overlay">
        <h1>TILTED!</h1>
    </div>

    <!-- Game Over Overlay -->
    <div v-if="showGameOver && !stats.is_training" class="overlay-screen game-over-overlay">
        <h1>GAME OVER</h1>
        <p v-if="!autoStartEnabled">Press Launch to Restart</p>
        <p v-else>Please wait...</p>
    </div>

    <div v-if="!config || !config.rails" class="loading-placeholder">
      <div class="spinner"></div>
      <div class="loading-text">CONNECTING...</div>
    </div>

    <div v-if="cameraMode === 'perspective' && showDebug" class="debug-overlay">
      <div>Camera X: {{ cameraDebug.x.toFixed(2) }}</div>
      <div>Camera Y: {{ cameraDebug.y.toFixed(2) }}</div>
      <div>Camera Z: {{ cameraDebug.z.toFixed(2) }}</div>
    </div>
    
    <!-- Rail Editor Controls -->
    <div class="editor-controls" v-if="cameraMode === 'perspective'">
        <div class="controls-row">
            <button @click="$emit('toggle-fullscreen')" class="fullscreen-btn" title="Playfield Full">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"/>
                </svg>
            </button>
            <button @click="toggleEditMode" :class="{ active: isEditMode }">
                {{ isEditMode ? 'Done Editing' : 'Edit' }}
            </button>
            <button @click="$emit('toggle-view')">
                {{ cameraMode === 'perspective' ? 'Switch to 2D' : 'Switch to 3D' }}
            </button>
        </div>

        <div v-if="isEditMode" class="edit-actions">
            <button @click="deleteSelectedObject" :disabled="selectedRailIndex === -1 && selectedBumperIndex === -1">Delete Selected</button>
            <div v-if="selectedRailIndex !== -1" class="selected-info">
                Selected: {{ selectedRailIndex }}
            </div>
            
            <div class="object-drawer">
                <div class="drawer-title">Drag to Add:</div>
                <div class="drawer-item" draggable="true" @dragstart="onDragStart($event, 'rail')">
                    <div class="icon rail-icon"></div>
                    <span>Rail</span>
                </div>
                <div class="drawer-item" draggable="true" @dragstart="onDragStart($event, 'bumper')">
                    <div class="icon bumper-icon"></div>
                    <span>Bumper</span>
                </div>
            </div>
        </div>
    </div>
    
    <!-- Game Settings Overlay -->
    <div v-if="showSettings" class="sound-settings-overlay">
        <GameSettings 
            :smokeIntensity="smokeIntensity"
            @update-smoke-intensity="(val) => smokeIntensity = val"
            @close="showSettings = false" 
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

<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import SoundManager from '../utils/SoundManager'
import GameSettings from './GameSettings.vue'

const props = defineProps({
    socket: Object,
    configSocket: Object,
    config: Object,
    nudgeEvent: Object,
    stats: Object,
    cameraMode: { type: String, default: 'perspective' },
    autoStartEnabled: { type: Boolean, default: false },
    showFlipperZones: { type: Boolean, default: false },
})

const container = ref(null)
let scene, camera, renderer, controls
let resizeObserver
// let socket // Use props.socket
let balls = [] // Array of mesh objects
let flippers = {} // { left: mesh, right: mesh, upper: [] }
let tableGroup
let ballGeo, ballMat
let zoneMeshes = [] // Store zone meshes for show/hide

// Ball effects for combo-based visuals
let ballGlows = []
let ballTrails = [] // { mesh: THREE.Mesh, positions: THREE.Vector3[] }
let ballParticles = []

// Physics Config (to sync dimensions)
let physicsConfig = ref(null)
// Store previous flipper values for change detection (not reactive)
let lastFlipperValues = {
    length: null,
    width: null,
    tipWidth: null
}
const cameraDebug = ref({ x: 0, y: 0, z: 0 })
const showDebug = ref(false)
const showSettings = ref(false)
const smokeIntensity = ref(1.0)
let debugTimeout = null

// Mobile Controls State
const controlsActive = ref(false)

// Stuck Ball State
const stuckBallDialog = ref(false)
const stuckBallTimer = ref(20)
let stuckBallInterval = null

const formatNumber = (num) => {
  if (num === undefined || num === null) return '0'
  return num.toLocaleString()
}

// Rail Editor State
const isEditMode = ref(false)
const selectedRailIndex = ref(-1)
const selectedBumperIndex = ref(-1)
const selectedType = ref(null) // 'rail' or 'bumper'
const isDragging = ref(false)
const dragPoint = ref(null) // 'p1', 'p2', or 'body'
const dragStartPos = new THREE.Vector2()
const dragState = { initialP1: null, initialP2: null, initialPos: null }
const raycaster = new THREE.Raycaster()
const mouse = new THREE.Vector2()
const railHandles = [] // Array of mesh handles
const railMeshes = [] // Array of rail body meshes
const bumperMeshes = [] // Array of bumper meshes
let dragPlane = null // Plane for raycasting during drag

// Camera Pan State
const isPanning = ref(false)
const panStart = new THREE.Vector2()
const cameraStartPos = new THREE.Vector3()

const toggleEditMode = () => {
    isEditMode.value = !isEditMode.value
    if (!isEditMode.value) {
        selectedRailIndex.value = -1
        clearRailHandles()
    } else {
        updateRailHandles()
    }
}

const addRail = () => {
    // Add a default rail in the center
    const newRail = {
        p1: { x: 0.4, y: 0.4 },
        p2: { x: 0.6, y: 0.6 }
    }
    props.configSocket.emit('create_rail', newRail)
}

const deleteSelectedObject = () => {
    if (selectedType.value === 'rail' && selectedRailIndex.value !== -1) {
        props.configSocket.emit('delete_rail', { index: selectedRailIndex.value })
        selectedRailIndex.value = -1
        clearRailHandles()
    } else if (selectedType.value === 'bumper' && selectedBumperIndex.value !== -1) {
        props.configSocket.emit('delete_bumper', { index: selectedBumperIndex.value })
        selectedBumperIndex.value = -1
    }
}

const updateRailHandles = () => {
    clearRailHandles()
    if (!isEditMode.value || !props.config || !props.config.rails) return
    
    props.config.rails.forEach((rail, index) => {
        // Create handles for p1 and p2
        const p1 = mapToWorld(rail.p1.x, rail.p1.y)
        const p2 = mapToWorld(rail.p2.x, rail.p2.y)
        
        const createHandle = (pos, pointName) => {
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

const mapToWorld = (x, y) => {
    // Map normalized (0-1) to world coordinates used in 3D scene
    // Based on mapX and mapY functions
    return {
        x: (x - 0.5) * 0.6,
        y: (0.5 - y) * 1.2
    }
}

const mapFromWorld = (wx, wy) => {
    // Inverse of mapToWorld
    return {
        x: (wx / 0.6) + 0.5,
        y: 0.5 - (wy / 1.2)
    }
}

const onDragStart = (event, type) => {
    event.dataTransfer.setData('type', type)
}

const onDrop = (event) => {
    const type = event.dataTransfer.getData('type')
    if (!type) return
    
    updateMouse(event)
    raycaster.setFromCamera(mouse, camera)
    
    const plane = new THREE.Plane(new THREE.Vector3(0, 0, 1), 0)
    const target = new THREE.Vector3()
    raycaster.ray.intersectPlane(plane, target)
    
    if (target) {
        const normPos = mapFromWorld(target.x, target.y)
        
        if (type === 'rail') {
            const newRail = {
                p1: { x: normPos.x - 0.1, y: normPos.y - 0.1 },
                p2: { x: normPos.x + 0.1, y: normPos.y + 0.1 }
            }
            props.configSocket.emit('create_rail', newRail)
        } else if (type === 'bumper') {
            const newBumper = {
                x: normPos.x,
                y: normPos.y,
                radius_ratio: 0.04,
                value: 100
            }
            props.configSocket.emit('create_bumper', newBumper)
        }
    }
}

const onMouseDown = (event) => {
    console.log("Container MouseDown", event.button)
    // Resume Audio Context on first interaction
    SoundManager.resume()

    // Middle mouse button for camera panning
    if (event.button === 1) {
        event.preventDefault()
        isPanning.value = true
        panStart.set(event.clientX, event.clientY)
        cameraStartPos.copy(camera.position)
        return
    }
    
    if (!isEditMode.value) return
    
    updateMouse(event)
    raycaster.setFromCamera(mouse, camera)
    
    // Check handles first
    const intersects = raycaster.intersectObjects(railHandles)
    if (intersects.length > 0) {
        const hit = intersects[0].object
        selectedRailIndex.value = hit.userData.railIndex
        selectedType.value = 'rail'
        selectedBumperIndex.value = -1
        dragPoint.value = hit.userData.point
        isDragging.value = true
        
        // Create drag plane at hit height
        if (!dragPlane) {
            dragPlane = new THREE.Plane(new THREE.Vector3(0, 0, 1), -hit.position.z)
        }
        
        // Disable orbit controls if we had them (we don't seem to use OrbitControls explicitly here?)
        // If we did, we'd need to disable them.
        
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
        dragPoint.value = 'body'
        isDragging.value = true
        
        // Create drag plane
        if (!dragPlane) {
            dragPlane = new THREE.Plane(new THREE.Vector3(0, 0, 1), -hit.position.z)
        }
        
        // Store start position
        const target = new THREE.Vector3()
        raycaster.ray.intersectPlane(dragPlane, target)
        if (target) {
            const normPos = mapFromWorld(target.x, target.y)
            dragStartPos.set(normPos.x, normPos.y)
            
            // Store initial rail positions to avoid drift accumulation
            const rail = props.config.rails[selectedRailIndex.value]
            if (rail) {
                // Store as userData on the rail object temporarily? Or separate ref?
                // Let's use a separate object for drag state
                dragState.initialP1 = { ...rail.p1 }
                dragState.initialP2 = { ...rail.p2 }
            }
        }
        
        updateRailHandles()
        return
    }
    
    // Check bumpers
    const bumperIntersects = raycaster.intersectObjects(bumperMeshes)
    if (bumperIntersects.length > 0) {
        const hit = bumperIntersects[0].object
        selectedBumperIndex.value = hit.userData.bumperIndex
        selectedType.value = 'bumper'
        selectedRailIndex.value = -1
        isDragging.value = true
        
        if (!dragPlane) {
            dragPlane = new THREE.Plane(new THREE.Vector3(0, 0, 1), -hit.position.z)
        }
        
        const target = new THREE.Vector3()
        raycaster.ray.intersectPlane(dragPlane, target)
        if (target) {
            const normPos = mapFromWorld(target.x, target.y)
            dragStartPos.set(normPos.x, normPos.y)
            
            const bumper = props.config.bumpers[selectedBumperIndex.value]
            if (bumper) {
                dragState.initialPos = { x: bumper.x, y: bumper.y }
            }
        }
        
        updateRailHandles() // Clear rail handles
        return
    }
}

const onMouseMove = (event) => {
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
                if (dragPoint.value === 'body') {
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
            }
        } else if (selectedType.value === 'bumper') {
            const bumper = props.config.bumpers[selectedBumperIndex.value]
            if (bumper) {
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
                props.configSocket.emit('update_rails', props.config.rails)
            } else if (selectedType.value === 'bumper' && props.config.bumpers) {
                props.configSocket.emit('update_bumpers', props.config.bumpers)
            }
        }
    }
}

// Zoom functionality
let zoomDebounceTimer = null
const onWheel = (event) => {
    if (!props.config) return

    // Calculate new zoom
    // DeltaY is usually +/- 100 per tick.
    // Zoom range typically 0.5 to 2.0
    const sensitivity = 0.001
    let newZoom = (physicsConfig.value.camera_zoom || 1.0) - (event.deltaY * sensitivity)
    
    // Clamp zoom
    newZoom = Math.max(0.2, Math.min(3.0, newZoom))
    
    // Update local config immediately for responsiveness
    physicsConfig.value.camera_zoom = newZoom
    
    // Force camera update locally
    updateCamera()
    
    // Debounce network update
    if (zoomDebounceTimer) clearTimeout(zoomDebounceTimer)
    zoomDebounceTimer = setTimeout(() => {
        console.log('Emitting zoom update:', newZoom)
        props.configSocket.emit('update_physics_v2', { camera_zoom: newZoom })
    }, 300)
}

const updateMouse = (event) => {
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
    console.log("Relaunch confirmed")
    props.socket.emit('relaunch_ball')
    clearInterval(stuckBallInterval)
    stuckBallDialog.value = false
}

const cancelRelaunch = () => {
    console.log("Relaunch cancelled")
    clearInterval(stuckBallInterval)
    stuckBallDialog.value = false
}

// Watch for config changes from parent
// Watch moved to after createTable definition


const mapX = (x) => (x - 0.5) * 0.6
const mapY = (y) => (0.5 - y) * 1.2

const createTable = (config = null) => {
  console.log('Creating Table with config:', config)
  if (tableGroup) scene.remove(tableGroup)
  // Remove old table if it exists
  if (tableGroup) {
    scene.remove(tableGroup)
    // Dispose of geometries and materials to free memory
    tableGroup.traverse((obj) => {
      if (obj.geometry) obj.geometry.dispose()
      if (obj.material) {
        if (Array.isArray(obj.material)) {
          obj.material.forEach(mat => mat.dispose())
        } else {
          obj.material.dispose()
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

  // Initialize ball resources - Chrome finish
  ballGeo = new THREE.SphereGeometry(0.016, 32, 32)
  ballMat = new THREE.MeshStandardMaterial({ 
    color: 0xdddddd, // Bright silver (very visible)
    metalness: 0.7, // Reduced from 0.95 for more subtle reflections
    roughness: 0.25, // Increased from 0.1 to diffuse reflections
    emissive: 0x333333, // Slightly darker base emissive
    emissiveIntensity: 0.05 // Reduced from 0.1 for subtler glow
  })
  flippers = { left: null, right: null, dropTargets: [], bumpers: [] }
  zoneMeshes = [] // Clear zone meshes array

  // Floor - Brighter playfield
  const floorGeo = new THREE.PlaneGeometry(0.6, 1.2)
  const floorMat = new THREE.MeshStandardMaterial({
    color: 0x2a2a44, // Brighter blue-gray (was #1a1a2e)
    roughness: 0.4,
    metalness: 0.6,
    emissive: 0x1a1a2e,
    emissiveIntensity: 0.15
  })
  const floor = new THREE.Mesh(floorGeo, floorMat)
  floor.receiveShadow = true
  tableGroup.add(floor)

  // Walls - Chrome-like finish
  const wallMat = new THREE.MeshStandardMaterial({
    color: 0x888888,
    roughness: 0.2,
    metalness: 0.9,
    emissive: 0x222222,
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

         // Main dome - brighter metallic silver
         const domeMat = new THREE.MeshStandardMaterial({
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

         // Ring base around dome - more prominent
         const ringMat = new THREE.MeshStandardMaterial({
           color: 0x888888, // Lighter gray
           roughness: 0.25,
           metalness: 0.85,
           emissive: 0x444444,
           emissiveIntensity: 0.3
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
           bumper2D // Store reference for updates
         }
         tableGroup.add(bumperGroup)
         flippers.bumpers.push(bumperGroup)
         bumperMeshes.push(bumperGroup)
      })
    }

    // Drop Targets - Enhanced with beveled edges and gradient colors
    if (config.drop_targets) {
      flippers.dropTargets = [] // Initialize array

      // 2D representation for top-down view
      const target2DGeo = new THREE.PlaneGeometry(1, 1)

      config.drop_targets.forEach((t, idx) => {
        const w = t.width * 0.6
        const h = 0.04 // Slightly taller
        const d = t.height * 1.2
        
        // Colorful gradient targets
        const colors = [0xff00ff, 0x00ffff, 0xffff00, 0xff0088, 0x00ff88]
        const targetColor = colors[idx % colors.length]

        const targetMat = new THREE.MeshStandardMaterial({
          color: targetColor,
          roughness: 0.4,
          metalness: 0.5,
          emissive: targetColor,
          emissiveIntensity: 0.3
        })

        const target = new THREE.Mesh(new THREE.BoxGeometry(w, d, h), targetMat)
        target.position.set(mapX(t.x), mapY(t.y), h/2)
        target.castShadow = true

        // Add 2D representation for top-down view (flat rectangle on floor)
        const target2DMat = new THREE.MeshBasicMaterial({
          color: targetColor,
          side: THREE.DoubleSide
        })
        const target2D = new THREE.Mesh(target2DGeo, target2DMat)
        target2D.scale.set(w, d, 1)
        target2D.position.set(mapX(t.x), mapY(t.y), 0.001) // Just above floor
        tableGroup.add(target2D)

        tableGroup.add(target)
        flippers.dropTargets.push(target)
      })
    }

    // Rails - Chrome-finished guide tubes
    if (config.rails) {
      const railRadius = 0.008 // Thickness of rail tube
      const railHeight = 0.04 // Height above playfield

      // Rail material - chrome finish
      const railMat = new THREE.MeshStandardMaterial({
        color: 0xcccccc,
        roughness: 0.2,
        metalness: 0.9,
        emissive: 0x444444,
        emissiveIntensity: 0.2
      })

      config.rails.forEach((rail, index) => {
        // Calculate start and end positions in 3D space
        const x1 = mapX(rail.p1.x)
        const y1 = mapY(rail.p1.y)
        const x2 = mapX(rail.p2.x)
        const y2 = mapY(rail.p2.y)

        // Calculate distance between points
        const dx = x2 - x1
        const dy = y2 - y1
        const length = Math.sqrt(dx * dx + dy * dy)

        // Create cylinder geometry for the rail
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

        // Store rail metadata for editing
        railMesh.userData = {
          railIndex: index,
          type: 'rail',
          p1: rail.p1,
          p2: rail.p2
        }

        tableGroup.add(railMesh)
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

  // Enhanced flipper material - vibrant red with metallic finish
  const flipperMat = new THREE.MeshStandardMaterial({
    color: 0xff0000, // Bright red
    roughness: 0.3,
    metalness: 0.7,
    emissive: 0x880000,
    emissiveIntensity: 0.2
  })

  // Left Flipper
  const leftPivot = new THREE.Group()
  // Default fallback if config missing
  let lx = -0.26
  let ly = -0.48
  
  if (config && config.left_flipper_pos_x !== undefined) {
      // Physics pivot is at (x_min, y_max)
      lx = mapX(config.left_flipper_pos_x)
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
      rx = mapX(config.right_flipper_pos_x_max)
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


const updateBalls = (ballData) => {
  if (!ballData) return
  
  // Get current combo for visual effects
  const combo = props.stats?.combo_count || 0

  // Create new balls if needed
  while (balls.length < ballData.length) {
    const ball = new THREE.Mesh(ballGeo, ballMat.clone()) 
    ball.castShadow = true

    // Add point light for glow effect
    const glowLight = new THREE.PointLight(0xffffff, 0, 0.2)
    ball.add(glowLight)
    ballGlows.push(glowLight)

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
}

// Update ball appearance and emit particles
const updateBallAppearance = (ball, glow, pGroup, combo, ballPos, prevPos) => {
  if (!ball || !ball.material) return

  const material = ball.material

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
      glow.intensity = 0
      emitRate = 0
  } else {
      // Dynamic settings - TUNED FOR SUBTLETY & VOLUME
      if (combo < 20) {
          // Grey Smoke - Ball Gold/Orange
          material.color.setHex(0xffaa00) // Gold
          material.emissive.setHex(0xff4400) // Orange glow
          material.emissiveIntensity = 0.5 
          glow.intensity = 0.5
          
          emitRate = 1 // 1 per frame
          pColor = 0xaaaaaa
          pSize = 0.015
          pType = 'smoke'
          pOpacity = 0.05 // Very transparent (was 0.15+)
          pLifeDecay = 0.005 // Lingers for ~200 frames (3s)
          pGrowth = 1.02 // Steady growth
      } else if (combo < 30) {
          // Blue/Cyan Smoke
          material.color.setHex(0xccffff) 
          material.emissive.setHex(0x00ffff)
          material.emissiveIntensity = 0.6 
          glow.color.setHex(0x00ffff)
          glow.intensity = 0.6
          
          emitRate = 2
          pColor = 0x0088ff
          pOpacity = 0.08 // Very transparent
          pSize = 0.02
          pLifeDecay = 0.008 
          pGrowth = 1.03
      } else if (combo < 40) {
           // Purple Magic
           material.color.setHex(0xffccff)
           material.emissive.setHex(0xff00ff)
           material.emissiveIntensity = 0.7
           glow.color.setHex(0xff00ff)
           glow.intensity = 0.7
           
           emitRate = 3
           pColor = 0xff00ff
           pOpacity = 0.10
           pSize = 0.022
           pLifeDecay = 0.01 
           pGrowth = 1.04
      } else if (combo < 50) {
           // Green Toxic
           material.color.setHex(0xbbddbb)
           material.emissive.setHex(0x00ff00)
           material.emissiveIntensity = 0.6
           glow.color.setHex(0x00ff00)
           glow.intensity = 0.6
           
           emitRate = 4
           pColor = 0x00ff00
           pOpacity = 0.12
           pSize = 0.025
           pGrowth = 1.05
           pLifeDecay = 0.012
      } else {
           // FIRE!!!
           const firePhase = (Date.now() % 500) / 500
           const fireColor = firePhase < 0.5 ? 0xff6600 : 0xffaa00
           
           material.color.setHex(0xffaa00)
           material.emissive.setHex(fireColor)
           material.emissiveIntensity = 0.8
           glow.color.setHex(fireColor)
           glow.intensity = 1.0

           emitRate = 5
           pColor = fireColor
           pOpacity = 0.15 // Still transparent even for fire
           pSize = 0.03
           pGrowth = 1.06 
           pLifeDecay = 0.015 
      }
  }

  // Apply Smoke Intensity Setting
  if (smokeIntensity.value !== 1.0) {
      if (smokeIntensity.value <= 0) {
          emitRate = 0
      } else {
          emitRate = Math.round(emitRate * smokeIntensity.value)
          pOpacity = Math.min(1.0, pOpacity * Math.sqrt(smokeIntensity.value))
      }
  }

  // Emit Particles with Interpolation
  if (pGroup) {
      if (emitRate > 0) {
          spawnParticles(pGroup, emitRate, ballPos, prevPos, pColor, pOpacity, pSize, pGrowth, pLifeDecay)
      } else {
          // Allow natural decay - Removing the forced rapid decay
          // This lets the smoke "hang" in the air as requested
      }
      animateParticleSystem(pGroup)
  }
}

const spawnParticles = (pGroup, count, currentPos, prevPos, color, opacity, size, growth, decay) => {
    const pool = pGroup.userData.pool
    let spawned = 0
    
    // Determine how many particles to reuse/create
    const totalToSpawn = count
    
    // Spawn loop - Use FOR loop to guarantee termination
    for (let i = 0; i < totalToSpawn; i++) {
        let p = pool.find(p => !p.visible)
        
        // If no dead particle found, try to create new if under limit
        if (!p && pool.length < 300) { 
            const geo = new THREE.SphereGeometry(1, 6, 6)
            const mat = new THREE.MeshBasicMaterial({ transparent: true })
            p = new THREE.Mesh(geo, mat)
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

const animateParticleSystem = (pGroup) => {
    const pool = pGroup.userData.pool
    pool.forEach(p => {
        if (!p.visible) return
        
        const data = p.userData
        
        // Move
        p.position.add(data.velocity)
        
        // Grow
        p.scale.multiplyScalar(data.growth)
        
        // Fade
        data.life -= data.decay
        if (data.life <= 0) {
            p.visible = false
        } else {
            p.material.opacity = data.life * data.baseOpacity
        }
    })
}

const updateFlippers = (state) => {
  if (!state.flippers) return
  const flipperData = state.flippers
  if (flippers.left) {
    // Negate angle because Physics +30 is Down, but Three.js +30 is Up
    flippers.left.rotation.z = THREE.MathUtils.degToRad(-flipperData.left_angle)
  }
  
  if (flippers.right) {
    // Physics angle is now symmetric (-30 to 30).
    // Visual mesh extends +X (Right).
    // We want it to point Left-Down (210 deg) when angle is -30.
    // 180 - (-30) = 210.
    // We want Left-Up (150 deg) when angle is 30.
    // 180 - 30 = 150.
    // So 180 - angle is correct.
    flippers.right.rotation.z = THREE.MathUtils.degToRad(180 - flipperData.right_angle)
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

let animationId
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

    if (controls) controls.update()

    renderer.render(scene, camera)
    
    camera.position.x = originalX // Restore
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

const initThree = () => {
  scene = new THREE.Scene()
  scene.background = new THREE.Color(0x1a1a28) // Brighter background (was #0a0a15)

  // Initial size (will be updated by ResizeObserver)
  const width = container.value.clientWidth
  const height = container.value.clientHeight
  const aspect = width / height

  camera = new THREE.PerspectiveCamera(45, aspect, 0.1, 100)
  camera.position.set(0, -1.5, 0.9) 
  camera.lookAt(0, 0, 0)

  renderer = new THREE.WebGLRenderer({ antialias: true })
  renderer.setSize(width, height)
  renderer.shadowMap.enabled = true
  renderer.shadowMap.type = THREE.PCFSoftShadowMap // Softer shadows
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
  dirLight.shadow.mapSize.width = 2048
  dirLight.shadow.mapSize.height = 2048
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
      ONE: THREE.TOUCH.NONE, // Disable 1-finger interaction 
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
  const activeBallCount = ref(0)
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
      if (camera && renderer) {
        camera.aspect = width / height
        camera.updateProjectionMatrix()
        renderer.setSize(width, height)
      }
    }
  })
  if (container.value) {
    resizeObserver.observe(container.value)
  }

  // Use shared socket from props
  const socket = props.socket
  
  // Remove existing listeners to avoid duplicates if re-mounted?
  // Socket.io ensures one listener per event usually if using .on, but if we re-mount we might duplicate.
  // Ideally we should clean up in onUnmounted.
  
  const onConnect = () => {
    console.log('Pinball3D Socket Connected')
  }

  
  const updateDropTargets = (dropTargetStates) => {
    if (!flippers.dropTargets || !dropTargetStates) return
    
    flippers.dropTargets.forEach((mesh, i) => {
      if (i < dropTargetStates.length) {
        mesh.visible = dropTargetStates[i]
      }
    })
  }

  const updateBumpers = (bumperStates) => {
    if (!flippers.bumpers || !bumperStates) return
    
    flippers.bumpers.forEach((bumperGroup, i) => {
      if (i < bumperStates.length) {
        const active = bumperStates[i] > 0
        const domeMesh = bumperGroup.userData.domeMesh
        const ringMesh = bumperGroup.userData.ringMesh
        const lights = bumperGroup.userData.lights

        // Set active state for animation control
        bumperGroup.userData.isActive = active

        // Store hit timestamp for scale animation
        if (active && !bumperGroup.userData.lastHitTime) {
          bumperGroup.userData.lastHitTime = Date.now()
        } else if (!active) {
          bumperGroup.userData.lastHitTime = null
        }

        if (active) {
            // Make everything white and bright during hit
            if (domeMesh) {
              domeMesh.material.color.setHex(0xffffff)
              domeMesh.material.emissive.setHex(0xffffff)
            }
            if (ringMesh) {
              ringMesh.material.color.setHex(0xffffff)
              ringMesh.material.emissive.setHex(0xffffff)
              ringMesh.material.emissiveIntensity = 2.0
            }
            // Lights set to white (animation will make them blink fast)
            if (lights) {
              lights.forEach(light => {
                light.material.color.setHex(0xffffff)
                light.material.emissive.setHex(0xffffff)
              })
            }
        } else {
            // Return to normal UFO appearance
            if (domeMesh) {
              domeMesh.material.color.setHex(0xcccccc)
              domeMesh.material.emissive.setHex(0x666666)
            }
            if (ringMesh) {
              ringMesh.material.color.setHex(0x888888)
              ringMesh.material.emissive.setHex(0x444444)
              ringMesh.material.emissiveIntensity = 0.3
            }
            // Lights will be restored to rainbow by animation
        }
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

  const onGameState = (state) => {
    if (!state || !state.balls) return
    updateBalls(state.balls)
    activeBallCount.value = state.balls.length // Track active balls
    updateFlippers(state)
    updateDropTargets(state.drop_targets)
    updateBumpers(state.bumper_states)

    // Handle Sound Events
    if (state.events && state.events.length > 0) {
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

 // If already connected
  if (socket.connected) {
      onConnect()
  }

  socket.on('connect', onConnect)
  socket.on('game_state', onGameState)
  socket.on('stuck_ball', onStuckBall)
  // socket.on('physics_config_loaded', onConfigLoaded) // Removed
  
  // Store cleanup function
  container.value._cleanupSocket = () => {
      socket.off('connect', onConnect)
      socket.off('game_state', onGameState)
      socket.off('stuck_ball', onStuckBall)
      // socket.off('physics_config_loaded', onConfigLoaded) // Removed
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
    camera.position.set(0, 0, 5)
    camera.lookAt(0, 0, 0)
    camera.rotation.z = Math.PI / 2 // Rotate to match 2D orientation (if needed)
    // Actually, Three.js Y is Up in 2D?
    // Table is 0.6 x 1.2.
    // If we look down Z. X is Right. Y is Up.
    // This matches standard 2D view.
    camera.rotation.set(0, 0, 0) // Reset rotation
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
})

// Function to update visibility of 3D vs 2D elements based on camera mode
const updateVisibilityForCameraMode = (mode) => {
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
const updateTable = (config) => {
  // Update Bumpers
  if (config.bumpers && flippers.bumpers && config.bumpers.length === flippers.bumpers.length) {
    config.bumpers.forEach((b, i) => {
      const mesh = flippers.bumpers[i]
      if (mesh) mesh.position.set(mapX(b.x), mapY(b.y), 0.025)
    })
  } else {
    // Count mismatch, full rebuild
    createTable(config)
    return
  }

  // Update Rails
  // Note: This assumes rail count matches. If not, we should rebuild.
  // But we don't store rail meshes in a convenient list matching config index?
  // createTable adds them to tableGroup but doesn't store them in flippers list (except bumpers/dropTargets).
  // I need to update createTable to store rails in flippers.rails or similar.
  // For now, let's just call createTable for now if it's not just bumpers.
  // Or better: Update createTable to store rails.
  
  // Since I can't easily update createTable in this Replace block without changing more code,
  // I will fallback to createTable for now if it's not just bumpers.
  // But wait, I don't know if it's just bumpers.
  
  // Let's just call createTable for now. It SHOULD be fast enough.
  // The user's issue might be that the watcher wasn't firing or something else.
  // But if I use this block, I can at least debug.
  
  createTable(config)
  camera.updateProjectionMatrix()
}

const activateControls = () => {
    if (controls && !controlsActive.value) {
        controls.enabled = true
        controlsActive.value = true
        // Optional: Reset if needed, or just unlock
    }
}

// Cache last camera config to detect actual changes
const lastCameraConfig = ref({})

// Watch for config changes from parent (must be after createTable is defined)
watch(() => props.config, (newConfig, oldConfig) => {
    if (!newConfig) return
    if (isDragging.value) return

    console.log('[Pinball3D] Config watcher fired')

    // Compare against our stored non-reactive values
    const flipperLengthChanged = newConfig.flipper_length !== lastFlipperValues.length
    const flipperWidthChanged = newConfig.flipper_width !== lastFlipperValues.width
    const flipperTipWidthChanged = newConfig.flipper_tip_width !== lastFlipperValues.tipWidth
    const flipperChanged = flipperLengthChanged || flipperWidthChanged || flipperTipWidthChanged

    // Update physicsConfig
    physicsConfig.value = newConfig
    
    // Always rebuild if no old config (first load)
    if (lastFlipperValues.length === null) {
        console.log('[Pinball3D] Initial load, rebuilding table')
        lastFlipperValues.length = newConfig.flipper_length
        lastFlipperValues.width = newConfig.flipper_width
        lastFlipperValues.tipWidth = newConfig.flipper_tip_width
        createTable(newConfig)
        updateCamera()
        return
    }

    if (flipperChanged) {
        console.log('[Pinball3D] Flipper properties changed, rebuilding table')
        if (flipperLengthChanged) console.log(`  flipper_length: ${lastFlipperValues.length} -> ${newConfig.flipper_length}`)
        if (flipperWidthChanged) console.log(`  flipper_width: ${lastFlipperValues.width} -> ${newConfig.flipper_width}`)
        if (flipperTipWidthChanged) console.log(`  flipper_tip_width: ${lastFlipperValues.tipWidth} -> ${newConfig.flipper_tip_width}`)

        // Update stored values
        lastFlipperValues.length = newConfig.flipper_length
        lastFlipperValues.width = newConfig.flipper_width
        lastFlipperValues.tipWidth = newConfig.flipper_tip_width

        createTable(newConfig)
        updateCamera()
        return
    }

    // Check if any non-camera property changed
    const cameraProps = ['camera_x', 'camera_y', 'camera_z', 'camera_pitch', 'camera_zoom']
    const allKeys = Object.keys(newConfig)
    const nonCameraChanged = allKeys.some(key => {
        if (cameraProps.includes(key)) return false

        // Deep equality check for arrays/objects
        if (Array.isArray(newConfig[key]) && Array.isArray(oldConfig[key])) {
            return JSON.stringify(newConfig[key]) !== JSON.stringify(oldConfig[key])
        }
        return newConfig[key] !== oldConfig[key]
    })

    if (nonCameraChanged) {
        console.log('[Pinball3D] Non-camera properties changed, rebuilding table')
        createTable(newConfig)
    } else {
        console.log('[Pinball3D] Only camera properties changed, skipping table rebuild')
    }

    // Update Camera Position if in perspective mode AND camera params changed
    if (props.cameraMode === 'perspective') {
        let cameraChanged = false
        
        // Check against cached config
        const currentCam = {
            x: newConfig.camera_x,
            y: newConfig.camera_y,
            z: newConfig.camera_z,
            pitch: newConfig.camera_pitch,
            zoom: newConfig.camera_zoom
        }
        
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

const triggerShake = (direction) => {
  console.log('Pinball3D: triggerShake called')
  const intensity = 0.2
  const dir = direction.toLowerCase() === 'left' ? -1 : 1
  
  // Simple shake animation loop
  let frame = 0
  const maxFrames = 10
  
  const shake = () => {
    if (frame >= maxFrames) {
      shakeOffset.x = 0
      return
    }
    
    // Oscillate
    const decay = 1 - (frame / maxFrames)
    shakeOffset.x = Math.sin(frame * 1.5) * intensity * decay * dir
    
    frame++
    requestAnimationFrame(shake)
  }
  shake()
}

onUnmounted(() => {
  if (container.value && container.value._cleanupSocket) {
      container.value._cleanupSocket()
  }
  window.removeEventListener('keydown', handleKeydown)
  // Cleanup Three.js
  if (animationId) cancelAnimationFrame(animationId)
  
  window.removeEventListener('keydown', handleKeydown)
  
  if (tableGroup) {
    // Dispose table resources
    tableGroup.traverse((obj) => {
      if (obj.geometry) obj.geometry.dispose()
      if (obj.material) {
        if (Array.isArray(obj.material)) {
          obj.material.forEach(mat => mat.dispose())
        } else {
          obj.material.dispose()
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

.pinball-container.controls-active {
  border-color: #0088ff; /* Blue border to indicate active state */
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
    right: 10px;
    width: 90%;
    z-index: 100;
    display: flex;
    flex-direction: column-reverse;
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
    flex-direction: column;
    gap: 5px;
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
    top: 10px;
    right: 10px;
    background: rgba(0, 0, 0, 0.6);
    border: none;
    border-radius: 50%;
    width: 40px;
    height: 40px;
    font-size: 20px;
    cursor: pointer;
    z-index: 10000;
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    transition: background 0.2s;
}

.sound-toggle-btn:hover {
    background: rgba(0, 0, 0, 0.8);
}

.sound-settings-overlay {
    position: absolute;
    top: 60px;
    right: 10px;
    z-index: 200;
}

.editor-controls button.active {
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

.object-drawer {
    margin-bottom: 10px;
    border-bottom: 1px solid #555;
    padding-bottom: 10px;
}
.drawer-title {
    font-size: 12px;
    color: #aaa;
    margin-bottom: 5px;
}
.drawer-item {
    display: flex;
    align-items: center;
    gap: 5px;
    background: #444;
    padding: 5px;
    margin-bottom: 5px;
    border-radius: 3px;
    cursor: grab;
}
.drawer-item:active {
    cursor: grabbing;
}
.icon {
    width: 16px;
    height: 16px;
    background: #666;
}
.rail-icon {
    background: linear-gradient(45deg, transparent 45%, #fff 45%, #fff 55%, transparent 55%);
}
.bumper-icon {
    border-radius: 50%;
    background: #ffaa00;
}

.loading-placeholder {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: #111;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #888;
  font-family: 'Segoe UI', sans-serif;
  z-index: 50;
}

.spinner {
  width: 40px;
  height: 40px;
  border: 4px solid #333;
  border-top: 4px solid #4caf50;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-bottom: 15px;
}

.loading-text {
  font-size: 1.2em;
  letter-spacing: 1px;
  animation: pulse-text 1.5s ease-in-out infinite alternate;
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
  z-index: 20; /* Above training overlay and canvas */
  pointer-events: none; /* Let clicks pass through if needed, though usually Game Over stops input */
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
</style>
