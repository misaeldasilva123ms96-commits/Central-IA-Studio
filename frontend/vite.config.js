import {defineConfig} from 'vite';
export default defineConfig({
 build:{rollupOptions:{output:{manualChunks(id){
  if(id.includes('/node_modules/highlight.js/'))return 'syntax';
  if(id.includes('/node_modules/'))return 'vendor';
 }}}}
});
