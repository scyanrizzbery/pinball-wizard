import { createApp } from 'vue'
import Highcharts from 'highcharts'
import HighchartsVue from 'highcharts-vue'
import HighchartsStock from 'highcharts/modules/stock'
import App from './App.vue'
import sockets from './services/socket'
import './style.css'

// Initialize Highcharts Stock module (handle potential ES/CJS interop issues)
// Initialize Highcharts Stock module
const initStock = (HighchartsStock as any).default || HighchartsStock;

// Check if stockChart is already available (auto-registered or side-effect)
if (typeof (Highcharts as any).stockChart !== 'function') {
    if (typeof initStock === 'function') {
        initStock(Highcharts);
    } else {
        console.warn('Highcharts Stock module is not a function and stockChart is missing.', initStock);
    }
}

const app = createApp(App)
app.use(HighchartsVue);

// Expose for E2E testing
(window as any).__app__ = app;
(window as any).sockets = sockets;

app.mount('#app')
