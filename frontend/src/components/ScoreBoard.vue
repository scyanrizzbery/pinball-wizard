<template>
  <div class="scoreboard-container">
    <!-- Main Score -->
    <div class="stat-box main-score" style="background: transparent; border: none; box-shadow: none; padding: 0;">
      <span class="label" style="margin-bottom: 5px;">SCORE</span>
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
    
    <div class="sub-stats">
      <!-- High Score -->
      <div class="stat-box" style="background: transparent; border: none; box-shadow: none; padding: 0;">
        <span class="label" style="margin-bottom: 5px;">HIGH SCORE</span>
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
  flex-direction: column;
  gap: 10px;
  width: 100%;
}

.sub-stats {
  display: flex;
  justify-content: center;
  gap: 20px;
  flex-wrap: wrap;
}

.sub-stats .stat-box {
  flex: 0 1 auto;
  display: flex;
  flex-direction: column;
  align-items: center;
  min-width: 120px;
}

.main-score {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.label {
  font-family: 'Segoe UI', sans-serif;
  font-size: 0.7em;
  color: #888;
  letter-spacing: 2px;
  font-weight: 800;
  text-transform: uppercase;
  text-shadow: 0 1px 2px rgba(0,0,0,1);
}

/* Score Board */
.score-board {
    background: #000;
    border: 4px solid #333;
    border-radius: 8px;
    padding: 8px 12px;
    display: inline-flex;
    gap: 4px;
    align-items: center;
    box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.5);
}

.score-reel {
    width: 20px;
    height: 26px;
    overflow: hidden;
    background: linear-gradient(180deg, #1a1a1a 0%, #0d0d0d 100%);
    border: 1px solid #444;
    border-radius: 4px;
    position: relative;
    box-shadow: inset 0 1px 3px rgba(0, 0, 0, 0.6);
}

.score-strip {
    transition: transform 0.3s cubic-bezier(0.4, 0.0, 0.2, 1);
    will-change: transform;
}

.reel-number {
    height: 26px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-family: 'Courier New', monospace;
    font-size: 17px;
    font-weight: bold;
    color: #ff6b35;
    text-shadow: 0 0 8px rgba(255, 107, 53, 0.6);
}

.score-comma {
    font-size: 17px;
    font-weight: bold;
    color: #666;
    margin: 0 2px;
}
</style>
