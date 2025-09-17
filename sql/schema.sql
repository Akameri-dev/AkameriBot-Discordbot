CREATE TABLE IF NOT EXISTS characters (
  id SERIAL PRIMARY KEY,
  user_id TEXT NOT NULL,        -- discord user id
  guild_id TEXT NOT NULL,       -- servidor
  name TEXT NOT NULL,
  gender TEXT,
  age INT,
  attributes JSONB DEFAULT '{}'::jsonb,  -- { "fuerza": 10, "agilidad": 8 }
  traits JSONB DEFAULT '[]'::jsonb,      -- ["valiente","curioso"]
  lore TEXT,
  image TEXT,
  approved BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE (guild_id, name)
);

CREATE TABLE IF NOT EXISTS items (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  category TEXT,
  description TEXT,
  effects JSONB DEFAULT '{}'::jsonb,     -- efectos aplicables
  uses JSONB DEFAULT '{}'::jsonb,        -- usos y parámetros
  craft JSONB DEFAULT '{}'::jsonb,       -- receta mínima o meta
  decompose JSONB DEFAULT '{}'::jsonb,   -- qué devuelva si se descompone
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS inventory (
  id SERIAL PRIMARY KEY,
  character_id INT NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
  item_id INT NOT NULL REFERENCES items(id),
  quantity INT NOT NULL DEFAULT 1,
  meta JSONB DEFAULT '{}'::jsonb,  -- posible estado (ej: durabilidad, custom name)
  UNIQUE (character_id, item_id)
);

CREATE TABLE IF NOT EXISTS recipes (
  id SERIAL PRIMARY KEY,
  result_item_id INT REFERENCES items(id),
  components JSONB NOT NULL,  -- [{"item_id":1,"qty":2},...]
  station TEXT,
  time_seconds INT DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS marketplace (
  id SERIAL PRIMARY KEY,
  seller_user_id TEXT,                -- user id del vendedor
  seller_character_id INT REFERENCES characters(id),
  item_id INT REFERENCES items(id),
  price BIGINT,
  quantity INT,
  created_at TIMESTAMPTZ DEFAULT now(),
  expires_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS attribute_defs (
  id SERIAL PRIMARY KEY,
  name TEXT UNIQUE NOT NULL,
  default_value NUMERIC DEFAULT 0,
  min_value NUMERIC,
  max_value NUMERIC
);
