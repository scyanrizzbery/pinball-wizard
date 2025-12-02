<template>
  <div class="scoreboard-container">
    <!-- Main Score -->
    <div class="stat-box main-score">
      <span class="label">SCORE</span>
      <div class="score-board">
        <template v-for="(item, index) in scoreReels" :key="index">
          <div class="score-reel" v-if="item.type === 'digit'">
            <div class="score-strip" :style="{ transform: `translateY(-${item.value * 26}px)` }">
              <div class="reel-number" v-for="n in 10" :key="n">{{ n - 1 }}</div>
            </div>
          </div>
          <div class="score-comma" v-else>,</div>
        </template>
      </div>
    </div>
    
    <!-- High Score -->
    <div class="stat-box high-score-box">
      <span class="label">HIGH SCORE</span>
      <div class="score-board">
        <template v-for="(item, index) in highScoreReels" :key="index">
          <div class="score-reel" v-if="item.type === 'digit'">
            <div class="score-strip" :style="{ transform: `translateY(-${item.value * 26}px)` }">
              <div class="reel-number" v-for="n in 10" :key="n">{{ n - 1 }}</div>
            </div>
          </div>
          <div class="score-comma" v-else>,</div>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  score: { type: Number, default: 0 },
  highScore: { type: Number, default: 0 }
})

const getReelItems = (num, minDigits) => {
  let s = num.toString();
  if (s.length < minDigits) {
    s = s.padStart(minDigits, '0');
  }
  
  let result = '';
  let count = 0;
  for (let i = s.length - 1; i >= 0; i--) {
    result = s[i] + result;
    count++;
    if (count % 3 === 0 && i > 0) {
      result = ',' + result;
    }
  }
  
  return result.split('').map(char => {
    if (char === ',') return { type: 'comma' };
    return { type: 'digit', value: parseInt(char) };
  });
}

const scoreReels = computed(() => getReelItems(props.score, 7))
const highScoreReels = computed(() => getReelItems(props.highScore, 7))
</script>

<style scoped>
.scoreboard-container {
  display: flex;
  flex-direction: row; /* Horizontal layout */
  justify-content: center;
  align-items: flex-start; /* Align top */
  gap: 20px;
  width: auto;
  pointer-events: none;
  background: rgba(0, 0, 0, 0.5); /* Semi-transparent background for legibility */
  padding: 10px 20px;
  border-radius: 12px;
  backdrop-filter: blur(4px);
}

.stat-box {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.main-score {
  /* Main score stays prominent */
}

.high-score-box {
  transform: scale(0.75); /* Make high score smaller */
  transform-origin: top center;
  opacity: 0.8; /* Slightly less opaque */
  margin-top: 5px; /* Adjust alignment */
}

.label {
  font-family: 'Segoe UI', sans-serif;
  font-size: 0.6em;
  color: #ccc;
  letter-spacing: 1px;
  font-weight: 800;
  text-transform: uppercase;
  text-shadow: 0 1px 2px rgba(0,0,0,1);
  margin-bottom: 2px;
}

/* Score Board */
.score-board {
    background: #000;
    border: 2px solid #333;
    border-radius: 6px;
    padding: 4px 8px;
    display: inline-flex;
    gap: 2px;
    align-items: center;
    box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.5);
}

.score-reel {
    width: 16px; /* Slightly smaller reels */
    height: 22px;
    overflow: hidden;
    background: linear-gradient(180deg, #1a1a1a 0%, #0d0d0d 100%);
    border: 1px solid #444;
    border-radius: 3px;
    position: relative;
    box-shadow: inset 0 1px 3px rgba(0, 0, 0, 0.6);
}

.score-strip {
    transition: transform 0.3s cubic-bezier(0.4, 0.0, 0.2, 1);
    will-change: transform;
}

.reel-number {
    height: 22px; /* Match reel height */
    display: flex;
    align-items: center;
    justify-content: center;
    font-family: 'Courier New', monospace;
    font-size: 15px; /* Smaller font */
    font-weight: bold;
    color: #ff6b35;
    text-shadow: 0 0 8px rgba(255, 107, 53, 0.6);
}

.score-comma {
    font-size: 15px;
    font-weight: bold;
    color: #666;
    margin: 0 1px;
}

@media (max-width: 690px) {
  .scoreboard-container {
    gap: 10px;
    padding: 5px 10px;
    transform: scale(0.9); /* Slight overall scale down on mobile */
  }
}
</style>
