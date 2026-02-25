-- Create products table
CREATE TABLE IF NOT EXISTS public.products (
    id TEXT PRIMARY KEY, -- Olive Young Goods No (e.g., G000000...)
    name TEXT NOT NULL,
    brand TEXT,
    category TEXT, -- 'Tone Lotion/BB' or 'Cushion/Foundation'
    price NUMERIC,
    original_price NUMERIC,
    star_rating NUMERIC,
    review_count INTEGER,
    thumbnail_url TEXT,
    product_url TEXT,
    last_updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create reviews table
CREATE TABLE IF NOT EXISTS public.reviews (
    id TEXT PRIMARY KEY, -- Review ID from Olive Young
    product_id TEXT REFERENCES public.products(id) ON DELETE CASCADE,
    author TEXT,
    rating INTEGER,
    content TEXT,
    skin_type TEXT,
    option_name TEXT,
    created_at TIMESTAMP WITH TIME ZONE,
    is_best BOOLEAN DEFAULT FALSE,
    last_updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for faster recommendation queries
CREATE INDEX IF NOT EXISTS idx_products_category ON public.products(category);
CREATE INDEX IF NOT EXISTS idx_reviews_rating ON public.reviews(rating);
CREATE INDEX IF NOT EXISTS idx_reviews_product_id ON public.reviews(product_id);
