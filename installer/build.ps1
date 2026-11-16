# Genera installer\out\PataAuto-Setup-<versión>.exe
# Requiere: pip install pyinstaller pynput psutil pygame vgamepad numpy windows-capture  +  Inno Setup 7
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
Remove-Item -Recurse -Force out, build -ErrorAction SilentlyContinue
python -m PyInstaller --noconfirm --windowed --name PataAuto `
    --distpath out --workpath build --specpath . `
    --exclude-module cv2 --collect-all vgamepad --collect-all windows_capture --collect-submodules pynput `
    ..\pataauto.py
$msi = python -c "import vgamepad, pathlib; print(pathlib.Path(vgamepad.__file__).parent / 'win/vigem/install/x64/ViGEmBusSetup_x64.msi')"
& "C:\Program Files\Inno Setup 7\ISCC.exe" "/DViGEmMsi=$msi" PataAuto.iss
