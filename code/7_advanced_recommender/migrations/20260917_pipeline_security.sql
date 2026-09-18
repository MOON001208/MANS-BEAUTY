-- Run in Supabase SQL Editor. Additive data migration; no product/review deletion.
BEGIN;
CREATE TABLE IF NOT EXISTS public.products (
  id text PRIMARY KEY, name text NOT NULL, brand text, category text,
  price numeric, original_price numeric, star_rating numeric, review_count integer,
  thumbnail_url text, product_url text, last_updated_at timestamptz DEFAULT now()
);
CREATE TABLE IF NOT EXISTS public.reviews (
  id text PRIMARY KEY, product_id text REFERENCES public.products(id) ON DELETE RESTRICT,
  author text, rating integer, content text, skin_type text, option_name text,
  created_at timestamptz, is_best boolean DEFAULT false, last_updated_at timestamptz DEFAULT now()
);
ALTER TABLE public.products
  ADD COLUMN IF NOT EXISTS product_type text,
  ADD COLUMN IF NOT EXISTS ingredients_raw text,
  ADD COLUMN IF NOT EXISTS ingredient_level text,
  ADD COLUMN IF NOT EXISTS coverage_score numeric,
  ADD COLUMN IF NOT EXISTS longevity_score numeric,
  ADD COLUMN IF NOT EXISTS lightweight_score numeric,
  ADD COLUMN IF NOT EXISTS suitable_shades text[],
  ADD COLUMN IF NOT EXISTS shade_options jsonb,
  ADD COLUMN IF NOT EXISTS suitable_skin_types text[],
  ADD COLUMN IF NOT EXISTS suitable_concerns text[],
  ADD COLUMN IF NOT EXISTS compat_oily numeric,
  ADD COLUMN IF NOT EXISTS compat_dry numeric,
  ADD COLUMN IF NOT EXISTS compat_sensitive numeric,
  ADD COLUMN IF NOT EXISTS compat_combination numeric,
  ADD COLUMN IF NOT EXISTS profile_metadata jsonb,
  ADD COLUMN IF NOT EXISTS source_options jsonb;
ALTER TABLE public.reviews
  ADD COLUMN IF NOT EXISTS skin_tone text,
  ADD COLUMN IF NOT EXISTS skin_trouble text;
CREATE INDEX IF NOT EXISTS idx_reviews_product_id ON public.reviews(product_id);
CREATE INDEX IF NOT EXISTS idx_reviews_product_created ON public.reviews(product_id, created_at DESC, id);

ALTER TABLE public.products ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.reviews ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.products, public.reviews FROM PUBLIC, anon, authenticated;
GRANT SELECT ON TABLE public.products TO anon, authenticated;
-- Reviewer nickname is unnecessary for the public recommendation screen.
GRANT SELECT (id, product_id, rating, content, skin_type, skin_tone, skin_trouble,
  option_name, created_at, is_best, last_updated_at) ON public.reviews TO anon, authenticated;
GRANT ALL ON TABLE public.products, public.reviews TO service_role;
DROP POLICY IF EXISTS catalog_public_read ON public.products;
CREATE POLICY catalog_public_read ON public.products FOR SELECT TO anon, authenticated USING (true);
DROP POLICY IF EXISTS reviews_public_read ON public.reviews;
CREATE POLICY reviews_public_read ON public.reviews FOR SELECT TO anon, authenticated USING (true);

-- Prevent legacy destructive merge code from cascading product deletion into reviews.
DO $$
DECLARE fk record;
BEGIN
  FOR fk IN SELECT conname FROM pg_constraint
    WHERE conrelid = 'public.reviews'::regclass AND confrelid = 'public.products'::regclass
      AND contype = 'f' AND confdeltype = 'c'
  LOOP
    EXECUTE format('ALTER TABLE public.reviews DROP CONSTRAINT %I', fk.conname);
    EXECUTE format('ALTER TABLE public.reviews ADD CONSTRAINT %I FOREIGN KEY (product_id) REFERENCES public.products(id) ON DELETE RESTRICT', fk.conname);
  END LOOP;
END $$;
NOTIFY pgrst, 'reload schema';
COMMIT;

-- Verify after applying: anon/authenticated table writes must all be false.
SELECT role_name, table_name,
  has_table_privilege(role_name, 'public.' || table_name, 'INSERT') AS can_insert,
  has_table_privilege(role_name, 'public.' || table_name, 'UPDATE') AS can_update,
  has_table_privilege(role_name, 'public.' || table_name, 'DELETE') AS can_delete
FROM (VALUES ('anon'), ('authenticated')) r(role_name)
CROSS JOIN (VALUES ('products'), ('reviews')) t(table_name);
