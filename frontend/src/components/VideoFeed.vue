<template>
  <div id="video-container">
    <!-- Tilted Overlay -->
    <div id="tilted-overlay" v-if="isTilted">TILTED!</div>

    <div v-if="stats.is_training"
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
    
    <!-- DEBUG OVERLAY -->
    <div style="position: absolute; top: 10px; left: 10px; background: rgba(0,0,0,0.8); color: lime; padding: 5px; z-index: 9999; font-family: monospace; font-size: 12px; pointer-events: none; display: none">
      Offsets: X={{ physics.rail_x_offset }} Y={{ physics.rail_y_offset }}
    </div>
    <div id="video-wrapper" ref="containerElement" :style="zoomStyle">
      <div v-if="!videoSrc" class="loading-placeholder">
        <div class="spinner"></div>
        <div class="loading-text">CONNECTING...</div>
      </div>
      <img v-else id="video-stream" :src="videoSrc" alt="Pinball Game" ref="videoElement">
      
      <!-- Zone Editor Overlay (Polygon) -->
      <div v-if="showZones" class="zone-overlay">
        <svg viewBox="0 0 1 1" preserveAspectRatio="none" style="width: 100%; height: 100%; position: absolute; top: 0; left: 0; pointer-events: none;">
          <polygon v-for="(zone, index) in zones" :key="'zone-'+index"
                   :points="zone.svgPoints" 
                   class="zone-poly"
                   :class="{ 'left-zone': zone.type === 'left', 'right-zone': zone.type === 'right' }"
                   @mousedown="startDrag('zone', index, 'body', $event)"
                   @touchstart="startDrag('zone', index, 'body', $event)" />

          <!-- Rails -->
          <line v-for="(rail, index) in rails" :key="'rail-'+index"
                :x1="rail.screenP1.x" :y1="rail.screenP1.y"
                :x2="rail.screenP2.x" :y2="rail.screenP2.y"
                class="rail-line"
                @mousedown="startDrag('rail', index, 'body', $event)"
                @touchstart="startDrag('rail', index, 'body', $event)" />

          <!-- Bumpers -->
          <!-- Bumpers -->
          <circle v-for="(bumper, index) in bumpers" :key="'bumper-'+index"
                  :cx="bumper.screenPos.x" :cy="bumper.screenPos.y"
                  r="0.04"
                  class="bumper-circle"
                  @mousedown="startDrag('bumper', index, 'body', $event)"
                  @touchstart="startDrag('bumper', index, 'body', $event)" />

          <!-- Drop Targets -->
          <rect v-for="(target, index) in dropTargets" :key="'target-'+index"
                  :x="target.screenRect.x" :y="target.screenRect.y"
                  :width="target.screenRect.width" :height="target.screenRect.height"
                  class="target-rect"
                  @mousedown="startDrag('target', index, 'body', $event)"
                  @touchstart="startDrag('target', index, 'body', $event)" />


        </svg>

        <!-- Handles for all zones -->
        <template v-for="(zone, zIndex) in zones" :key="'zone-h-'+zIndex">
          <div v-for="(point, pIndex) in zone.screenPoints" :key="'z-'+zIndex + '-' + pIndex"
               class="handle"
               :style="{ left: (point.x * 100) + '%', top: (point.y * 100) + '%' }"
               @mousedown.stop="startDrag('zone', zIndex, pIndex, $event)"
               @touchstart.stop="startDrag('zone', zIndex, pIndex, $event)">
          </div>
          
          <!-- Delete Button (Center of zone) -->
          <div class="delete-btn"
               :style="{ 
                 left: ((zone.screenPoints[0].x + zone.screenPoints[2].x)/2 * 100) + '%', 
                 top: ((zone.screenPoints[0].y + zone.screenPoints[2].y)/2 * 100) + '%' 
               }"
               @click.stop="removeZone(zIndex)">
            ×
          </div>
        </template>

        <!-- Handles for Rails -->
        <template v-for="(rail, rIndex) in rails" :key="'rail-h-'+rIndex">
          <!-- P1 Handle -->
          <div class="handle rail-handle"
               :style="{ left: (rail.screenP1.x * 100) + '%', top: (rail.screenP1.y * 100) + '%' }"
               @mousedown.stop="startDrag('rail', rIndex, 'p1', $event)"
               @touchstart.stop="startDrag('rail', rIndex, 'p1', $event)">
          </div>
          <!-- P2 Handle -->
          <div class="handle rail-handle"
               :style="{ left: (rail.screenP2.x * 100) + '%', top: (rail.screenP2.y * 100) + '%' }"
               @mousedown.stop="startDrag('rail', rIndex, 'p2', $event)"
               @touchstart.stop="startDrag('rail', rIndex, 'p2', $event)">
          </div>

          <!-- Delete Button (Center of rail) -->
          <div class="delete-btn"
               :style="{ 
                 left: ((rail.screenP1.x + rail.screenP2.x)/2 * 100) + '%', 
                 top: ((rail.screenP1.y + rail.screenP2.y)/2 * 100) + '%' 
               }"
               @click.stop="removeRail(rIndex)">
            ×
          </div>
        </template>


        
        <!-- Add Zone Controls -->
        <div class="add-controls">
          <button @click="addZone('left')">+ Left Zone</button>
          <button @click="addZone('right')">+ Right Zone</button>
          <button @click="addRail">+ Rail</button>
          <button @click="resetZones" class="reset-btn">Reset Zones</button>
        </div>
      </div>
      
      <div class="video-controls">
        <button @click="$emit('toggle-fullscreen')" class="fullscreen-btn" title="Playfield Full">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"/>
          </svg>
        </button>
        <button class="edit-btn" @click="showZones = !showZones" :class="{ active: showZones }">
          {{ showZones ? 'Hide editor' : 'Edit' }}
        </button>
        <button v-if="hasUnsavedChanges" @click="$emit('save-layout')" class="control-btn save-btn">
          Save Layout
        </button>

        <button @click="$emit('toggle-view')" class="switch-view-btn">
          Switch to 3D
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, computed, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  videoSrc: String,
  isTilted: Boolean,
  stats: Object,
  nudgeEvent: Object,
  physics: Object, // Receive physics config to get zone coords
  socket: Object, // Receive socket instance
  configSocket: Object, // Receive config socket instance
  hasUnsavedChanges: Boolean
})

