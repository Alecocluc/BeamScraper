# BeamScraper

Downloads every official BeamNG.drive vehicle from the
[BeamNG documentation](https://documentation.beamng.com/official_content/vehicles/)
into one folder per vehicle.

## Setup

```
pip install -r requirements.txt
```

## Usage

```
python scraper.py                 # writes into ./vehicles
python scraper.py --out data      # custom output directory
python scraper.py --skip-images   # descriptions and manifest only
```

Each vehicle folder contains:

- `default.jpg` - the preview image (extension follows the real image format)
- `description.txt` - name, brand, slogan, description and every listed
  property (country, body style, transmission, years, drivetrain, propulsion,
  derby class, weight/power, induction type, configuration count and link)

The output directory also gets a `vehicles.json` manifest with the same data
for all vehicles.

Re-running the scraper writes into the same folders. Vehicles that share a
name (the two Ibishu Pessima generations) are told apart by their production
years, e.g. `Pessima (1988-1991)`.

If the scraper prints "No vehicles found", BeamNG changed the page layout;
`parse_vehicles()` in `scraper.py` documents which selectors it relies on.
