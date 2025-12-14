<template>
  <Teleport to="body">
    <div v-if="show" class="modal-overlay" @click.self="handleBackdropClick" @keydown.esc="cancel">
      <div class="modal-content" role="dialog" aria-modal="true">
        <h3 v-if="title">{{ title }}</h3>
        <p v-if="message" class="modal-message">{{ message }}</p>
        
        <div v-if="type === 'prompt'" class="modal-input-container">
          <input 
            ref="inputRef"
            v-model="inputValue" 
            @keyup.enter="confirm"
            class="modal-input"
            type="text"
            :placeholder="placeholder"
          >
        </div>

        <div class="modal-actions">
          <button class="btn-cancel" @click="cancel" v-if="type !== 'alert'">Cancel</button>
          <button class="btn-confirm" @click="confirm">
             {{ confirmText || 'OK' }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, watch, nextTick, onMounted, onUnmounted } from 'vue'

const props = defineProps<{
  show: boolean
  title?: string
  message?: string
  type: 'alert' | 'confirm' | 'prompt'
  confirmText?: string
  placeholder?: string
  initialValue?: string
}>()

const emit = defineEmits<{
  (e: 'update:show', value: boolean): void
  (e: 'confirm', value?: string): void
  (e: 'cancel'): void
}>()

const inputValue = ref('')
const inputRef = ref<HTMLInputElement | null>(null)

watch(() => props.show, async (newVal) => {
  if (newVal) {
    inputValue.value = props.initialValue || ''
    if (props.type === 'prompt') {
      await nextTick()
      inputRef.value?.focus()
    }
  }
})

const confirm = () => {
  emit('confirm', props.type === 'prompt' ? inputValue.value : undefined)
}

const cancel = () => {
  emit('cancel')
}

const handleBackdropClick = () => {
  if (props.type !== 'alert') {
    cancel()
  }
}
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  background: rgba(0, 0, 0, 0.75);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 9999;
  backdrop-filter: blur(4px);
  animation: fadeIn 0.2s ease-out;
}

.modal-content {
  background: #1e1e1e;
  border: 1px solid #444;
  border-radius: 8px;
  padding: 24px;
  min-width: 320px;
  max-width: 500px;
  box-shadow: 0 20px 50px rgba(0,0,0,0.6);
  color: white;
  animation: slideUp 0.2s ease-out;
}

h3 {
  margin-top: 0;
  margin-bottom: 12px;
  color: #4caf50;
  font-size: 1.2rem;
}

.modal-message {
  color: #ddd;
  margin-bottom: 24px;
  line-height: 1.5;
}

.modal-input {
  width: 100%;
  padding: 12px;
  background: #333;
  border: 1px solid #555;
  color: white;
  border-radius: 4px;
  margin-bottom: 24px;
  box-sizing: border-box;
  font-size: 1rem;
}

.modal-input:focus {
  outline: none;
  border-color: #4caf50;
  background: #3a3a3a;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

button {
  padding: 10px 20px;
  border-radius: 4px;
  border: none;
  cursor: pointer;
  font-weight: 600;
  font-size: 0.95rem;
  transition: background-color 0.2s;
}

.btn-cancel {
  background: #333;
  color: #ccc;
  border: 1px solid #444;
}
.btn-cancel:hover {
  background: #444;
  color: white;
}

.btn-confirm {
  background: #4caf50;
  color: #111;
}
.btn-confirm:hover {
  background: #45a049;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes slideUp {
  from { transform: translateY(20px); opacity: 0; }
  to { transform: translateY(0); opacity: 1; }
}
</style>
