import { createApp, h } from 'vue'
import PrimeVue from 'primevue/config'
import Aura from '@primeuix/themes/aura'
import './style.css'
import {RouterView} from 'vue-router'
import {router} from './router.js'

const app=createApp({render:()=>h(RouterView)}).use(router).use(PrimeVue, { theme: { preset: Aura, options: { darkModeSelector: false } } })
router.isReady().then(()=>app.mount('#app'))
