/**
 * NickOS PM2 ecosystem config
 *
 * Usage:
 *   npm install -g pm2          # one-time
 *   pm2 start ecosystem.config.js
 *   pm2 save && pm2 startup     # persist across reboots
 *   pm2 logs / pm2 status       # monitor
 *   pm2 restart all             # restart
 *   pm2 stop all                # stop
 */

const path = require('path')
const ROOT  = __dirname

module.exports = {
  apps: [
    // ── FastAPI backend ────────────────────────────────────────────────────
    {
      name:         'nickos-api',
      script:       'python3',
      args:         '-m uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload',
      cwd:          ROOT,
      interpreter:  'none',
      env: {
        PYTHONUNBUFFERED: '1',
      },
      // Restart policy
      autorestart:  true,
      max_restarts: 10,
      min_uptime:   '5s',
      restart_delay: 2000,
      // Log files
      out_file:     path.join(ROOT, 'logs/api-out.log'),
      error_file:   path.join(ROOT, 'logs/api-err.log'),
      merge_logs:   true,
      log_date_format: 'YYYY-MM-DD HH:mm:ss',
    },

    // ── Vite frontend (dev) ────────────────────────────────────────────────
    {
      name:         'nickos-dashboard',
      script:       'npm',
      args:         'run dev',
      cwd:          path.join(ROOT, 'nickos-dashboard'),
      interpreter:  'none',
      autorestart:  true,
      max_restarts: 5,
      min_uptime:   '5s',
      restart_delay: 3000,
      out_file:     path.join(ROOT, 'logs/dashboard-out.log'),
      error_file:   path.join(ROOT, 'logs/dashboard-err.log'),
      merge_logs:   true,
      log_date_format: 'YYYY-MM-DD HH:mm:ss',
    },

    // ── Telegram bot ───────────────────────────────────────────────────────
    {
      name:         'nickos-bot',
      script:       'python3',
      args:         'bot/main.py',
      cwd:          ROOT,
      interpreter:  'none',
      env: {
        PYTHONUNBUFFERED: '1',
      },
      autorestart:  true,
      max_restarts: 10,
      min_uptime:   '5s',
      restart_delay: 5000,
      out_file:     path.join(ROOT, 'logs/bot-out.log'),
      error_file:   path.join(ROOT, 'logs/bot-err.log'),
      merge_logs:   true,
      log_date_format: 'YYYY-MM-DD HH:mm:ss',
    },
  ],
}
