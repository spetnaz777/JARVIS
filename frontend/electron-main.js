const { app, BrowserWindow, ipcMain, globalShortcut, Tray, Menu, nativeImage } = require("electron");
const path = require("path");
const fs = require("fs");

const SETTINGS_PATH = path.join(app.getPath("userData"), "window-settings.json");
const DEFAULT_WIDTH = 420;
const DEFAULT_HEIGHT = 620;

function loadWindowSettings() {
  try {
    if (fs.existsSync(SETTINGS_PATH)) {
      return JSON.parse(fs.readFileSync(SETTINGS_PATH, "utf8"));
    }
  } catch (e) {}
  return null;
}

function saveWindowSettings(win) {
  try {
    const bounds = win.getBounds();
    fs.writeFileSync(SETTINGS_PATH, JSON.stringify(bounds));
  } catch (e) {}
}

function getInitialPosition() {
  const { screen } = require("electron");
  const display = screen.getPrimaryDisplay();
  const { width, height } = display.workAreaSize;
  return {
    x: width - DEFAULT_WIDTH - 50,
    y: height - DEFAULT_HEIGHT - 50,
  };
}

let mainWindow = null;
let tray = null;

function createWindow() {
  const savedSettings = loadWindowSettings();
  const defaultPos = getInitialPosition();

  mainWindow = new BrowserWindow({
    width: savedSettings?.width || DEFAULT_WIDTH,
    height: savedSettings?.height || DEFAULT_HEIGHT,
    x: savedSettings?.x || defaultPos.x,
    y: savedSettings?.y || defaultPos.y,
    transparent: true,
    frame: false,
    alwaysOnTop: true,
    skipTaskbar: false,
    resizable: true,
    minWidth: 320,
    minHeight: 400,
    maxWidth: 800,
    maxHeight: 1000,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false,
      webSecurity: false,
    },
    backgroundColor: "#00000000",
    hasShadow: false,
  });

  const isDev = process.env.NODE_ENV !== "production" || !fs.existsSync(path.join(__dirname, "dist", "index.html"));

  if (isDev) {
    mainWindow.loadURL("http://localhost:3000");
    mainWindow.webContents.openDevTools({ mode: "detach" });
  } else {
    mainWindow.loadFile(path.join(__dirname, "dist", "index.html"));
  }

  mainWindow.on("close", () => {
    saveWindowSettings(mainWindow);
  });

  mainWindow.on("closed", () => {
    mainWindow = null;
  });

  mainWindow.webContents.on("did-finish-load", () => {
    mainWindow.webContents.send("window-ready");
  });
}

function createTray() {
  const iconPath = path.join(__dirname, "public", "icon.png");
  let trayIcon;

  if (fs.existsSync(iconPath)) {
    trayIcon = nativeImage.createFromPath(iconPath);
  } else {
    trayIcon = nativeImage.createEmpty();
  }

  tray = new Tray(trayIcon.resize({ width: 16, height: 16 }));

  const contextMenu = Menu.buildFromTemplate([
    {
      label: "Show JARVIS",
      click: () => {
        if (mainWindow) {
          mainWindow.show();
          mainWindow.focus();
        }
      },
    },
    { type: "separator" },
    {
      label: "Quit",
      click: () => {
        app.quit();
      },
    },
  ]);

  tray.setToolTip("JARVIS AI Assistant");
  tray.setContextMenu(contextMenu);
  tray.on("double-click", () => {
    if (mainWindow) {
      mainWindow.isVisible() ? mainWindow.hide() : mainWindow.show();
    }
  });
}

app.whenReady().then(() => {
  createWindow();
  createTray();

  globalShortcut.register("CommandOrControl+Shift+Space", () => {
    if (mainWindow) {
      if (!mainWindow.isVisible()) {
        mainWindow.show();
        mainWindow.focus();
      }
      mainWindow.webContents.send("hotkey-activate");
    }
  });

  globalShortcut.register("CommandOrControl+Shift+H", () => {
    if (mainWindow) {
      mainWindow.isVisible() ? mainWindow.hide() : mainWindow.show();
    }
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("will-quit", () => {
  globalShortcut.unregisterAll();
});

ipcMain.on("set-ignore-mouse", (event, ignore) => {
  if (mainWindow) {
    mainWindow.setIgnoreMouseEvents(ignore, { forward: true });
  }
});

ipcMain.on("minimize-window", () => {
  if (mainWindow) mainWindow.hide();
});

ipcMain.on("close-window", () => {
  app.quit();
});

ipcMain.on("toggle-always-on-top", (event, value) => {
  if (mainWindow) mainWindow.setAlwaysOnTop(value);
});

ipcMain.on("save-position", () => {
  if (mainWindow) saveWindowSettings(mainWindow);
});
