<template>
  <div ref="container" class="pinball-container">
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
  socket: Object,
  config: Object,
  nudgeEvent: Object,
  cameraMode: { type: String, default: 'perspective' }
})

const emit = defineEmits(['toggle-view'])

const container = ref(null)
let scene, camera, renderer
let resizeObserver
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
  balls = []
  flippers = { left: null, right: null, dropTargets: [], bumpers: [] }

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
      const baseMat = new THREE.MeshStandardMaterial({ color: 0xffaa00 })
      config.bumpers.forEach(b => {
         const mat = baseMat.clone() // Clone for individual color control
         const mesh = new THREE.Mesh(bumperGeo, mat)
         mesh.rotation.x = Math.PI / 2
         mesh.position.set(mapX(b.x), mapY(b.y), 0.025)
         tableGroup.add(mesh)
         flippers.bumpers.push(mesh)
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





    // Zones
    if (config.zones) {
      config.zones.forEach(zone => {
        if (!zone.points || zone.points.length < 3) return

        const shape = new THREE.Shape()
        const first = zone.points[0]
        shape.moveTo(mapX(first.x), mapY(first.y))
        
        for (let i = 1; i < zone.points.length; i++) {
          const p = zone.points[i]
          shape.lineTo(mapX(p.x), mapY(p.y))
        }
        shape.closePath()

        const geometry = new THREE.ShapeGeometry(shape)
        const color = zone.type === 'left' ? 0x00ff00 : 0x0000ff
        const material = new THREE.MeshBasicMaterial({ 
          color: color, 
          transparent: true, 
          opacity: 0.2,
          side: THREE.DoubleSide
        })
        
        const mesh = new THREE.Mesh(geometry, material)
        mesh.position.z = 0.01 // Slightly above floor
        tableGroup.add(mesh)
      })
    }

    // Rails (New)
    if (config.rails) {
      // Use same color as walls (0x444444)
      const railMat = new THREE.MeshStandardMaterial({ color: 0x444444 })
      const railHeight = 0.05
      const railThickness = 0.02
      
      config.rails.forEach(rail => {
        const p1 = rail.p1
        const p2 = rail.p2
        
        const x1 = mapX(p1.x)
        const y1 = mapY(p1.y)
        const x2 = mapX(p2.x)
        const y2 = mapY(p2.y)
        
        const vec = new THREE.Vector2(x2 - x1, y2 - y1)
        const len = vec.length()
        const angle = Math.atan2(vec.y, vec.x)
        
        const mesh = new THREE.Mesh(new THREE.BoxGeometry(1, 1, railHeight), railMat)
        mesh.position.set(x1 + vec.x/2, y1 + vec.y/2, railHeight/2)
        mesh.rotation.z = angle
        mesh.scale.set(len, railThickness, 1)
        tableGroup.add(mesh)
      })
    }
  }
  // Flippers
  // Flippers
  // Use config.flipper_length (fraction of width) * table width (0.6)
  // Default flipper_length in physics is 0.2. 0.2 * 0.6 = 0.12 (matches previous hardcoded value)
  const flipperLength = (config && config.flipper_length) ? config.flipper_length * 0.6 : 0.12
  const flipperWidth = (config && config.flipper_width) ? config.flipper_width * 0.6 : 0.02
  const flipperHeight = 0.04
  
  // Create rounded flipper shape (Stadium/Capsule 2D shape)
  const flipperShape = new THREE.Shape()
  const radius = flipperWidth / 2
  // The physics segment goes from (radius, 0) to (length-radius, 0)
  // We want to draw the outline of this segment with thickness 'flipperWidth'
  // Effectively, a rectangle from x=radius to x=length-radius with height=flipperWidth,
  // plus semicircles at x=radius and x=length-radius.
  // Actually, simpler: just draw the path.
  
  const segLen = flipperLength - flipperWidth // Distance between circle centers
  
  // Start at bottom-left of the straight part
  flipperShape.moveTo(radius, -radius)
  // Line to bottom-right
  flipperShape.lineTo(radius + segLen, -radius)
  // Semicircle at right end
  flipperShape.absarc(radius + segLen, 0, radius, -Math.PI/2, Math.PI/2, false)
  // Line to top-left
  flipperShape.lineTo(radius, radius)
  // Semicircle at left end
  flipperShape.absarc(radius, 0, radius, Math.PI/2, -Math.PI/2, false)
  
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

  const flipperMat = new THREE.MeshStandardMaterial({ color: 0xff0000 })

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
  leftMesh.position.set(flipperLength / 2, 0, 0) 
  leftPivot.add(leftMesh)
  flippers.left = leftPivot

  // Right Flipper
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
      const normalizedY = state.plunger.y / 800 // Use fixed physics height for normalization
      flippers.plunger.position.y = mapY(normalizedY)
  }

  if (flippers.leftPlunger && state.left_plunger) {
      const normalizedY = state.left_plunger.y / 800
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
  // Socket.io ensures one listener per event usually if using .on, but if we remount we might duplicate.
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
    
    flippers.bumpers.forEach((mesh, i) => {
      if (i < bumperStates.length) {
        const active = bumperStates[i] > 0
        if (active) {
            mesh.material.color.setHex(0x00ffff) // Cyan Flash
            mesh.material.emissive.setHex(0x00ffff)
            mesh.material.emissiveIntensity = 0.5
        } else {
            mesh.material.color.setHex(0xffaa00) // Orange
            mesh.material.emissive.setHex(0x000000)
            mesh.material.emissiveIntensity = 0.0
        }
      }
    })
  }
  
  const onGameState = (state) => {
    updateBalls(state.balls)
    updateFlippers(state)
    updateDropTargets(state.drop_targets)
    updateBumpers(state.bumper_states)
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
  if (resizeObserver) {
    resizeObserver.disconnect()
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
.pinball-container {
  display: flex;
  justify-content: center;
  align-items: center;
  width: 100%;
  height: 100%;
  overflow: hidden;
  position: absolute; /* Fill the aspect-ratio parent */
  top: 0;
  left: 0;
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
