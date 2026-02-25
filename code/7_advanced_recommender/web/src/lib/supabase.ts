import { createClient } from '@supabase/supabase-js';

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!;
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!;

export const supabase = createClient(supabaseUrl, supabaseAnonKey);

export interface Product {
  id: string;
  name: string;
  brand: string;
  category: string;
  product_type: string | null;
  price: number;
  original_price: number;
  star_rating: number;
  review_count: number;
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
}

export interface Review {
  id: string;
  product_id: string;
  author: string;
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