const emit = defineEmits(['update-zone', 'update-rail', 'update-bumper', 'save-layout', 'reset-zones', 'toggle-view', 'toggle-fullscreen'])

const handleKeydown = (e) => {
  if (['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'PageUp', 'PageDown', 'Home', 'End'].includes(e.code)) {
    e.preventDefault()
    if (props.configSocket) {
        props.configSocket.emit('camera_control', { key: e.code })
    }
  }
}

onMounted(() => {
  window.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown)
})

const videoElement = ref(null)
const containerElement = ref(null)
const lastNudgeTime = ref(props.nudgeEvent?.time || 0)
const showZones = ref(false)
const dragging = ref(null) // { type: 'zone'|'rail', index: int, handle: index|'p1'|'p2'|'body', startPos: {x,y} }

const formatNumber = (num) => {
  if (num === undefined || num === null) return '0'
  return num.toLocaleString()
}

// Watch nudge event and trigger shake
watch(() => props.nudgeEvent, (newVal) => {
  if (newVal && newVal.time > lastNudgeTime.value) {
    lastNudgeTime.value = newVal.time
    const element = videoElement.value
    if (element) {
      element.classList.remove('shake-left', 'shake-right')
      void element.offsetWidth // Trigger reflow

      if (newVal.direction.toLowerCase() === 'left') {
        element.classList.add('shake-left')
      } else {
        element.classList.add('shake-right')
      }

      setTimeout(() => {
        element.classList.remove('shake-left', 'shake-right')
      }, 300)
    }
  }
}, { deep: true })
// Helper to get coordinates from physics prop
// Now projects Table Coords -> Screen Coords
const zones = computed(() => {
  if (!props.physics || !props.physics.zones) return []
  
  return props.physics.zones.map(zone => {
    const points = zone.points.map(p => project3D(p.x, p.y))
    return {
      ...zone,
      screenPoints: points,
      svgPoints: getPolygonPoints(points)
    }
  })
})

