import { defineConfig } from 'astro/config';
const site = process.env.SITE_URL || 'https://www.mnppsaturn.ru';
const base = process.env.BASE_PATH || '/';
export default defineConfig({ site, base, trailingSlash: 'ignore' });
