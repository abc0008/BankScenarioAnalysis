const { spawn } = require('child_process');
const path = require('path');

const backendPath = path.join(__dirname, 'Backend-Flask');

console.log('Current working directory:', process.cwd());
console.log('Backend path:', backendPath);

const backend = spawn('python', ['-v', 'app.py'], {
  cwd: backendPath,
  env: { 
    ...process.env, 
    FLASK_APP: 'app.py', 
    FLASK_ENV: 'development',
    FLASK_DEBUG: 'True',
    PYTHONUNBUFFERED: '1'
  },
  stdio: 'inherit'
});

backend.on('close', (code) => {
  console.log(`Backend process exited with code ${code}`);
});

process.on('SIGINT', () => {
  backend.kill('SIGINT');
  process.exit();
});