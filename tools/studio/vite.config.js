import { svelte } from '@sveltejs/vite-plugin-svelte';
import fs from 'node:fs';
import path from 'node:path';
import { defineConfig } from 'vite';
import { createApi } from './server/api.js';

// Папка ассетов: SourceArt в корне репозитория. Другая — через STUDIO_ROOT.
const root = path.resolve(process.env.STUDIO_ROOT ?? '../../SourceArt');
fs.mkdirSync(root, { recursive: true });

export default defineConfig({
  plugins: [
    svelte(),
    {
      name: 'studio-api',
      configureServer(server) {
        server.middlewares.use('/api', createApi({ root }));
      },
    },
  ],
  clearScreen: false,
});
