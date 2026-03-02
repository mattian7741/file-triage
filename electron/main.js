'use strict';

const { app, BrowserWindow } = require('electron');
const path = require('path');
const { spawn } = require('child_process');

const PORT = 5001;
const SERVER_URL = `http://127.0.0.1:${PORT}`;

let serverProcess = null;
let mainWindow = null;

function startBackend() {
  const projectRoot = app.isPackaged
    ? path.join(process.resourcesPath, 'app')
    : app.getAppPath();
  const pythonCmd = process.env.PYTHON_PATH || 'python3';
  const args = ['-m', 'file_triage.cli', 'explorer', '--port', String(PORT)];
  const env = { ...process.env, PYTHONPATH: path.join(projectRoot, 'src') };
  serverProcess = spawn(pythonCmd, args, {
    cwd: projectRoot,
    env,
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  serverProcess.stdout.on('data', (d) => process.stdout.write(d));
  serverProcess.stderr.on('data', (d) => process.stderr.write(d));
  serverProcess.on('error', (err) => {
    console.error('Failed to start backend:', err);
  });
  serverProcess.on('exit', (code, signal) => {
    if (code !== null && code !== 0) console.error('Backend exited with code', code);
    serverProcess = null;
  });
}

function waitForServer(ms = 2000) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: { nodeIntegration: false, contextIsolation: true },
  });
  mainWindow.loadURL(SERVER_URL);
  mainWindow.on('closed', () => { mainWindow = null; });
}

app.whenReady().then(() => {
  startBackend();
  waitForServer().then(createWindow);
});

app.on('window-all-closed', () => {
  if (serverProcess) {
    serverProcess.kill('SIGTERM');
    serverProcess = null;
  }
  app.quit();
});
