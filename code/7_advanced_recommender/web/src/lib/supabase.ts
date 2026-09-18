import { createClient } from '@supabase/supabase-js';

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!;
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY || process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!;

export const supabase = createClient(supabaseUrl, supabaseAnonKey, { auth: { persistSession: false, autoRefreshToken: false } });

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
  profile_metadata?: { version?: string; analyzed_count?: number; analyzed_at?: string; evidence_counts?: Record<string, number>; positive_concern_counts?: Record<string, number>; negative_concern_counts?: Record<string, number>; shade_source?: string; skin_review_counts?: Record<string, number>; evidence_review_ids?: Record<string, string[]>; concern_evidence_ids?: Record<string, string[]> } | null;
  reviews?: { count: number }[];
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

export type SkinType = 'oily' | 'dry' | 'combination' | 'sensitive';
export type SkinConcern = 'acne' | 'pore' | 'redness' | 'spots' | 'wrinkle';
export type PriorityAttr = 'coverage' | 'longevity' | 'lightweight';
export type ShadeChoice = '21' | '23' | '25' | 'any';
export type ApplicationMethod = 'hand' | 'tool' | 'any';
