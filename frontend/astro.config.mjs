// @ts-check
import { defineConfig } from 'astro/config';
import react from '@astrojs/react';
import tailwind from '@astrojs/tailwind';

// https://astro.build/config
// Deployment target is environment-driven so the same source tree can build for production
// and for the staging mirror, which live at different GitHub Pages paths. Both fall back to
// the production values, so an unset environment always builds production correctly.
export default defineConfig({
  integrations: [react(), tailwind()],
  site: process.env.PUBLIC_SITE_URL || 'https://bd4l.github.io',
  base: process.env.PUBLIC_BASE_PATH || '/Breaches',
  output: 'static'
});
