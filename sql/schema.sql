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

-- Agregar la columna image si no existe
ALTER TABLE items ADD COLUMN IF NOT EXISTS image TEXT;

-- Agregar la columna craft si no existe
ALTER TABLE items ADD COLUMN IF NOT EXISTS craft JSONB DEFAULT '{}'::jsonb;

-- Agregar la columna decompose si no existe
ALTER TABLE items ADD COLUMN IF NOT EXISTS decompose JSONB DEFAULT '{}'::jsonb;

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


-- =============================
-- ACTUALIZACIÓN DE TABLA ITEMS
-- =============================
ALTER TABLE items ADD COLUMN IF NOT EXISTS equipable BOOLEAN DEFAULT FALSE;
ALTER TABLE items ADD COLUMN IF NOT EXISTS attack TEXT;
ALTER TABLE items ADD COLUMN IF NOT EXISTS defense TEXT;
ALTER TABLE items ADD COLUMN IF NOT EXISTS max_uses INTEGER DEFAULT 0;

-- =============================
-- ACTUALIZACIÓN DE TABLA INVENTARIO
-- =============================
ALTER TABLE inventory ADD COLUMN IF NOT EXISTS current_uses INTEGER;
ALTER TABLE inventory ADD COLUMN IF NOT EXISTS equipped_slot TEXT;

-- =============================
-- TABLA DE RANURAS DE EQUIPAMIENTO
-- =============================
CREATE TABLE IF NOT EXISTS equipment_slots (
    id SERIAL PRIMARY KEY,
    guild_id TEXT NOT NULL,
    name TEXT NOT NULL,
    slot_limit INTEGER DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (guild_id, name)
);

-- =============================
-- TABLA DE LÍMITES DE INVENTARIO
-- =============================
CREATE TABLE IF NOT EXISTS inventory_limits (
    id SERIAL PRIMARY KEY,
    guild_id TEXT NOT NULL UNIQUE,
    general_limit INTEGER DEFAULT 100,
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- =============================
-- ACTUALIZACIÓN DE PERSONAJES - ATRIBUTOS BASE
-- =============================
-- Asegurarse de que los atributos base existan para todos los personajes
UPDATE characters 
SET attributes = jsonb_set(
    COALESCE(attributes, '{}'::jsonb), 
    '{ataque_base}', '5', true
)
WHERE attributes IS NULL OR NOT attributes ? 'ataque_base';

UPDATE characters 
SET attributes = jsonb_set(
    attributes, 
    '{defensa_base}', '5', true
)
WHERE NOT attributes ? 'defensa_base';

UPDATE characters 
SET attributes = jsonb_set(
    attributes, 
    '{agilidad_base}', '5', true
)
WHERE NOT attributes ? 'agilidad_base';