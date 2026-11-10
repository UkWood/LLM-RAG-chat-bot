import { defineCollection, reference } from 'astro:content';
import { glob } from 'astro/loaders';
import { z } from 'astro/zod';

// Общие поля. oldUrl и legacyId — след старого сайта (для редиректов и сверки), на страницах не показываются.
const base = {
  title: z.string(),
  subtitle: z.string().optional(),
  oldUrl: z.string().optional(),
  legacyId: z.coerce.number().optional(),
  draft: z.boolean().default(false),
};

// Документы и файлы: сами файлы лежат на хостинге (/ftp, /update …), в карточке только ссылка.
export const DOC_KINDS = ['manual', 'software', 'presentation', 'certificate', 'declaration', 'registry', 'datasheet', 'other'] as const;
const doc = z.object({
  title: z.string(),
  kind: z.enum(DOC_KINDS),
  url: z.string(),
  version: z.string().optional(),
  date: z.coerce.date().optional(),
});
const certificate = z.union([doc, z.object({ kind: z.literal('scan'), image: z.string(), title: z.string().optional() })]);

// Вход или выход: вид (ключ из src/data/io-kinds.yaml), число и пояснение («не более», «из них 2 с релейным выходом»)
const io = z.object({ kind: z.string(), count: z.number().int().nonnegative(), note: z.string().optional() });

const loader = (dir: string) => glob({ pattern: '**/*.md', base: `./src/content/${dir}` });

export const collections = {
  // Страница. Для главной (home) дополнительно: heading — заголовок первого экрана, lead — вступление под ним, directions — основные направления деятельности.
  pages: defineCollection({
    loader: loader('pages'),
    schema: z.object({
      ...base,
      kind: z.enum(['section', 'solution']).optional(), // solution — страница типового решения
      images: z.array(z.string()).default([]), // для решений: главная иллюстрация
      systems: z.array(reference('systems')).default([]), // для решений: системы
      products: z.array(reference('products')).default([]), // для решений: оборудование
      groups: z.array(z.object({ title: z.string(), icon: z.string().default('layers'), items: z.array(reference('pages')).default([]) })).default([]), // для «Типовых решений»: разделы со страницами решений
      heading: z.string().optional(),
      lead: z.string().optional(),
      directions: z.array(z.object({ title: z.string(), href: z.string() })).default([]),
    }),
  }),
  // Новость: products — изделия, о которых новость (найдены по упоминанию обозначения в тексте).
  news: defineCollection({ loader: loader('news'), schema: z.object({ ...base, date: z.coerce.date(), products: z.array(reference('products')).default([]) }) }),
  // Система или раздел оборудования (kind: category — перечень изделий, а не система). Состав строится из изделий (products.systems).
  systems: defineCollection({
    loader: loader('systems'),
    schema: z.object({
      ...base,
      kind: z.enum(['system', 'category']).default('system'),
      summary: z.string().optional(), // краткое описание для списков, поиска и description страницы
      applications: z.array(z.string()).default([]), // области применения из src/data/applications.yaml
      documents: z.array(doc).default([]),
      videos: z.array(z.object({ title: z.string(), url: z.string(), group: z.string().optional() })).default([]), // ссылки на видео (Rutube) в конце описания; group — подзаголовок серии
      images: z.array(z.string()).default([]), // главная иллюстрация или фото системы
      imageDark: z.string().optional(), // вариант главной иллюстрации для тёмной схемы (images[0] — для светлой)
      articles: z.array(reference('articles')).default([]), // примеры применения: статьи
      solutions: z.array(reference('pages')).default([]), // примеры применения: страницы решений
    }),
  }),
  // Материал: section — страница-раздел (pages), products и systems — оборудование и системы, о которых материал.
  articles: defineCollection({ loader: loader('articles'), schema: z.object({ ...base, section: z.string().optional(), products: z.array(reference('products')).default([]), systems: z.array(reference('systems')).default([]) }) }),
  // Группа каталога: список изделий строится автоматически. system — система с тем же содержанием (если есть); icon — значок Lucide для карточек изделий без фото.
  groups: defineCollection({
    loader: loader('groups'),
    schema: z.object({ ...base, group: z.string().optional(), summary: z.string().optional(), icon: z.string().optional(), system: reference('systems').optional() }),
  }),
  // Изделие: поля вместо вёрстки (см. docs/content-model.md). Значения interfaces/protocols — из словарей src/data/.
  products: defineCollection({
    loader: loader('products'),
    schema: z.object({
      ...base,
      name: z.string().optional(), // полное наименование; title — обозначение («БКД-UPS»)
      article: z.string().optional(),
      group: reference('groups').optional(),
      systems: z.array(reference('systems')).default([]),
      status: z.enum(['active', 'obsolete', 'discontinued']).default('active'),
      notice: z.string().optional(),
      images: z.array(z.string()).default([]),
      interfaces: z.array(z.string()).default([]),
      protocols: z.array(z.string()).default([]),
      ip: z.string().optional(),
      temperature_c: z.object({ min: z.number(), max: z.number() }).optional(),
      mass_kg: z.number().optional(),
      dimensions_mm: z.tuple([z.number(), z.number(), z.number()]).optional(),
      lifetime_years: z.number().optional(),
      power: z.string().optional(),
      specs: z.array(z.object({ group: z.string().optional(), name: z.string(), value: z.string() })).default([]),
      inputs: z.array(io).default([]),
      outputs: z.array(io).default([]),
      features: z.array(z.string()).default([]),
      connectors: z.array(z.object({ id: z.string(), description: z.string(), label: z.string().default('') })).default([]),
      documents: z.array(doc).default([]),
      videos: z.array(z.object({ title: z.string(), url: z.string(), group: z.string().optional() })).default([]), // ссылки на видео (Rutube) в конце описания; group — подзаголовок серии
      certificates: z.array(certificate).default([]),
      related: z.array(reference('products')).default([]),
      variant_of: reference('products').optional(),
      // связи страницы устройства: совместимое ПО (изделия группы «Программное обеспечение») и примеры применения (статьи и страницы решений)
      software: z.array(reference('products')).default([]),
      articles: z.array(reference('articles')).default([]),
      solutions: z.array(reference('pages')).default([]),
    }),
  }),
};
