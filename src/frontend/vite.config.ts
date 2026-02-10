import { defineConfig } from 'vite';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));

export default defineConfig({
    root: '.',
    build: {
        outDir: 'dist',
        emptyOutDir: true,
        rollupOptions: {
            input: {
                main: resolve(__dirname, 'index.html'),
                savings: resolve(__dirname, 'savings.html'),
            },
        },
    },
    server: {
        proxy: {
            '/api': {
                target: 'http://localhost:7071',
                changeOrigin: true,
            },
            '/.auth': {
                target: 'http://localhost:7071',
                changeOrigin: true,
            },
        },
    },
});