const rails = computed(() => {
  if (!props.physics || !props.physics.rails) return []
  
  // Apply Rail Translation Offsets
  // Offsets are already normalized (relative to width/height)
  const normOffsetX = parseFloat(props.physics.rail_x_offset || 0)
  const normOffsetY = parseFloat(props.physics.rail_y_offset || 0)
  const lengthScale = parseFloat(props.physics.guide_length_scale || 1.0)
  
  // console.log(`VideoFeed rails computed. Rails: ${props.physics.rails.length}, Offsets: ${normOffsetX}, ${normOffsetY}`)
  
  return props.physics.rails.map(rail => {
    // Apply offset to base coordinates
    const p1x = rail.p1.x + normOffsetX
    const p1y = rail.p1.y + normOffsetY
    const p2x = rail.p2.x + normOffsetX
    const p2y = rail.p2.y + normOffsetY
    
    // Calculate Length Scaling (P1 relative to P2)
    // Vector pointing from P2 to P1
    const dx = p1x - p2x
    const dy = p1y - p2y
    // In normalized coords, distance acts differently if aspect ratio is not 1.0?
    // Actually physics engine converts to Pixels/World FIRST, then does distance.
    // Here we are in Normalized coords.
    // If Table Ratio is 0.6 / 1.2 (~0.5 aspect?).
    // Distance in normalized space is squashed.
    // To match Physics Engine (World Space) logic:
    // We must de-normalize, scale, then re-normalize.
    
    const wx1 = p1x * TABLE_WIDTH
    const wy1 = p1y * TABLE_HEIGHT
    const wx2 = p2x * TABLE_WIDTH
    const wy2 = p2y * TABLE_HEIGHT
    
    const wdx = wx1 - wx2
    const wdy = wy1 - wy2
    const wLen = Math.sqrt(wdx*wdx + wdy*wdy)
    
    let final_wx1 = wx1
    let final_wy1 = wy1
    
    if (wLen > 0) {
        const ux = wdx / wLen
        const uy = wdy / wLen
        const scaledLen = wLen * lengthScale
        final_wx1 = wx2 + ux * scaledLen
        final_wy1 = wy2 + uy * scaledLen
    }
    
    // Normalize back
    const final_p1x = final_wx1 / TABLE_WIDTH
    const final_p1y = final_wy1 / TABLE_HEIGHT
    
    const p1 = project3D(final_p1x, final_p1y)
    const p2 = project3D(p2x, p2y)
    return {
      ...rail,
      screenP1: p1,
      screenP2: p2
    }
  })
})

const bumpers = computed(() => {
  if (!props.physics || !props.physics.bumpers) return []
  console.log('VideoFeed: Computing bumpers', props.physics.bumpers.length)
  return props.physics.bumpers.map(b => {
    const pos = project3D(b.x, b.y)
    return {
      ...b,
      screenPos: pos
    }
  })
})

const dropTargets = computed(() => {
  if (!props.physics || !props.physics.drop_targets) return []
  return props.physics.drop_targets.map(t => {
      // Calculate projected corners to get bounding box
      const p1 = project3D(t.x - t.width/2, t.y - t.height/2)
      const p2 = project3D(t.x + t.width/2, t.y + t.height/2)
      
      return {
          ...t,
          screenRect: {
              x: Math.min(p1.x, p2.x),
              y: Math.min(p1.y, p2.y),
              width: Math.abs(p2.x - p1.x),
              height: Math.abs(p2.y - p1.y)
          }
      }
  })
})

const zoomStyle = computed(() => {
    // If we assume simulation video covers 0-1 range.
    // camera_x = 0-1 (Target X / Origin X)
    // camera_y = 0-1 (Target Y / Origin Y)
    // zoom = Scalar
    
    // We use default values if props.physics is missing
    const cx = props.physics?.camera_x ?? 0.5
    const cy = props.physics?.camera_y ?? 0.5 
    const zoom = props.physics?.camera_zoom ?? 1.0
    
    let originX = cx * 100
    let originY = cy * 100
    
    // Heuristic: If cy is clearly outside table (e.g. 3D camera position > 1.0), 
    // center vertically for 2D view unless we know better.
    // Standard table Y is 0 (Top) to 1 (Bottom).
    if (cy > 1.2 || cy < -0.2) originY = 50
    
    // Also clamp origin to keep it sane
    originX = Math.max(0, Math.min(100, originX))
    originY = Math.max(0, Math.min(100, originY))

    return {
        transform: `scale(${zoom})`,
        transformOrigin: `${originX}% ${originY}%`,
        transition: 'transform 0.3s ease-out' // Smooth transition for presets
    }
})

