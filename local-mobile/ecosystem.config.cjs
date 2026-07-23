// PM2 config برای اجرای سرورِ لوکالِ local-mobile در سندباکس (پورت ۳۰۰۰).
// اجرا:  cd local-mobile && pm2 start ecosystem.config.cjs
module.exports = {
  apps: [
    {
      name: 'localmobile',
      script: 'server.mjs',
      interpreter: 'node',
      env: { PORT: 3000, HOST: '0.0.0.0', NODE_ENV: 'production' },
      watch: false,
      instances: 1,
      exec_mode: 'fork',
    },
  ],
}
