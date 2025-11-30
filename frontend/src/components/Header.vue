<template>
  <div class="app-header">
    <div class="header-text">
      <h1>Pinball Wizard 🧙‍♂️</h1>
    </div>

    <div class="connection-status" style="font-size: 0.8em; color: #888;">
      <span class="status-dot" :class="connected ? 'status-connected' : 'status-disconnected'"></span>
      {{ connected ? 'Connected' : 'Disconnected' }}
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
  display: flex;
  align-items: center;
  gap: 5px;
  order: 1;
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

@media (max-width: 690px) {
  .app-header {
    flex-direction: row;
    gap: 10px;
  }

  .app-header h1 {
    margin: 5px 0;
    font-size: 1.5em;
  }

  .connection-status {
    font-size: 0.7em;
    margin-top: 5px;
    order: 0;
  }

  #stats-container {
    flex-direction: row;
    flex-wrap: nowrap;
    justify-content: space-between;
    align-items: flex-start;
    gap: 2px;
    width: 100%;
    padding: 0 2px;
    box-sizing: border-box;
  }
}
</style>