// Projection Constants (Must match backend)
const TABLE_WIDTH = 450
const TABLE_HEIGHT = 800
const ASPECT = TABLE_WIDTH / TABLE_HEIGHT

const project3D = (tx, ty) => {
  // tx, ty are normalized table coords (0-1)
  // Simulation video feed uses direct 2D mapping.
  // We bypass perspective projection to align overlay with the flat video feed.
  // This prevents scrambling when 3D camera settings (zoom/pitch) are changed.
  return { x: tx, y: ty }
}

const unproject2D = (sx, sy) => {
  // sx, sy are normalized screen coords (0-1)
  // Inverse of project3D (Identity for simulation)
  return {
    x: sx,
    y: sy
  }
}

const getPolygonPoints = (points) => {
  return points.map(p => `${p.x},${p.y}`).join(' ')
}

const getMousePos = (e) => {
  if (!containerElement.value) return { x: 0, y: 0 }
  const rect = containerElement.value.getBoundingClientRect()
  const clientX = e.touches ? e.touches[0].clientX : e.clientX
  const clientY = e.touches ? e.touches[0].clientY : e.clientY
  return {
    x: (clientX - rect.left) / rect.width,
    y: (clientY - rect.top) / rect.height
  }
}

const startDrag = (type, index, handle, e) => {
  if (e.cancelable) e.preventDefault()
  // Store start pos in Screen Coords
  dragging.value = { type, index, handle, startPos: getMousePos(e) }
  window.addEventListener('mousemove', onDrag)
  window.addEventListener('mouseup', stopDrag)
  window.addEventListener('touchmove', onDrag, { passive: false })
  window.addEventListener('touchend', stopDrag)
}

const stopDrag = () => {
  dragging.value = null
  window.removeEventListener('mousemove', onDrag)
  window.removeEventListener('mouseup', stopDrag)
  window.removeEventListener('touchmove', onDrag)
  window.removeEventListener('touchend', stopDrag)
}

const onDrag = (e) => {
  if (!dragging.value) return
  if (e.cancelable) e.preventDefault()
  
  const pos = getMousePos(e) // Screen Coords
  const { type, index, handle, startPos } = dragging.value
  
  if (type === 'zone') {
    // Clone the entire zones array because we need to emit the full list
    const newZones = JSON.parse(JSON.stringify(props.physics.zones))
    const targetZone = newZones[index]
    
    if (handle === 'body') {
      // Move entire polygon
      const tStart = unproject2D(startPos.x, startPos.y)
      const tCurr = unproject2D(pos.x, pos.y)
      
      const dx = tCurr.x - tStart.x
      const dy = tCurr.y - tStart.y
      
      for (let p of targetZone.points) {
        p.x += dx
        p.y += dy
      }
      dragging.value.startPos = pos // Update start pos
    } else {
      // Move specific point
      const tPos = unproject2D(pos.x, pos.y)
      targetZone.points[handle].x = tPos.x
      targetZone.points[handle].y = tPos.y
    }
    emit('update-zone', newZones)
  } else if (type === 'rail') {
    const newRails = JSON.parse(JSON.stringify(props.physics.rails))
    const targetRail = newRails[index]
    const normOffsetX = parseFloat(props.physics.rail_x_offset || 0)
    const normOffsetY = parseFloat(props.physics.rail_y_offset || 0)
    
    console.log(`Drag Rail: handle=${handle}, startPos=${JSON.stringify(startPos)}, pos=${JSON.stringify(pos)}, offset=${normOffsetX}`)
    
    if (handle === 'body') {
      const tStart = unproject2D(startPos.x, startPos.y)
      const tCurr = unproject2D(pos.x, pos.y)
      const dx = tCurr.x - tStart.x
      const dy = tCurr.y - tStart.y
      
      targetRail.p1.x += dx
      targetRail.p1.y += dy
      targetRail.p2.x += dx
      targetRail.p2.y += dy
      
      dragging.value.startPos = pos
    } else if (handle === 'p1') {
      const tPos = unproject2D(pos.x, pos.y)
      targetRail.p1.x = tPos.x - normOffsetX
      targetRail.p1.y = tPos.y - normOffsetY
    } else if (handle === 'p2') {
      const tPos = unproject2D(pos.x, pos.y)
      targetRail.p2.x = tPos.x - normOffsetX
      targetRail.p2.y = tPos.y - normOffsetY
    }

    emit('update-rail', newRails)
  } else if (type === 'bumper') {
    const newBumpers = JSON.parse(JSON.stringify(props.physics.bumpers))
    const targetBumper = newBumpers[index]
    
    const tPos = unproject2D(pos.x, pos.y)
    targetBumper.x = tPos.x
    targetBumper.y = tPos.y
    
    emit('update-bumper', newBumpers)
  }
}

