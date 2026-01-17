# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_dynamic_libs, collect_data_files, collect_submodules

block_cipher = None

# Collect pywhispercpp binaries and data
pywhispercpp_binaries = collect_dynamic_libs('pywhispercpp')
pywhispercpp_datas = collect_data_files('pywhispercpp')

# Also collect _pywhispercpp extension
import site
import glob
site_packages = site.getsitepackages()[0]
pywhispercpp_ext = glob.glob(f'{site_packages}/_pywhispercpp*.so')
for ext in pywhispercpp_ext:
    pywhispercpp_binaries.append((ext, '.'))

# Collect dylibs folder explicitly
dylibs_path = f'{site_packages}/pywhispercpp/.dylibs'
import os
if os.path.exists(dylibs_path):
    for f in os.listdir(dylibs_path):
        if f.endswith('.dylib'):
            pywhispercpp_binaries.append((os.path.join(dylibs_path, f), 'pywhispercpp/.dylibs'))

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=pywhispercpp_binaries,
    datas=[('icons', 'icons'), ('models', 'models')] + pywhispercpp_datas,
    hiddenimports=[
        'pywhispercpp',
        'pywhispercpp.model',
        'pywhispercpp.utils',
        'pywhispercpp.constants',
        '_pywhispercpp',
        'sounddevice',
        'pynput',
        'pynput.keyboard',
        'pynput.keyboard._darwin',
        'rumps',
        'PIL',
        'numpy',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Dictator',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Dictator',
)

app = BUNDLE(
    coll,
    name='Dictator.app',
    icon='Dictator.icns',
    bundle_identifier='com.dictator.app',
    info_plist={
        'NSMicrophoneUsageDescription': 'Dictator needs microphone access to record speech for transcription.',
        'NSAppleEventsUsageDescription': 'Dictator needs accessibility access to paste transcribed text.',
        'CFBundleShortVersionString': '0.1.0',
        'LSUIElement': True,  # Hide from dock (menu bar style app)
    },
)
