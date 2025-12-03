<template>
  <div ref="container" class="pinball-container" 
       @mousedown="onMouseDown" 
       @mousemove="onMouseMove" 
       @mouseup="onMouseUp"
       @mouseleave="onMouseUp"
       @dragover.prevent
       @drop="onDrop">
    <button @click="$emit('toggle-view')" class="switch-view-btn">
      {{ cameraMode === 'perspective' ? 'Switch to 2D' : 'Switch to 3D' }}
    </button>
    <div v-if="cameraMode === 'perspective' && showDebug" class="debug-overlay">
      <div>Camera X: {{ cameraDebug.x.toFixed(2) }}</div>
      <div>Camera Y: {{ cameraDebug.y.toFixed(2) }}</div>
      <div>Camera Z: {{ cameraDebug.z.toFixed(2) }}</div>
    </div>
    
    <!-- Rail Editor Controls -->
    <div class="editor-controls" v-if="cameraMode === 'perspective'">
        <button @click="toggleEditMode" :class="{ active: isEditMode }">
            {{ isEditMode ? 'Done Editing' : 'Edit Rails' }}
        </button>
        <div v-if="isEditMode" class="edit-actions">
            <button @click="addRail">Add Rail</button>
            <button @click="deleteSelectedObject" :disabled="selectedRailIndex === -1 && selectedBumperIndex === -1">Delete Selected</button>
            <div v-if="selectedRailIndex !== -1" class="selected-info">
                Selected: {{ selectedRailIndex }}
            </div>
            
            <div class="object-drawer">
                <div class="drawer-title">Drag to Add:</div>
                <div class="drawer-item" draggable="true" @dragstart="onDragStart($event, 'rail')">
                    <span>Rail</span>
                </div>
                <div class="drawer-item" draggable="true" @dragstart="onDragStart($event, 'bumper')">
                    <span>Bumper</span>
                </div>
            </div>
        </div>
    </div>
    
    <!-- Stuck Ball Dialog -->
    <div v-if="stuckBallDialog" class="stuck-ball-dialog">
      <div class="dialog-content">
        <h2>BALL LOST! RE-LAUNCH?</h2>
        <div class="timer">{{ stuckBallTimer }}</div>
        <div class="buttons">
          <button @click="confirmRelaunch" class="confirm-btn">YES (Enter)</button>
          <button @click="cancelRelaunch" class="cancel-btn">NO (Esc)</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'
import * as THREE from 'three'

  const props = defineProps({
  socket: Object,
  configSocket: Object,
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
let ballGeo, ballMat

// Physics Config (to sync dimensions)
let physicsConfig = ref(null)
const cameraDebug = ref({ x: 0, y: 0, z: 0 })
const showDebug = ref(false)
let debugTimeout = null

// Stuck Ball State
const stuckBallDialog = ref(false)
const stuckBallTimer = ref(20)
let stuckBallInterval = null

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
  
  // Initialize ball resources
  ballGeo = new THREE.SphereGeometry(0.016, 32, 32)
  ballMat = new THREE.MeshStandardMaterial({ 
    color: 0xcccccc,
    metalness: 0.9,
    roughness: 0.1
  })
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
      config.bumpers.forEach((b, i) => {
         const mat = baseMat.clone() // Clone for individual color control
         const mesh = new THREE.Mesh(bumperGeo, mat)
         mesh.rotation.x = Math.PI / 2
         mesh.position.set(mapX(b.x), mapY(b.y), 0.025)
         mesh.userData = { bumperIndex: i, type: 'bumper' }
         tableGroup.add(mesh)
         flippers.bumpers.push(mesh)
         bumperMeshes.push(mesh)
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
      
      // Decoupled: 3D Rail should match Visual Rail (static), not Physics Rail (offset)
      // const offsetX = config.rail_x_offset || 0
      // const offsetY = config.rail_y_offset || 0

      config.rails.forEach((rail, index) => {
        const p1 = rail.p1
        const p2 = rail.p2
        
        const x1 = mapX(p1.x)
        const y1 = mapY(p1.y)
        const x2 = mapX(p2.x)
        const y2 = mapY(p2.y)
        
        // Debug log removed
        // if (index === 0) console.log(...)
        
        const vec = new THREE.Vector2(x2 - x1, y2 - y1)
        const len = vec.length()
        const angle = Math.atan2(vec.y, vec.x)
        
        const mesh = new THREE.Mesh(new THREE.BoxGeometry(1, 1, railHeight), railMat)
        mesh.position.set(x1 + vec.x/2, y1 + vec.y/2, railHeight/2)
        mesh.rotation.z = angle
        mesh.scale.set(len, railThickness, 1)
        mesh.userData = { railIndex: index, type: 'body' }
        railMeshes.push(mesh)
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
  leftMesh.position.set(-radius, 0, 0) 
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
  
  rightMesh.position.set(-radius, 0, 0)
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
  
  // Ensure camera is updated to match config immediately
  updateCamera()
  
  animate()
}

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
  // For now, let's just rebuild if we suspect rail changes?
  // Or better: Update createTable to store rails.
  
  // Since I can't easily update createTable in this Replace block without changing more code,
  // I will fallback to createTable for now if it's not just bumpers.
  // But wait, I don't know if it's just bumpers.
  
  // Let's just call createTable for now. It SHOULD be fast enough.
  // The user's issue might be that the watcher wasn't firing or something else.
  // But if I use this block, I can at least debug.
  
  createTable(config)
}

// Watch for config changes from parent (must be after createTable is defined)
watch(() => props.config, (newConfig, oldConfig) => {
  if (isDragging.value) return
  if (newConfig) {
    // console.log(`Pinball3D watcher fired.`)
    physicsConfig.value = newConfig
    
    if (newConfig !== oldConfig) {
        // Full replacement
        createTable(newConfig)
    } else {
        // Mutation
        // Try to update in place if possible, otherwise rebuild
        // For now, just rebuild to ensure correctness
        createTable(newConfig)
    }

    // Update Camera Position if in perspective mode AND camera params changed
    if (props.cameraMode === 'perspective') {
        let cameraChanged = true
        if (oldConfig && newConfig !== oldConfig) {
            cameraChanged = (
                newConfig.camera_x !== oldConfig.camera_x ||
                newConfig.camera_y !== oldConfig.camera_y ||
                newConfig.camera_z !== oldConfig.camera_z ||
                newConfig.camera_pitch !== oldConfig.camera_pitch ||
                newConfig.camera_zoom !== oldConfig.camera_zoom
            )
        }
        
        if (cameraChanged) {
            updateCamera()
        }
    }
  }
}, { deep: true })


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
    top: 10px;
    right: 10px;
    z-index: 100;
    display: flex;
    flex-direction: column;
    gap: 10px;
    background: rgba(0, 0, 0, 0.7);
    padding: 10px;
    border-radius: 5px;
}

.edit-actions {
    display: flex;
    flex-direction: column;
    gap: 5px;
}

.editor-controls button {
    background: #333;
    color: white;
    border: 1px solid #555;
    padding: 5px 10px;
    cursor: pointer;
    border-radius: 3px;
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
    margin-top: 10px;
    border-top: 1px solid #555;
    padding-top: 10px;
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
</style>