const addZone = (type) => {
  const newZones = JSON.parse(JSON.stringify(props.physics.zones || []))
  const newZone = {
    id: 'zone_' + Date.now(),
    type: type,
    points: [
      {x: 0.4, y: 0.4},
      {x: 0.6, y: 0.4},
      {x: 0.6, y: 0.6},
      {x: 0.4, y: 0.6}
    ]
  }
  newZones.push(newZone)
  emit('update-zone', newZones)
}

const addRail = () => {
  const newRails = JSON.parse(JSON.stringify(props.physics.rails || []))
  newRails.push({
    p1: {x: 0.4, y: 0.4},
    p2: {x: 0.6, y: 0.6}
  })
  emit('update-rail', newRails)
}

const removeZone = (index) => {
  const newZones = JSON.parse(JSON.stringify(props.physics.zones))
  newZones.splice(index, 1)
  emit('update-zone', newZones)
}

const removeRail = (index) => {
  const newRails = JSON.parse(JSON.stringify(props.physics.rails))
  newRails.splice(index, 1)
  emit('update-rail', newRails)
}

const resetZones = () => {
  emit('reset-zones')
}
</script>

<style scoped>
#video-container {
  margin-bottom: 20px;
  display: inline-block;
  max-width: 100%;
  background: #000;
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.3);
  position: relative;
}

img {
  max-width: 100%;
  height: auto;
  display: block;
}

/* Tilted Overlay */
#tilted-overlay {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%) rotate(-15deg);
  font-size: 120px;
  font-weight: bold;
  color: rgba(255, 0, 0, 0.8);
  text-shadow: 4px 4px 8px rgba(0, 0, 0, 0.9);
  pointer-events: none;
  z-index: 1000;
  animation: pulse 0.5s ease-in-out infinite alternate;
}

@keyframes pulse {
  from {
    transform: translate(-50%, -50%) rotate(-15deg) scale(1);
  }

  to {
    transform: translate(-50%, -50%) rotate(-15deg) scale(1.1);
  }
}

/* Shake Animation */
@keyframes shake-left {

  0%,
  100% {
    transform: translateX(0);
  }

  25% {
    transform: translateX(-8px);
  }

  75% {
    transform: translateX(4px);
  }
}

@keyframes shake-right {

  0%,
  100% {
    transform: translateX(0);
  }

  25% {
    transform: translateX(8px);
  }

  75% {
    transform: translateX(-4px);
  }
}

.shake-left {
  animation: shake-left 0.3s ease-in-out;
}

.shake-right {
  animation: shake-right 0.3s ease-in-out;
}

.shake-right {
  animation: shake-right 0.3s ease-in-out;
}

#video-container {
  user-select: none;
  -webkit-user-select: none;
}

#video-wrapper {
  position: relative;
  display: inline-block;
  /* width: 100%; Removed to let it shrink to image size */
  line-height: 0; /* Remove vertical gap for inline-block */
}

.zone-overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
  z-index: 20;
}

.zone-poly {
  fill: rgba(76, 175, 80, 0.2);
  stroke: #4caf50;
  stroke-width: 2;
  vector-effect: non-scaling-stroke;
  pointer-events: all;
  cursor: move;
  transition: fill 0.2s;
}

.zone-poly:hover {
  fill: rgba(76, 175, 80, 0.4);
}

.rail-line {
  stroke: #2196F3;
  stroke-width: 4;
  vector-effect: non-scaling-stroke;
  pointer-events: all;
  cursor: move;
}

