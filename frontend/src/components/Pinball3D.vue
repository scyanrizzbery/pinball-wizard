<template>
  <div ref="container" class="pinball-container" :style="{ width: width + 'px', height: height + 'px' }">
    <button @click="$emit('toggle-view')" class="switch-view-btn">
      {{ cameraMode === 'perspective' ? 'Switch to 2D' : 'Switch to 3D' }}
    </button>
    <div v-if="cameraMode === 'perspective' && showDebug" class="debug-overlay">
      <div>Camera X: {{ cameraDebug.x.toFixed(2) }}</div>
      <div>Camera Y: {{ cameraDebug.y.toFixed(2) }}</div>
      <div>Camera Z: {{ cameraDebug.z.toFixed(2) }}</div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'
import * as THREE from 'three'

  const props = defineProps({
  width: Number,
  height: Number,
  socket: Object,
  socket: Object,
  config: Object,
  nudgeEvent: Object,
  cameraMode: { type: String, default: 'perspective' }
})

const emit = defineEmits(['toggle-view'])

const container = ref(null)
let scene, camera, renderer
// let socket // Use props.socket
let balls = [] // Array of mesh objects
let flippers = {} // { left: mesh, right: mesh, upper: [] }
let tableGroup

// Physics Config (to sync dimensions)
let physicsConfig = ref(null)
const cameraDebug = ref({ x: 0, y: 0, z: 0 })
const showDebug = ref(false)
let debugTimeout = null

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
  
  // Clear existing balls and flippers so they are recreated in the new group
  balls = []
  flippers = { left: null, right: null, dropTargets: [] }

  // Floor
  const floorGeo = new THREE.PlaneGeometry(0.6, 1.2)
  const floorMat = new THREE.MeshStandardMaterial({ color: 0x222222, roughness: 0.4, metalness: 0.6 })
  const floor = new THREE.Mesh(floorGeo, floorMat)
  floor.receiveShadow = true
  tableGroup.add(floor)

  // Walls
  const wallMat = new THREE.MeshStandardMaterial({ color: 0x444444 })
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
    // Top Arch (Visual)
    const archShape = new THREE.Shape()
    archShape.moveTo(mapX(1.0), mapY(0.15))
    archShape.lineTo(mapX(0.6), mapY(0.0))
    archShape.lineTo(mapX(1.0), mapY(0.0))
    archShape.lineTo(mapX(1.0), mapY(0.15))
    
    const archGeo = new THREE.ExtrudeGeometry(archShape, { depth: 0.05, bevelEnabled: false })
    const archMat = new THREE.MeshStandardMaterial({ color: 0x555555 })
    const arch = new THREE.Mesh(archGeo, archMat)
    tableGroup.add(arch)

    // Triangle Guide - Top-Left (mirror of top-right arch)
    const leftGuideShape = new THREE.Shape()
    leftGuideShape.moveTo(mapX(0.0), mapY(0.15))
    leftGuideShape.lineTo(mapX(0.4), mapY(0.0))
    leftGuideShape.lineTo(mapX(0.0), mapY(0.0))
    leftGuideShape.lineTo(mapX(0.0), mapY(0.15))
    
    const leftGuideGeo = new THREE.ExtrudeGeometry(leftGuideShape, { depth: 0.05, bevelEnabled: false })
    const leftGuideMat = new THREE.MeshStandardMaterial({ color: 0x555555 })
    const leftGuide = new THREE.Mesh(leftGuideGeo, leftGuideMat)
    tableGroup.add(leftGuide)

    // Bumpers
    if (config.bumpers) {
      const bumperGeo = new THREE.CylinderGeometry(0.025, 0.025, 0.05, 32)
      const bumperMat = new THREE.MeshStandardMaterial({ color: 0xffaa00 })
      config.bumpers.forEach(b => {
         const mesh = new THREE.Mesh(bumperGeo, bumperMat)
         mesh.rotation.x = Math.PI / 2
         mesh.position.set(mapX(b.x), mapY(b.y), 0.025)
         tableGroup.add(mesh)
      })
    }

    // Drop Targets
    if (config.drop_targets) {
      const targetMat = new THREE.MeshStandardMaterial({ color: 0xffaa00 })
      flippers.dropTargets = [] // Initialize array
      config.drop_targets.forEach(t => {
        const w = t.width * 0.6
        const h = 0.03 
        const d = t.height * 1.2 
        
        const target = new THREE.Mesh(new THREE.BoxGeometry(w, d, h), targetMat)
        target.position.set(mapX(t.x), mapY(t.y), h/2)
        tableGroup.add(target)
        flippers.dropTargets.push(target) // Store reference for updates
      })
    }







  }
  // Flippers
  // Flippers
  // Use config.flipper_length (fraction of width) * table width (0.6)
  // Default flipper_length in physics is 0.2. 0.2 * 0.6 = 0.12 (matches previous hardcoded value)
  const flipperLength = (config && config.flipper_length) ? config.flipper_length * 0.6 : 0.12
  const flipperWidth = 0.02
  const flipperHeight = 0.04
  const flipperGeo = new THREE.BoxGeometry(flipperLength, flipperWidth, flipperHeight)
  const flipperMat = new THREE.MeshStandardMaterial({ color: 0xff0000 })

  // Left Flipper
  const leftPivot = new THREE.Group()
  // Default fallback if config missing
  let lx = -0.18
  let ly = -0.48
  
  if (config && config.left_flipper_pos_x !== undefined) {
      // Physics pivot is at (x_min, y_max)
      lx = mapX(config.left_flipper_pos_x)
      ly = mapY(config.left_flipper_pos_y_max)
  }
  
  leftPivot.position.set(lx, ly, 0.02)
  tableGroup.add(leftPivot)
  
  const leftMesh = new THREE.Mesh(flipperGeo, flipperMat)
  leftMesh.position.set(flipperLength / 2, 0, 0) 
  leftPivot.add(leftMesh)
  flippers.left = leftPivot

  // Right Flipper
  const rightPivot = new THREE.Group()
  // Default fallback
  let rx = 0.18
  let ry = -0.48
  
  if (config && config.right_flipper_pos_x_max !== undefined) {
      // Physics pivot is at (x_max, y_max)
      rx = mapX(config.right_flipper_pos_x_max)
      ry = mapY(config.right_flipper_pos_y_max)
  }
  
  rightPivot.position.set(rx, ry, 0.02)
  tableGroup.add(rightPivot)
  
  const rightMesh = new THREE.Mesh(flipperGeo, flipperMat)
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
  // So Pivot is at "Left" of the mesh (which is now Right in world space due to rotation).
  // So the mesh setup is actually symmetric (both extend Right from pivot), and rotation handles the direction.
  // So we keep the mesh position as is.
  
  rightMesh.position.set(flipperLength / 2, 0, 0)
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
  tableGroup.add(plunger)
  flippers.plunger = plunger

  // Left Plunger (Kickback)
  const leftPlunger = createPlungerMesh(0x888888)
  leftPlunger.position.set(mapX(0.075), mapY(0.95), 0.02)
  tableGroup.add(leftPlunger)
  flippers.leftPlunger = leftPlunger
}

