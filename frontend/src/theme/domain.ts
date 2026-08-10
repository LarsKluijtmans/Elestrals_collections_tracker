/**
 * Domain tokens — the layer branding must never reach.
 *
 * Element hues and rarity treatments are a **data encoding**, not decoration. They have to
 * mean the same thing in every deployment, for every tenant, forever. If a company could
 * rebrand them, the same hue would mean Fire in one install and Water in another.
 *
 * Chrome tokens (primary, surfaces, focus ring) come from branding-api and live in
 * `tokens.ts`. Mixing the two layers is a review failure.
 *
 * See memory-bank/standards/ux-guide.md §2 and §4.
 */

export const ELEMENTS = [
  'fire', 'solar', 'thunder', 'wind', 'frost', 'water', 'lunar', 'earth',
] as const;
export type ElementKey = (typeof ELEMENTS)[number];

/** Dark values first — the product is dark-first. Light values are darkened for AA on white. */
export const ELEMENT_HUES: Record<ElementKey, { dark: string; light: string; label: string }> = {
  fire:    { dark: '#FF6A5A', light: '#C7392B', label: 'Fire' },
  solar:   { dark: '#FFA033', light: '#B36405', label: 'Solar' },
  thunder: { dark: '#FFD84D', light: '#8A6B00', label: 'Thunder' },
  wind:    { dark: '#4FDD9B', light: '#0E7A50', label: 'Wind' },
  frost:   { dark: '#5FDDEC', light: '#0A7286', label: 'Frost' },
  water:   { dark: '#5AA0FF', light: '#1257C4', label: 'Water' },
  lunar:   { dark: '#B69BFF', light: '#6A46CF', label: 'Lunar' },
  earth:   { dark: '#D2A06B', light: '#8A5A22', label: 'Earth' },
};

/**
 * The chip rule: an element colour is NEVER a solid fill. 14% alpha background, full-strength
 * text and border. Solid saturation belongs to the brand accent alone — which is also what
 * keeps Lunar from competing with a violet brand primary.
 *
 * Chips always render the element name too. Colour is redundant encoding, never the only one.
 */
export const ELEMENT_CHIP_ALPHA = 0.14;
export const ELEMENT_BORDER_ALPHA = 0.45;

export const RARITIES = [
  'common', 'uncommon', 'rare', 'holo_rare', 'full_art', 'alt_art',
  'prismatic', 'secret', 'promo',
] as const;
export type RarityKey = (typeof RARITIES)[number];

/**
 * Rarity is encoded as *material*, never hue — element already owns hue, and two hue
 * encodings in one dense row is unreadable.
 */
export type RarityMaterial =
  | { kind: 'flat'; tone: 'muted' | 'secondary' }
  | { kind: 'ring' }
  | { kind: 'silver'; sheen: boolean }
  | { kind: 'element-gradient' }
  | { kind: 'iridescent' }
  | { kind: 'dashed' };

export const RARITY_MATERIALS: Record<RarityKey, { material: RarityMaterial; label: string }> = {
  common:     { material: { kind: 'flat', tone: 'muted' },      label: 'Common' },
  uncommon:   { material: { kind: 'ring' },                     label: 'Uncommon' },
  rare:       { material: { kind: 'silver', sheen: false },     label: 'Rare' },
  holo_rare:  { material: { kind: 'silver', sheen: true },      label: 'Holo Rare' },
  full_art:   { material: { kind: 'element-gradient' },         label: 'Full Art' },
  alt_art:    { material: { kind: 'element-gradient' },         label: 'Alt Art' },
  prismatic:  { material: { kind: 'iridescent' },               label: 'Prismatic' },
  secret:     { material: { kind: 'iridescent' },               label: 'Secret' },
  promo:      { material: { kind: 'dashed' },                   label: 'Promo' },
};

/** Condition: a neutral badge with a letter grade. No colour at all. */
export const CONDITIONS = [
  'mint', 'near_mint', 'lightly_played', 'moderately_played', 'heavily_played', 'damaged',
] as const;
export type ConditionKey = (typeof CONDITIONS)[number];

export const CONDITION_LABELS: Record<ConditionKey, { short: string; long: string }> = {
  mint:              { short: 'M',   long: 'Mint' },
  near_mint:         { short: 'NM',  long: 'Near Mint' },
  lightly_played:    { short: 'LP',  long: 'Lightly Played' },
  moderately_played: { short: 'MP',  long: 'Moderately Played' },
  heavily_played:    { short: 'HP',  long: 'Heavily Played' },
  damaged:           { short: 'DMG', long: 'Damaged' },
};

/**
 * Price movement. Colour is ALWAYS paired with a glyph — this product is fundamentally red
 * and green numbers, and roughly 1 in 12 men has a red-green deficiency.
 */
export const PRICE_MOVEMENT = {
  up:   { dark: '#35C77F', light: '#0E7A50', glyph: '▲' },
  down: { dark: '#F0524B', light: '#C0342E', glyph: '▼' },
  flat: { dark: '#6C7896', light: '#737E99', glyph: '–' },
} as const;

export function hexToRgba(hex: string, alpha: number): string {
  const h = hex.replace('#', '');
  const n = parseInt(h.length === 3 ? h.split('').map((c) => c + c).join('') : h, 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${alpha})`;
}
