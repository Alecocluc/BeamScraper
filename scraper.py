import os
import requests
from bs4 import BeautifulSoup

# URL of the BeamNG vehicle grid
url = "https://documentation.beamng.com/official_content/vehicles/"
response = requests.get(url)
soup = BeautifulSoup(response.content, 'html.parser')

# Scrape vehicle cards
vehicle_cards = soup.find_all('div', class_='vehicle-card card card-lg shadow-small border-0 rounded')

# Loop through each vehicle card
for vehicle_card in vehicle_cards:
    # Extract vehicle name
    vehicle_name_tag = vehicle_card.find('h4', class_='full-width anchor font-weight-medium')
    vehicle_name = vehicle_name_tag.text.strip() if vehicle_name_tag else "Unknown Vehicle"

    # Create a unique folder for each vehicle, appending an index if the folder exists
    folder_name = vehicle_name
    index = 1
    while os.path.exists(folder_name):
        folder_name = f"{vehicle_name}_{index}"
        index += 1

    os.makedirs(folder_name, exist_ok=True)

    # Extract image URL
    img_tag = vehicle_card.find('img', class_='vehicle-preview')
    img_url = img_tag['src'] if img_tag else None

    if img_url:
        # Download image
        img_response = requests.get(img_url)
        with open(f"{folder_name}/default.png", 'wb') as img_file:
            img_file.write(img_response.content)

    # Extract vehicle data description
    data_tag = vehicle_card.find('div', class_='vehicle-data')
    pairs = data_tag.find_all('div', class_='pair') if data_tag else []

    # Format and write the description
    with open(f"{folder_name}/description.txt", 'w') as desc_file:
        for pair in pairs:
            key = pair.find('div', class_='key').text.strip() if pair.find('div', class_='key') else ""
            value = pair.find('div', class_='value').text.strip() if pair.find('div', class_='value') else ""
            if key and value:
                # Remove extra spaces, ensure proper formatting, and remove double colons
                key = key.rstrip(':').strip()  # Strip trailing colons/spaces
                value = " ".join(value.split())  # Clean up unnecessary spaces
                desc_file.write(f"{key}: {value}\n")
