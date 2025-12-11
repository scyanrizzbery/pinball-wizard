import { createApp } from 'vue'
import Highcharts from 'highcharts'
import HighchartsVue from 'highcharts-vue'
import App from './App.vue'

import sockets from './services/socket'

const app = createApp(App)
app.use(HighchartsVue)
window.__app__ = app // Expose for E2E testing
window.sockets = sockets // Expose for E2E testing
app.mount('#app')
