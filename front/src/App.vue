<template>
  <div id="app">
    <AppNav />
    <RouterView />
    <AppFooter />
  </div>
</template>

<script setup>
import AppNav from './components/AppNav.vue'
import AppFooter from './components/AppFooter.vue'
import { RouterView } from 'vue-router'
</script>

<style>
#app {
  min-height: 100vh;
  font-family: var(--font-body);
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  background: var(--bg-primary);
  color: var(--text-primary);
}
</style>