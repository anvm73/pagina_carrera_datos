import { defineConfig } from 'astro/config';
import tailwind from '@astrojs/tailwind';

// Astro config with Tailwind integration
export default defineConfig({
  srcDir: 'src',
  integrations: [tailwind({ config: './tailwind.config.cjs' })],
});
