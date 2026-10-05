"""Fail closed on credentials, runtime data, local paths or private device IDs."""
import argparse
import hashlib
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
# Reviewed, generated demo renders only. Changed/new media still fail closed.
REVIEWED_MEDIA = {
    'docs/images/climate.png': 'bf55b8ccf37cf0b700b39201e1f1de485d2818ad4acc936854f3f15ad32d241b',
    'docs/images/home-dark.png': '7e5080ad5c745756cfd59e60f74fadc1300c031d5d0f9d047029a9497250deb0',
    'docs/images/home-light.png': '342380695567afeecf7342367d96076fe4df2d3e1aab37de9071fdbba8e20b6c',
    'docs/images/monitor.png': '5ee226d908f2240e616e4306ba6da95b8ed693b2daaf9b6793eea82fa7a4df96',
    'docs/images/purifier.png': '1432ceaf21095e021fb2eb8e60dea3a35448c6b8c57f9b26e7432130046694c2',
}
OMIT = {".git", ".venv", "venv", "build", "dist", "__pycache__", ".pytest_cache", "vendor"}
PRIVATE_NAMES = {"vk03_config.json", "vk03_theme.json", "token.txt", ".env",
                 "vk03_cpu_sensor.json", "vk03_pc_sensor.json", "vk03_cpu_setup_status.json",
                 "vk03_performance.json", "vk03_exe_test.json"}
PATTERNS = (
    ("private device identifier", re.compile(r"(?:zimi|xiaomi|dmaker)_cn_\d+", re.I)),
    ("private LAN address", re.compile(r"\b(?:192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b")),
    ("Windows user path", re.compile(r"[A-Z]:[\\/]Users[\\/][^\s\"'<>]+", re.I)),
    ("JWT credential", re.compile(r"eyJ[A-Za-z0-9_-]{30,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}")),
    ("nonempty encrypted credential", re.compile(r'"token_dpapi"\s*:\s*"[^"\s]+"')),
)


def audit(root):
    errors = []
    for path in Path(root).rglob("*"):
        relative = path.relative_to(root)
        if any(part in OMIT for part in relative.parts) or not path.is_file():
            continue
        if (path.name in PRIVATE_NAMES or path.suffix.lower() in (".exe", ".dll", ".pdb", ".zip", ".log", ".flag")
                or path.name.startswith("vk03_background")):
            errors.append(str(relative) + ": runtime/private artifact")
            continue
        if path.suffix.lower() in (".png", ".jpg", ".jpeg", ".gif", ".mp4", ".webm", ".mov"):
            if REVIEWED_MEDIA.get(relative.as_posix()) == hashlib.sha256(path.read_bytes()).hexdigest():
                continue
            errors.append(str(relative) + ": media must be reviewed separately")
            continue
        try:
            content = path.read_text(encoding="utf-8-sig")
        except (UnicodeError, OSError):
            errors.append(str(relative) + ": unreviewed non-text file")
            continue
        if path.suffix == ".config":
            # .NET assembly version ranges look like IPv4 addresses; not network configuration.
            content=re.sub(r'(?:oldVersion|newVersion)="[^"]*"', '', content)
        for label, pattern in PATTERNS:
            if pattern.search(content):
                # Never print the matched secret itself.
                errors.append(str(relative) + ": " + label)
    return errors


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    findings = audit(args.root)
    if findings:
        print("Public-tree audit failed:\n" + "\n".join(findings))
        raise SystemExit(1)
    print("PASS public-tree audit: no detected credentials/private artifacts")