// Ball
const ballGeo = new THREE.SphereGeometry(0.016, 32, 32)
const ballMat = new THREE.MeshStandardMaterial({ 
  color: 0xcccccc,
  metalness: 0.9,
  roughness: 0.1
})

const updateBalls = (ballData) => {
  if (!ballData) return
  
  while (balls.length < ballData.length) {
    const ball = new THREE.Mesh(ballGeo, ballMat)
    ball.castShadow = true
    tableGroup.add(ball)
    balls.push(ball)
  }
  
  while (balls.length > ballData.length) {
    const ball = balls.pop()
    tableGroup.remove(ball)
  }
  
  ballData.forEach((data, i) => {
    const tx = (data.x - 0.5) * 0.6
    const ty = (0.5 - data.y) * 1.2
    balls[i].position.set(tx, ty, 0.03)
  })
}

const updateFlippers = (state) => {
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
      // Physics Y is in pixels (0 to height)
      // MapY expects normalized 0-1
      const normalizedY = state.plunger.y / props.height
      flippers.plunger.position.y = mapY(normalizedY)
  }

  if (flippers.leftPlunger && state.left_plunger) {
      const normalizedY = state.left_plunger.y / props.height
      flippers.leftPlunger.position.y = mapY(normalizedY)
  }
}

const animate = () => {
  requestAnimationFrame(animate)
  if (renderer && scene && camera) {
    // Apply shake offset to camera position (temporarily)
    const basePos = { x: 0, y: -1.5, z: 2.5 } // Default position, should track actual camera pos if moved
    // Better: Apply offset to camera.position relative to its current "base"
    // But camera moves with keys. 
    // Let's just modify the lookAt target or add a shake group?
    // Simplest: Add shakeOffset to camera.position before render, remove after.
    
    const originalX = camera.position.x
    camera.position.x += shakeOffset.x
    
    renderer.render(scene, camera)
    
    camera.position.x = originalX // Restore
  }
}

