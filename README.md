### Linux AppImage

```bash
pip3 install --break-system-packages pyinstaller appimage-builder

# 1. Build PyInstaller executable
pyinstaller --onefile --windowed kilo_manager.py

# 2. Create AppDir structure
mkdir -p AppDir/usr/bin
cp dist/kilo_manager AppDir/usr/bin/
cp kilo-manager.desktop AppDir/
cp AppRun AppDir/
chmod +x AppDir/usr/bin/kilo_manager AppDir/AppRun

# 3. Generate and build AppImage
appimage-builder --generate
appimage-builder
```