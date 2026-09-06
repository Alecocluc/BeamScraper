#!/usr/bin/env python3
"""BeamScraper - download BeamNG.drive official vehicle data.

Scrapes https://documentation.beamng.com/official_content/vehicles/ and writes,
for every vehicle, a folder containing its preview image and a description.txt
with brand, slogan, description and all listed properties. A vehicles.json
manifest with the same data is written to the output directory.

Usage:
    python scraper.py                 # writes into ./vehicles
    python scraper.py --out data      # custom output directory
    python scraper.py --skip-images   # descriptions and manifest only
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup, Tag

VEHICLES_URL = "https://documentation.beamng.com/official_content/vehicles/"
USER_AGENT = "Mozilla/5.0 (compatible; BeamScraper/1.0)"
TIMEOUT = 30
INVALID_PATH_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
KNOWN_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
IMAGE_EXT_BY_TYPE = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}


def clean(text: str) -> str:
    """Collapse every run of whitespace; the page pads values with newlines."""
    return " ".join(text.split())


def safe_folder_name(name: str) -> str:
    """Strip characters that are illegal in Windows/Unix folder names."""
    return INVALID_PATH_CHARS.sub("_", name).strip(" .") or "Unknown Vehicle"


def parse_vehicles(html: str | bytes, base_url: str = VEHICLES_URL) -> list[dict]:
    """Extract every vehicle card from the vehicles page.

    Cards are located through their ``.vehicle-data`` block instead of the outer
    wrapper's class list, which BeamNG changed in 2025 (``vehicle-card`` and
    ``card-lg`` were dropped). The vehicle ``<h4>`` is searched anywhere inside
    the card because it moved from a sibling of ``.vehicle-data`` to a child.
    Key/value lookups are tag-agnostic because the "Configurations" pair uses
    ``<p>`` where every other pair uses ``<div>``.
    """
    soup = BeautifulSoup(html, "html.parser")
    vehicles: list[dict] = []

    for data in soup.find_all("div", class_="vehicle-data"):
        card = data.parent if isinstance(data.parent, Tag) else data

        title = card.find("h4")
        name = clean(title.get_text()) if title else "Unknown Vehicle"

        brand_section = card.find_parent("div", class_="vehicle-brand")
        brand_title = brand_section.find(["h2", "h3"]) if brand_section else None
        brand = clean(brand_title.get_text()) if brand_title else ""

        img = card.find("img", class_="vehicle-preview")
        img_src = (img.get("src") or img.get("data-src")) if img else None
        image_url = urljoin(base_url, img_src) if img_src else None

        slogan_tag = data.find("p", class_="slogan")
        description_tag = data.find("p", class_="text")

        properties: dict[str, str] = {}
        configurations: int | str | None = None
        configurations_url: str | None = None
        for pair in data.find_all(class_="pair"):
            key_tag = pair.find(class_="key")
            value_tag = pair.find(class_="value")
            if key_tag is None or value_tag is None:
                continue
            key = clean(key_tag.get_text()).rstrip(":").strip()
            value = clean(value_tag.get_text())
            if not key or not value:
                continue
            if key == "Configurations":
                # Rendered as "View all (18) ->" with a link to the brand page.
                match = re.search(r"\((\d+)\)", value)
                configurations = int(match.group(1)) if match else value
                link = value_tag.find("a")
                if link is not None and link.get("href"):
                    configurations_url = urljoin(base_url, link["href"])
                continue
            properties[key] = value

        vehicles.append(
            {
                "name": name,
                "brand": brand,
                "slogan": clean(slogan_tag.get_text()) if slogan_tag else None,
                "description": clean(description_tag.get_text()) if description_tag else None,
                "image_url": image_url,
                "properties": properties,
                "configurations": configurations,
                "configurations_url": configurations_url,
            }
        )

    assign_folders(vehicles)
    return vehicles


def assign_folders(vehicles: list[dict]) -> None:
    """Give every vehicle a unique, stable folder name.

    Duplicate names (the two generations of the Ibishu Pessima) are told apart
    by their production years rather than a run-dependent numeric suffix, so
    re-running the scraper writes into the same folders instead of creating
    ``Name_1``, ``Name_2``... on every run.
    """
    counts = Counter(vehicle["name"] for vehicle in vehicles)
    used: set[str] = set()
    for vehicle in vehicles:
        folder = vehicle["name"]
        if counts[folder] > 1:
            years = vehicle["properties"].get("Years", "").replace(" ", "")
            if years:
                folder = f"{folder} ({years})"
        folder = safe_folder_name(folder)
        base, index = folder, 2
        while folder.lower() in used:  # case-insensitive: Windows folders are
            folder = f"{base}_{index}"
            index += 1
        used.add(folder.lower())
        vehicle["folder"] = folder


def write_description(path: Path, vehicle: dict) -> None:
    lines = [f"Name: {vehicle['name']}"]
    if vehicle["brand"]:
        lines.append(f"Brand: {vehicle['brand']}")
    if vehicle["slogan"]:
        lines.append(f"Slogan: {vehicle['slogan']}")
    if vehicle["description"]:
        lines.append(f"Description: {vehicle['description']}")
    for key, value in vehicle["properties"].items():
        lines.append(f"{key}: {value}")
    if vehicle["configurations"] is not None:
        lines.append(f"Configurations: {vehicle['configurations']}")
    if vehicle["configurations_url"]:
        lines.append(f"Configurations URL: {vehicle['configurations_url']}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def download_image(session: requests.Session, url: str, folder: Path) -> Path:
    """Save the preview image as default.<ext>, using the real image format."""
    response = session.get(url, timeout=TIMEOUT)
    response.raise_for_status()
    extension = Path(urlsplit(url).path).suffix.lower()
    if extension not in KNOWN_IMAGE_EXTENSIONS:
        content_type = response.headers.get("Content-Type", "").split(";")[0].strip()
        extension = IMAGE_EXT_BY_TYPE.get(content_type, ".jpg")
    target = folder / f"default{extension}"
    target.write_bytes(response.content)
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scrape BeamNG.drive official vehicles.")
    parser.add_argument("--out", type=Path, default=Path("vehicles"), help="output directory (default: ./vehicles)")
    parser.add_argument("--url", default=VEHICLES_URL, help="vehicles page to scrape")
    parser.add_argument("--skip-images", action="store_true", help="do not download preview images")
    args = parser.parse_args(argv)

    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT

    print(f"Fetching {args.url}")
    response = session.get(args.url, timeout=TIMEOUT)
    response.raise_for_status()

    vehicles = parse_vehicles(response.content, args.url)
    if not vehicles:
        print(
            "No vehicles found. The page layout has probably changed again; "
            "inspect the HTML and update parse_vehicles().",
            file=sys.stderr,
        )
        return 1

    args.out.mkdir(parents=True, exist_ok=True)
    image_failures = 0
    for vehicle in vehicles:
        folder = args.out / vehicle["folder"]
        folder.mkdir(exist_ok=True)
        write_description(folder / "description.txt", vehicle)
        if vehicle["image_url"] and not args.skip_images:
            try:
                download_image(session, vehicle["image_url"], folder)
            except requests.RequestException as exc:
                image_failures += 1
                print(f"  ! image failed for {vehicle['name']}: {exc}", file=sys.stderr)
        print(f"  {vehicle['brand']} {vehicle['name']}  =>  {vehicle['folder']}/")

    manifest = args.out / "vehicles.json"
    manifest.write_text(json.dumps(vehicles, indent=2, ensure_ascii=False), encoding="utf-8")

    summary = f"Done: {len(vehicles)} vehicles written to {args.out.resolve()}"
    if image_failures:
        summary += f" ({image_failures} image download(s) failed)"
    print(summary)
    return 1 if image_failures else 0


if __name__ == "__main__":
    sys.exit(main())
