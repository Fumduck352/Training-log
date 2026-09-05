require('dotenv').config();
const fs = require('fs');
const path = require('path');
const express = require('express');
const { Pool } = require('pg');

const INDEX_PATH = path.join(__dirname, 'index.html');

const PORT = process.env.PORT || 3000;

// Fixed roster: Lee's storage_key matches the original single-user key so
// his existing data carries over with no migration. New real people get
// assigned to a "spare" slot by renaming it (see PATCH /api/profiles/:id) —
// there's no public self-signup, Lee issues the names.
const SEED_PROFILES = [
  { id: 'lee', name: 'Lee', storageKey: 'lee-training-log-v1' },
  { id: 'tim', name: 'Tim', storageKey: 'training-log-v1:tim' },
  { id: 'dan', name: 'Dan', storageKey: 'training-log-v1:dan' },
  { id: 'spare-1', name: 'Spare 1', storageKey: 'training-log-v1:spare-1' },
  { id: 'spare-2', name: 'Spare 2', storageKey: 'training-log-v1:spare-2' },
  { id: 'spare-3', name: 'Spare 3', storageKey: 'training-log-v1:spare-3' },
];

if (!process.env.DATABASE_URL) {
  console.error('DATABASE_URL is not set. Add your Neon connection string as an env var.');
  process.exit(1);
}

const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  ssl: { rejectUnauthorized: false },
});

async function initDb() {
  await pool.query(`
    CREATE TABLE IF NOT EXISTS training_state (
      key TEXT PRIMARY KEY,
      value JSONB NOT NULL,
      updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
  `);
  await pool.query(`
    CREATE TABLE IF NOT EXISTS coach_feedback (
      id SERIAL PRIMARY KEY,
      exercise_id TEXT,
      day TEXT,
      message TEXT NOT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      read BOOLEAN NOT NULL DEFAULT false
    );
  `);
  await pool.query(`ALTER TABLE coach_feedback ADD COLUMN IF NOT EXISTS profile_id TEXT;`);
  await pool.query(`
    CREATE TABLE IF NOT EXISTS profiles (
      id TEXT PRIMARY KEY,
      name TEXT NOT NULL,
      storage_key TEXT NOT NULL UNIQUE,
      sort_order INTEGER NOT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
  `);
  for (let i = 0; i < SEED_PROFILES.length; i++) {
    const p = SEED_PROFILES[i];
    await pool.query(
      `INSERT INTO profiles (id, name, storage_key, sort_order) VALUES ($1, $2, $3, $4)
       ON CONFLICT (id) DO NOTHING`,
      [p.id, p.name, p.storageKey, i]
    );
  }
}

async function getStorageKey(profileId) {
  const result = await pool.query('SELECT storage_key FROM profiles WHERE id = $1', [profileId]);
  return result.rows[0] ? result.rows[0].storage_key : null;
}

const app = express();
app.use(express.json());

// ---- Version check ----
// Long-lived tabs (people who never close the app) never pick up a new
// deploy on their own. The client polls this and reloads itself the
// moment index.html's mtime changes, instead of running stale JS forever.
app.get('/api/version', (req, res) => {
  fs.stat(INDEX_PATH, (err, stats) => {
    if (err) return res.status(500).json({ error: 'stat failed' });
    res.json({ version: stats.mtimeMs });
  });
});

// ---- Profiles (fixed roster; Lee assigns spare slots to real people) ----

app.get('/api/profiles', async (req, res) => {
  const result = await pool.query('SELECT id, name FROM profiles ORDER BY sort_order ASC');
  res.json(result.rows);
});

app.patch('/api/profiles/:id', async (req, res) => {
  const { name } = req.body;
  if (!name || !name.trim()) return res.status(400).json({ error: 'missing name' });
  const result = await pool.query(
    'UPDATE profiles SET name = $1 WHERE id = $2 RETURNING id, name',
    [name.trim(), req.params.id]
  );
  if (!result.rows[0]) return res.status(404).json({ error: 'not found' });
  res.json(result.rows[0]);
});

// ---- Training state (the exercise data the app used to keep in localStorage) ----
// Scoped per profile via ?profile=<id>.

app.get('/api/state', async (req, res) => {
  const storageKey = await getStorageKey(req.query.profile);
  if (!storageKey) return res.status(404).json({ error: 'unknown profile' });
  const result = await pool.query('SELECT value FROM training_state WHERE key = $1', [storageKey]);
  res.json({ value: result.rows[0] ? result.rows[0].value : null });
});

app.put('/api/state', async (req, res) => {
  const { value } = req.body;
  if (value === undefined) return res.status(400).json({ error: 'missing value' });
  const storageKey = await getStorageKey(req.query.profile);
  if (!storageKey) return res.status(404).json({ error: 'unknown profile' });
  await pool.query(
    `INSERT INTO training_state (key, value, updated_at) VALUES ($1, $2, now())
     ON CONFLICT (key) DO UPDATE SET value = $2, updated_at = now()`,
    [storageKey, value]
  );
  res.json({ ok: true });
});

// ---- Coach feedback (written by Claude, read by the app) ----
// Scoped per profile via ?profile=<id> / profileId in the POST body.

app.get('/api/feedback', async (req, res) => {
  const profileId = req.query.profile;
  if (!profileId) return res.status(400).json({ error: 'missing profile' });
  const unreadOnly = req.query.unread === 'true';
  const query = unreadOnly
    ? 'SELECT * FROM coach_feedback WHERE profile_id = $1 AND read = false ORDER BY created_at DESC'
    : 'SELECT * FROM coach_feedback WHERE profile_id = $1 ORDER BY created_at DESC LIMIT 50';
  const result = await pool.query(query, [profileId]);
  res.json(result.rows);
});

app.post('/api/feedback', async (req, res) => {
  const { profileId, exerciseId, day, message } = req.body;
  if (!profileId) return res.status(400).json({ error: 'missing profileId' });
  if (!message) return res.status(400).json({ error: 'missing message' });
  const result = await pool.query(
    'INSERT INTO coach_feedback (profile_id, exercise_id, day, message) VALUES ($1, $2, $3, $4) RETURNING *',
    [profileId, exerciseId || null, day || null, message]
  );
  res.status(201).json(result.rows[0]);
});

app.patch('/api/feedback/:id/read', async (req, res) => {
  const result = await pool.query(
    'UPDATE coach_feedback SET read = true WHERE id = $1 RETURNING *',
    [req.params.id]
  );
  if (!result.rows[0]) return res.status(404).json({ error: 'not found' });
  res.json(result.rows[0]);
});

app.use(express.static(__dirname));

app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'index.html'));
});

initDb()
  .then(() => {
    app.listen(PORT, () => console.log(`Training log server listening on port ${PORT}`));
  })
  .catch((err) => {
    console.error('Failed to initialize database', err);
    process.exit(1);
  });
