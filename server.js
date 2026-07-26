require('dotenv').config();
const path = require('path');
const express = require('express');
const { Pool } = require('pg');

const PORT = process.env.PORT || 3000;
const STATE_KEY = 'lee-training-log-v1';

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
}

const app = express();
app.use(express.json());

// ---- Training state (the exercise data the app used to keep in localStorage) ----

app.get('/api/state', async (req, res) => {
  const result = await pool.query('SELECT value FROM training_state WHERE key = $1', [STATE_KEY]);
  res.json({ value: result.rows[0] ? result.rows[0].value : null });
});

app.put('/api/state', async (req, res) => {
  const { value } = req.body;
  if (value === undefined) return res.status(400).json({ error: 'missing value' });
  await pool.query(
    `INSERT INTO training_state (key, value, updated_at) VALUES ($1, $2, now())
     ON CONFLICT (key) DO UPDATE SET value = $2, updated_at = now()`,
    [STATE_KEY, value]
  );
  res.json({ ok: true });
});

// ---- Coach feedback (written by Claude, read by the app) ----

app.get('/api/feedback', async (req, res) => {
  const unreadOnly = req.query.unread === 'true';
  const query = unreadOnly
    ? 'SELECT * FROM coach_feedback WHERE read = false ORDER BY created_at DESC'
    : 'SELECT * FROM coach_feedback ORDER BY created_at DESC LIMIT 50';
  const result = await pool.query(query);
  res.json(result.rows);
});

app.post('/api/feedback', async (req, res) => {
  const { exerciseId, day, message } = req.body;
  if (!message) return res.status(400).json({ error: 'missing message' });
  const result = await pool.query(
    'INSERT INTO coach_feedback (exercise_id, day, message) VALUES ($1, $2, $3) RETURNING *',
    [exerciseId || null, day || null, message]
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
