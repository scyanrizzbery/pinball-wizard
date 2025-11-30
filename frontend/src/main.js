import { createApp } from 'vue'
import Highcharts from 'highcharts'
import HighchartsVue from 'highcharts-vue'
import App from './App.vue'

const app = createApp(App)
app.use(HighchartsVue)
app.mount('#app')
