# project specific
from utilities import get_country, combine_items, get_currency, get_tenancy_type, get_room_type, pw_to_pm, weeks_to_months
from items import RoomItem, BuildingItem, CampusItem, ContractItem, VenueItem, CombinedItem
from scrapy import Spider, Request
# external packages imports
import pdb
# python packages imports
import json
import logging
logging.debug("This is a warning")


class IqStudentSpider(Spider):
    name = "iq_student"
    base_url = 'https://www.iqstudentaccommodation.com/'

    def start_requests(self):
        yield Request(url=self.base_url, callback=self.parse_cities)

    def parse_cities(self, res):
        cities = list()
        for city in res.css('div[id="block-ourcitiesblock"]').css('ul.iq-footer__nav'):
            cities += city.css('a::text').getall()

        for city in cities:
            url = res.url + "/" + city.lower()
            yield Request(url=url, callback=self.parse_campus, meta={"city": city}, dont_filter=True)
            yield Request(url=url, callback=self.parse_list, meta={"city": city})

    def parse_campus(self, res):
        city = res.meta["city"]

        script = res.css(
            'script[data-drupal-selector="drupal-settings-json"]').get()
        script = script.strip(
            '<script type="application/json" data-drupal-selector="drupal-settings-json">').strip('</script>')
        script = json.loads(script)

        universities = script["views"]["universities"]

        for campus in universities:
            campus_item = CampusItem({
                "name": campus["text"],
                "institution": campus["text"],
                "address": campus["place_name"],
                "city": city
            })

            # coordinates
            latitude = campus["geometry"]["coordinates"][1]
            longitude = campus["geometry"]["coordinates"][0]
            if latitude == 0:
                postcode = campus_item["address"].split(",")[-1].strip()
                url_coordinates = f'https://postcodes.io/postcodes/{postcode}'
                request = requests.get(url_coordinates)
                latitude = request.json()["result"]["latitude"]
                longitude = request.json()["result"]["longitude"]

            campus_item.update({
                "latitude": float(latitude),
                "longitude": float(longitude)
            })

            yield campus_item

    def parse_list(self, res):
        script = res.css(
            'script[data-drupal-selector="drupal-settings-json"]').get()
        script = script.strip(
            '<script type="application/json" data-drupal-selector="drupal-settings-json">').strip('</script>')
        script = json.loads(script)

        for room in script["views"]["roomTypes"]:
            building_item = BuildingItem({
                "name": room["building"],
                "description": room["buildingDescription"],
                "longitude": room["coordinates"][0],
                "latitude": room["coordinates"][1],
                "operator": "iQ Student Accommodation",
                "city": res.meta["city"],
            })

            # country
            building_item["country"] = get_country(
                building_item["latitude"], building_item["longitude"])

            room_item = RoomItem({
                "building_name": building_item["name"],
                "description": room["description"],
                "amenities": [amenity["name"] for amenity in room["flatFeatures"]["featured"]],
                "name": room["title"],
                "url": f'{self.base_url}{room["url"]}',
                "operator": building_item["operator"]
            })

            # room type
            room_item["type"] = get_room_type(room_item['name'])

            yield Request(url=room_item["url"], callback=self.parse_room, meta={"building_item": building_item, "room_item": room_item})

    def parse_room(self, res):
        building_item = res.meta["building_item"]
        room_item = res.meta["room_item"]

        script = res.css(
            'script[data-drupal-selector="drupal-settings-json"]').get()
        script = script.strip(
            '<script type="application/json" data-drupal-selector="drupal-settings-json">').strip('</script>')
        script = json.loads(script)

        building_info = script["foursquare"]["buildings"][0]

        # building_address
        address_line1 = building_info["properties"]["address"]["address_line1"]
        address_line2 = building_info["properties"]["address"]["address_line2"]
        postcode = building_info["properties"]["address"]["postal_code"]
        if address_line2:
            address = f'{address_line1}, {address_line2}, {postcode} {building_item["city"]}'
        else:
            address = f'{address_line1}, {postcode} {building_item["city"]}'

        building_item["address"] = address

        # building_url
        room_slug = res.url.split('/')[-1]
        building_item["url"] = res.url.split(room_slug)[0]

        # venue
        for venue_type, venue_details in script["foursquare"]["venues"].items():
            venue_item = VenueItem({
                "city": building_item["city"],
                "type": venue_type
            })
            for venue in venue_details:
                venue_item.update({
                    "longitude": venue["geometry"]["coordinates"][0],
                    "latitude": venue["geometry"]["coordinates"][1],
                    "name": venue["properties"]["title"]
                })
                yield venue_item

        try:
            room_item["availability"] = "available"
            for academic_year, contracts in script["contracts"].items():
                contract_item = ContractItem({
                    "building_name": building_info["properties"]["title"],
                    "academic_year": f"{academic_year.split('-')[0]}/20{academic_year.split('-')[-1]}"
                })

                if isinstance(contracts, list):
                    contracts = {index: contracts[index]
                                 for index in range(len(contracts))}
                for contract in contracts.values():
                    contract_item.update({
                        "rent_pw": float(contract["Amount"]),
                        "rent_pm": pw_to_pm(float(contract["Amount"])),
                        "date_end": contract["ContractDateEnd"],
                        "date_start": contract["ContractDateStart"],
                        "deposit": contract["DepositAmount"],
                        "room_name": contract["RoomTypeDescription"],
                        "description": contract["TermDescription"],
                        "tenancy_weeks": int(contract["weeks"]),
                        "tenancy_months": weeks_to_months(int(contract["weeks"])),
                        "url": room_item["url"],
                    })
                    # currency
                    contract_item["currency"] = get_currency(
                        building_item["country"])

                    # offers
                    offers = [offer["promotionDescription"]
                              for offer in contract["offers"] if offer]
                    if len(offers) != 0:
                        contract_item["offers"] = offers
                    # else:
                    #     contract_item["offers"] = "n/a"

                    # rent total
                    contract_item["rent_total"] = contract_item["rent_pw"] * \
                        contract_item["tenancy_weeks"]

                    # contract available
                    text_price = res.css('p.iq-text-bold *::text').getall()
                    text_price = " ".join([element.replace("\n", "")
                                           for element in text_price]).strip()
                    rooms_available = contract["NumberOfRooms"]
                    if text_price.strip().lower().find("fully booked") != -1:
                        contract_item["availability"] = "sold out"
                    elif int(rooms_available) == 0:
                        contract_item["availability"] = "sold out"
                    else:
                        contract_item["availability"] = "available"

                    # tenancy_type
                    contract_item["tenancy_type"] = get_tenancy_type(
                        contract_item["tenancy_weeks"])

                    # combined_item
                    combined_item = CombinedItem()
                    combined_item_info = combine_items(
                        building_item, room_item, contract_item)
                    combined_item.update(combined_item_info)

                    yield contract_item
                    yield combined_item

        except KeyError as e:
            if str(e.args[0]) == 'contracts':
                room_item["availability"] = "sold out"
            else:
                msg = f'KeyError with: {e}'
                raise Exception(msg)

        yield building_item
        yield room_item
