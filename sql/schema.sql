-- =============================
-- PERSONAJES
-- =============================
CREATE TABLE IF NOT EXISTS characters (
  id SERIAL PRIMARY KEY,
  user_id TEXT NOT NULL,               -- Discord user id
  guild_id TEXT NOT NULL,              -- Servidor
  name TEXT NOT NULL,
  gender TEXT,
  age INT,
  attributes JSONB DEFAULT '{}'::jsonb, -- { "fuerza": 10, "agilidad": 8 }
  traits JSONB DEFAULT '[]'::jsonb,     -- ["valiente","curioso"]
  lore TEXT,
  image TEXT,
  approved BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE (guild_id, name)
);

-- =============================
-- OBJETOS
-- =============================
CREATE TABLE IF NOT EXISTS items (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  category TEXT,
  description TEXT,
  image TEXT,                           -- imagen del objeto
  effects JSONB DEFAULT '{}'::jsonb,    -- efectos aplicables
  uses JSONB DEFAULT '{}'::jsonb,       -- usos y parámetros
  created_at TIMESTAMPTZ DEFAULT now()
);

-- =============================
-- INVENTARIO
-- =============================
CREATE TABLE IF NOT EXISTS inventory (
  id SERIAL PRIMARY KEY,
  character_id INT NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
  item_id INT NOT NULL REFERENCES items(id),
  quantity INT NOT NULL DEFAULT 1,
  meta JSONB DEFAULT '{}'::jsonb,       -- estado (ej: durabilidad, equipado, custom name)
  UNIQUE (character_id, item_id)
);

-- =============================
-- RECETAS DE CRAFTEO
-- =============================
CREATE TABLE IF NOT EXISTS recipes (
  id SERIAL PRIMARY KEY,
  result_item_id INT NOT NULL REFERENCES items(id), -- objeto que se obtiene
  components JSONB NOT NULL,                        -- [{"item_id":1,"qty":2},...]
  station TEXT,                                     -- estación opcional (ej: yunque, mesa)
  time_seconds INT DEFAULT 0,                       -- tiempo de craft
  created_at TIMESTAMPTZ DEFAULT now()
);

-- =============================
-- RECETAS DE DESCOMPOSICIÓN
-- =============================
CREATE TABLE IF NOT EXISTS decompositions (
  id SERIAL PRIMARY KEY,
  source_item_id INT NOT NULL REFERENCES items(id), -- objeto que se descompone
  results JSONB NOT NULL,                           -- [{"item_id":2,"qty":1},...]
  created_at TIMESTAMPTZ DEFAULT now()
);

-- =============================
-- MERCADOS (multiples mercados por servidor)
-- =============================
CREATE TABLE IF NOT EXISTS markets (
  id SERIAL PRIMARY KEY,
  guild_id TEXT NOT NULL,
  name TEXT NOT NULL,
  created_by TEXT,
  created_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE (guild_id, name)
);

CREATE TABLE IF NOT EXISTS market_listings (
  id SERIAL PRIMARY KEY,
  market_id INT NOT NULL REFERENCES markets(id) ON DELETE CASCADE,
  item_id INT NOT NULL REFERENCES items(id),
  price JSONB NOT NULL,            -- [{"item_id":X,"qty":Y},...] precio actual
  initial_price JSONB NOT NULL,    -- copia del precio inicial (para reset)
  initial_stock INT DEFAULT 1,     -- stock definido al añadir (para reset)
  base_stock INT DEFAULT 0,        -- stock asignado en la última actualización
  current_stock INT DEFAULT 0,     -- stock actual (se decrementa al comprar)
  created_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE (market_id, item_id)
);

-- =============================
-- ATRIBUTOS DEFINIDOS (catálogo)
-- =============================
CREATE TABLE IF NOT EXISTS attribute_defs (
  id SERIAL PRIMARY KEY,
  name TEXT UNIQUE NOT NULL,
  default_value NUMERIC DEFAULT 0,
  min_value NUMERIC,
  max_value NUMERIC
);
