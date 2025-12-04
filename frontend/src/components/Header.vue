<template>
  <div class="app-header">
    <div class="header-text">
      <h1>Pinball Wizard 🧙‍♂️</h1>
    </div>

    <div class="connection-status" style="font-size: 0.8em; color: #888;">
      <span class="status-dot" :class="connected ? 'status-connected' : 'status-disconnected'"></span>
      <span class="status-text">{{ connected ? 'Connected' : 'Disconnected' }}</span>
    </div>

    <div id="stats-container">
      <slot name="stats"></slot>
    </div>
  </div>
</template>

<script setup>
defineProps({
  connected: {
    type: Boolean,
    required: true
  }
})
</script>

<style scoped>
.app-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
  flex-wrap: wrap;
}

.connection-status {
  position: fixed;
  top: 7px;
  right: 7px;
}

.status-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  display: inline-block;
}

.status-connected {
  background-color: #4caf50;
}

.status-disconnected {
  background-color: #f44336;
  box-shadow: 0 0 8px rgba(244, 67, 54, 0.6);
}

#stats-container {
  margin-top: 10px;
  display: flex;
  justify-content: center;
  flex-wrap: wrap;
  gap: 10px;
  font-size: 1em;
}

@media (max-width: 1200px) {
  .header-text {
    display: none;
  }
}

@media (max-width: 690px) {
  #stats-container {
    display: none;
  }

  .status-text {
    display: none;
  }

  .app-header {
    position: absolute;
    top: 7px;
    right: 7px;
    margin: 0;
    z-index: 1000;
    width: auto;
    padding: 0;
  }
}
</style>