const initThree = () => {
  scene = new THREE.Scene()
  scene.background = new THREE.Color(0x111111)

  const aspect = props.width / props.height
  camera = new THREE.PerspectiveCamera(45, aspect, 0.1, 100)
  camera.position.set(0, -1.5, 0.9) 
  camera.lookAt(0, 0, 0)

  renderer = new THREE.WebGLRenderer({ antialias: true })
  renderer.setSize(props.width, props.height)
  renderer.shadowMap.enabled = true
  container.value.appendChild(renderer.domElement)

  const ambientLight = new THREE.AmbientLight(0x404040, 0.5) 
  scene.add(ambientLight)

  const dirLight = new THREE.DirectionalLight(0xffffff, 1)
  dirLight.position.set(1, -2, 3)
  dirLight.castShadow = true
  scene.add(dirLight)
  
  const pointLight = new THREE.PointLight(0x00aaff, 0.5, 10)
  pointLight.position.set(0, 0, 1)
  scene.add(pointLight)

  // Initial creation (likely empty config until prop updates)
  createTable(props.config)
  
  animate()
}

onMounted(() => {
  initThree()
  
  // Use shared socket from props
  const socket = props.socket
  
  // Remove existing listeners to avoid duplicates if re-mounted?
  // Socket.io ensures one listener per event usually if using .on, but if we remount we might duplicate.
  // Ideally we should clean up in onUnmounted.
  
  const onConnect = () => {
    console.log('Pinball3D Socket Connected')
    socket.emit('load_physics')
  }
  
  
  const updateDropTargets = (dropTargetStates) => {
    if (!flippers.dropTargets || !dropTargetStates) return
    
    flippers.dropTargets.forEach((mesh, i) => {
      if (i < dropTargetStates.length) {
        mesh.visible = dropTargetStates[i]
      }
    })
  }
  
  const onGameState = (state) => {
    updateBalls(state.balls)
    updateFlippers(state)
    updateDropTargets(state.drop_targets)
  }
  
  // REMOVED: onConfigLoaded listener (handled by prop)

  // If already connected
  if (socket.connected) {
      onConnect()
  }

  socket.on('connect', onConnect)
  socket.on('game_state', onGameState)
  // socket.on('physics_config_loaded', onConfigLoaded) // Removed
  
  // Store cleanup function
  container.value._cleanupSocket = () => {
      socket.off('connect', onConnect)
      socket.off('game_state', onGameState)
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
       const cz = physicsConfig.value.camera_z * 0.6
       camera.position.set(cx, cy, cz)
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
})

// Watch for config changes from parent (must be after createTable is defined)
watch(() => props.config, (newConfig, oldConfig) => {
  if (newConfig) {
    console.log('Pinball3D received new config via prop', newConfig)
    physicsConfig.value = newConfig
    createTable(newConfig)

    // Update Camera Position if in perspective mode AND camera params changed
    if (props.cameraMode === 'perspective') {
        let cameraChanged = true
        if (oldConfig) {
            cameraChanged = (
                newConfig.camera_x !== oldConfig.camera_x ||
                newConfig.camera_y !== oldConfig.camera_y ||
                newConfig.camera_z !== oldConfig.camera_z ||
                newConfig.camera_pitch !== oldConfig.camera_pitch ||
                newConfig.camera_zoom !== oldConfig.camera_zoom
            )
        }
        
        if (cameraChanged) {
            console.log('Pinball3D: Camera params changed, updating camera')
            updateCamera()
        }
    }
  }
})

// Nudge Animation (Camera Shake)
const lastNudgeTime = ref(props.nudgeEvent?.time || 0)
watch(() => props.nudgeEvent, (newVal) => {
  // console.log('Pinball3D: nudgeEvent watcher fired', newVal)
  if (newVal && newVal.time > lastNudgeTime.value) {
    lastNudgeTime.value = newVal.time
    // console.log('Pinball3D: Triggering shake for', newVal.direction)
    triggerShake(newVal.direction)
  } else {
    // console.log('Pinball3D: Ignoring nudge (old timestamp or null)')
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
  if (renderer) {
      renderer.dispose()
      // Dispose scene...
  }
})

const handleKeydown = (e) => {
  if (!camera) return
  
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
.pinball-3d-container {
  width: 100%;
  height: 100%;
  overflow: hidden;
  position: relative;
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
</style>