.rail-line:hover {
  stroke: #64B5F6;
}

.bumper-circle {
  fill: rgba(255, 170, 0, 0.4);
  stroke: #ffaa00;
  stroke-width: 2;
  vector-effect: non-scaling-stroke;
  pointer-events: all;
  cursor: move;
}

.bumper-circle:hover {
  fill: rgba(255, 170, 0, 0.6);
  stroke: #ffcc00;
}

.target-rect {
  fill: rgba(0, 255, 255, 0.4);
  stroke: #00ffff;
  stroke-width: 2;
  vector-effect: non-scaling-stroke;
  pointer-events: all;
  cursor: move;
}

.target-rect:hover {
  fill: rgba(0, 255, 255, 0.6);
}



.rail-handle:hover {
  background: #2196F3;
}

.bumper-handle {
  border-color: #ffaa00;
}

.bumper-handle:hover {
  background: #ffaa00;
}

.control-btn {
  background: #4caf50;
  color: white;
  border: none;
  padding: 5px 10px;
  border-radius: 4px;
  cursor: pointer;
  margin-right: 5px;
}

.control-btn.active {
  background: #2196F3;
}

.control-btn.save-btn {
  background: #ff9800;
  animation: pulse-save 2s infinite;
}

@keyframes pulse-save {
  0% { box-shadow: 0 0 0 0 rgba(255, 152, 0, 0.7); }
  70% { box-shadow: 0 0 0 10px rgba(255, 152, 0, 0); }
  100% { box-shadow: 0 0 0 0 rgba(255, 152, 0, 0); }
}

.handle {
  position: absolute;
  width: 10px;
  height: 10px;
  background: #fff;
  border: 1px solid #4caf50;
  border-radius: 50%;
  pointer-events: all;
  z-index: 2;
  cursor: pointer;
  transform: translate(-50%, -50%); /* Center on point */
}

.handle:hover {
  background: #4caf50;
  transform: translate(-50%, -50%) scale(1.2);
}

.rail-handle {
  border-color: #2196F3;
}

.rail-handle:hover {
  background: #2196F3;
}

.zone-poly.left-zone { stroke: #4caf50; fill: rgba(76, 175, 80, 0.2); }
.zone-poly.right-zone { stroke: #ff9800; fill: rgba(255, 152, 0, 0.2); }

.delete-btn {
  position: absolute;
  width: 20px;
  height: 20px;
  background: red;
  color: white;
  border-radius: 50%;
  text-align: center;
  line-height: 20px;
  font-size: 14px;
  cursor: pointer;
  transform: translate(-50%, -50%);
  pointer-events: auto;
  opacity: 0;
  transition: opacity 0.2s;
}

.zone-overlay:hover .delete-btn {
  opacity: 1;
}

.add-controls {
  position: absolute;
  bottom: 60px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  gap: 10px;
  pointer-events: auto;
}

.add-controls button {
  background: rgba(0, 0, 0, 0.7);
  color: white;
  border: 1px solid #666;
  padding: 5px 10px;
  border-radius: 4px;
  cursor: pointer;
}

.add-controls button:hover {
  background: rgba(0, 0, 0, 0.9);
}

.video-controls {
  position: absolute;
  bottom: 20px;
  right: 20px;
  display: flex;
  gap: 10px;
  z-index: 30;
  width: 90%;
  justify-content: space-between; /* Space between fullscreen (left) and other buttons (right) */
  align-items: center;
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
  font-size: 12px;
}

.fullscreen-btn:hover {
  background: rgba(0, 120, 215, 0.8);
  border-color: #0078d7;
}

.fullscreen-btn svg {
  display: block;
}

.edit-btn {
  background: rgba(0, 0, 0, 0.6);
  color: #fff;
  border: 1px solid #555;
  padding: 5px 10px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
  /* Removed absolute positioning */
}

.edit-btn:hover {
  background: rgba(0, 0, 0, 0.8);
}

.edit-btn.active {
  background: #4caf50;
  border-color: #4caf50;
}

/* Ensure switch-view-btn inside controls is static */
.video-controls .switch-view-btn {
  position: static;
}

.loading-placeholder {
  width: 450px;
  height: 800px;
  background: #111;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #888;
  font-family: 'Segoe UI', sans-serif;
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
</style>
