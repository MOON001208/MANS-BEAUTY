import { createClient } from '@supabase/supabase-js';

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!;
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY || process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!;

export const supabase = createClient(supabaseUrl, supabaseAnonKey, { auth: { persistSession: false, autoRefreshToken: false } });

/** A product's own options ordered light to dark. Position 0 is the lightest
 *  option of this product, not a claim that it equals 21호. */
export interface ShadeLineup {
  basis: 'number' | 'brightness_words';
  options: { name: string; label: string; position: number; sold_out?: boolean }[];
}

export interface Product {
  id: string;
  name: string;
  brand: string;
  category: string;
  product_type: string | null;
  price: number | null;
  original_price: number | null;
  star_rating: number | null;
  review_count: number | null;
  thumbnail_url: string;
  product_url: string;
  ingredients_raw: string | null;
  ingredient_level: string | null;
  coverage_score: number | null;
  longevity_score: number | null;
  lightweight_score: number | null;
  suitable_shades: string[] | null;
  shade_options: Record<string, string> | null;
  suitable_skin_types: string[] | null;
  suitable_concerns: string[] | null;
  compat_oily: number | null;
  compat_dry: number | null;
  compat_sensitive: number | null;
  compat_combination: number | null;
  last_updated_at: string;
  profile_metadata?: ProfileMetadata | null;
  reviews?: { count: number }[];
}

export type WearAttributeKey = 'naturalness' | 'transfer_resistance' | 'smoothness';
export interface WearEvidence {
  score: number | null;
  evidence_count: number;
  positive_count: number;
  negative_count: number;
  mixed_count: number;
  positive_review_ids: string[];
  negative_review_ids: string[];
  mixed_review_ids: string[];
}
export interface ProfileMetadata {
  version?: string;
  metadata_revision?: number;
  source_category?: string | null;
  analyzed_count?: number;
  analyzed_at?: string;
  evidence_counts?: Record<string, number>;
  positive_concern_counts?: Record<string, number>;
  negative_concern_counts?: Record<string, number>;
  shade_source?: string;
  skin_review_counts?: Record<string, number>;
  evidence_review_ids?: Record<string, string[]>;
  concern_evidence_ids?: Record<string, string[]>;
  shade_lineup?: ShadeLineup | null;
  ingredient_source?: IngredientSource | null;
  wear_attributes?: Partial<Record<WearAttributeKey, WearEvidence>>;
  option_wear?: Record<string, { review_count: number; attributes: Partial<Record<WearAttributeKey, WearEvidence>> }>;
}

export interface Review {
  id: string;
  product_id: string;
  rating: number;
  content: string;
  skin_type: string;
  skin_trouble: string;
  skin_tone: string;
  option_name: string;
  created_at: string;
  is_best: boolean;
}

export interface IngredientSource {
  status: 'collected' | 'partial' | 'reference_only' | 'image_only' | 'not_listed' | 'unavailable';
  images?: { label: string; url: string }[];
  source_url: string;
  checked_at: string;
  entries: { label: string; text: string }[];
  references: { label: string; text: string }[];
  scope: 'seller_listing';
}

export type SkinType = 'oily' | 'dry' | 'combination' | 'sensitive';
export type SkinConcern = 'acne' | 'pore' | 'redness' | 'spots' | 'wrinkle';
export type PriorityAttr = 'coverage' | 'longevity' | 'lightweight' | WearAttributeKey;
export type ShadeChoice = '21' | '23' | '25' | 'any';
export type ApplicationMethod = 'hand' | 'tool' | 'any';
