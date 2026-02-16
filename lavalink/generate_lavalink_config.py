import json
import re
from pathlib import Path
from urllib.request import Request, urlopen


GITHUB_LATEST_RELEASE_URL = "https://api.github.com/repos/lavalink-devs/youtube-source/releases/latest"
DEPENDENCY_PATTERN = re.compile(
    r'(dependency:\s*"dev\.lavalink\.youtube:youtube-plugin:)([^"]+)(")'
)


def fetch_latest_youtube_plugin_version() -> str:
    request = Request(
        GITHUB_LATEST_RELEASE_URL,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "Klopfer-Bot-Lavalink-Config-Generator",
        },
    )

    with urlopen(request, timeout=15) as response:
        payload = json.load(response)

    tag_name = str(payload.get("tag_name", "")).strip()
    version = tag_name.lstrip("v")

    if not version:
        raise ValueError(f"Missing tag_name in GitHub response: {payload}")

    return version


def update_plugin_version(config_text: str, version: str) -> str:
    def replace(match: re.Match) -> str:
        return f'{match.group(1)}{version}{match.group(3)}'

    updated_text, replacement_count = DEPENDENCY_PATTERN.subn(replace, config_text, count=1)

    if replacement_count == 0:
        raise ValueError("Could not find youtube-plugin dependency line in application.yml")

    return updated_text


def main() -> None:
    base_path = Path.cwd()
    if not (base_path / "application.yml").exists():
        base_path = Path(__file__).resolve().parent
    input_path = base_path / "application.yml"
    output_path = base_path / "application.generated.yml"

    source_config = input_path.read_text(encoding="utf-8")

    try:
        latest_version = fetch_latest_youtube_plugin_version()
        generated_config = update_plugin_version(source_config, latest_version)
        print(f"Using youtube-plugin version: {latest_version}")
    except Exception as error:
        generated_config = source_config
        print(f"Warning: could not resolve latest youtube-plugin version ({error}).")
        print("Using application.yml as-is.")

    output_path.write_text(generated_config, encoding="utf-8")
    print(f"Wrote generated config to: {output_path}")


if __name__ == "__main__":
    main()