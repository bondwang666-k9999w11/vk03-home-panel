"""Allowlisted core release; never package user data or downloaded vendor tools."""
import argparse
from importlib.metadata import distribution, PackageNotFoundError
from pathlib import Path
import shutil
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from vk03_config import VERSION
from check_public_tree import audit

OWN_FILES = ("vk03_app.py", "vk03_home_panel_daily.py", "vk03_launcher.py", "vk03_theme.py",
             "vk03_media.py", "vk03_monitor.py", "vk03_appearance_editor.py", "vk03_config.py",
             "vk03_device_setup.py", "enable_cpu_sensors.ps1", "install_control_center.ps1",
             "stop_vk03.ps1", "StartVK03.cmd", "InstallShortcuts.cmd", "StopVK03.cmd",
             "SetupCpuSensors.cmd", "requirements.txt", "requirements-build.txt", "README.md",
             "LICENSE", "CHANGELOG.md", "THIRD_PARTY_NOTICES.md", ".gitignore")


def add_dependency_notices(stage):
    required = ("Pillow", "pystray", "PyInstaller")
    optional = ("numpy", "six", "pywin32-ctypes", "altgraph", "packaging", "pefile", "setuptools")
    index = []
    for package in required + optional:
        try:
            dist = distribution(package)
        except PackageNotFoundError:
            if package in required:
                raise RuntimeError("Build dependency not installed: " + package)
            continue
        count = 0
        for entry in dist.files or ():
            if any(term in entry.name.lower() for term in ("license", "copying", "notice")) and ".dist-info" in str(entry):
                src = Path(dist.locate_file(entry))
                if src.is_file():
                    target = stage / "DEPENDENCY_LICENSES" / package / str(entry)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(src, target)
                    count += 1
        if package in required and not count:
            raise RuntimeError("License text missing for " + package)
        index.append(package + "==" + dist.version)
        if package == "pystray":
            # Include unmodified corresponding Python source for the LGPL dependency.
            module = Path(dist.locate_file("pystray"))
            for src in module.rglob("*.py"):
                target = stage / "DEPENDENCY_SOURCE" / "pystray" / src.relative_to(module)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src, target)
    (stage / "DEPENDENCY_VERSIONS.txt").write_text("\n".join(index) + "\n", encoding="utf-8")


def build(exe, sensor_exe=None):
    findings = audit(ROOT)
    if findings:
        raise RuntimeError("Privacy audit failed: " + "; ".join(findings))
    if not exe.is_file():
        raise ValueError("Build the control center EXE first")
    destination = ROOT / "dist"
    destination.mkdir(exist_ok=True)
    archive = destination / ("VK03-v" + VERSION + "-core.zip")
    with tempfile.TemporaryDirectory(dir=destination) as directory:
        stage = Path(directory)
        for name in OWN_FILES:
            shutil.copyfile(ROOT / name, stage / name)
        for subdir in ("docs", "examples", "tools", "tests", "sensors"):
            for src in (ROOT / subdir).rglob("*"):
                if src.is_file() and src.suffix in (".md", ".json", ".py", ".ps1", ".cs", ".config", ".txt", ".png"):
                    target = stage / src.relative_to(ROOT)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(src, target)
        shutil.copyfile(exe, stage / "VK03控制中心.exe")
        runtime = exe.parent / '_internal'
        if not runtime.is_dir():
            raise ValueError('Folder build requires the adjacent _internal directory')
        shutil.copytree(runtime, stage / '_internal')
        if sensor_exe:
            shutil.copyfile(sensor_exe, stage / "sensors" / "VK03Sensors.exe")
        add_dependency_notices(stage)
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
            for src in sorted(stage.rglob("*")):
                if src.is_file():
                    z.write(src, src.relative_to(stage))
    with zipfile.ZipFile(archive) as z:
        if z.testzip() is not None:
            raise RuntimeError("Release ZIP failed integrity check")
    print("Created core release:", archive.name)
    return archive


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--exe", type=Path, required=True)
    parser.add_argument("--sensor-exe", type=Path)
    args = parser.parse_args()
    build(args.exe, args.sensor_exe)
