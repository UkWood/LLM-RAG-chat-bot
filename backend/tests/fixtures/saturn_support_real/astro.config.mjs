import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';
import { rehypeSiteLinks } from './scripts/rehype-site-links.mjs';
import { rehypeHeadingLevels } from './scripts/rehype-heading-levels.mjs';

// Боевой сайт: значения по умолчанию. Предпросмотр на GitHub Pages задаётся переменными окружения (см. .github/workflows/deploy.yml).
const site = process.env.SITE_URL || 'https://www.mnppsaturn.ru';
const base = process.env.BASE_PATH || '/';
const assetOrigin = process.env.ASSET_ORIGIN || ''; // для предпросмотра: https://www.mnppsaturn.ru

// Поддерживаемые браузеры (ADR 0006): Chrome и Edge 90+, Firefox 91+, Safari 14+ (Яндекс Браузер следует за Chromium).
// Lightning CSS понижает новый синтаксис стилей до этих версий; для скриптов задан тот же порог.
const v = (major, minor = 0) => (major << 16) | (minor << 8);
const targets = { chrome: v(90), edge: v(90), firefox: v(91), safari: v(14) };

// https://astro.build/config
export default defineConfig({
  site,
  base,
  trailingSlash: 'ignore',
  integrations: [sitemap()],
  vite: {
    css: { transformer: 'lightningcss', lightningcss: { targets } },
    build: { cssMinify: 'lightningcss', target: ['chrome90', 'edge90', 'firefox91', 'safari14'] },
  },
  markdown: { rehypePlugins: [[rehypeSiteLinks, { base, assetOrigin }], rehypeHeadingLevels] },
});
