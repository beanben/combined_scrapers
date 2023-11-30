# project specific
from utilities import get_country, combine_items, get_currency, get_tenancy_type, days_to_weeks, days_to_months, get_room_type, pw_to_pm
from items import RoomItem, BuildingItem, ContractItem, CombinedItem
from scrapy import Spider, Request
from settings import ROTATING_PROXY_LIST_PATH, proxy_list
# external packages imports
import requests
import pdb
import json
# python packages imports
from datetime import datetime
import re
import logging
logging.debug("This is a warning")


class PrestigeSpider(Spider):
    name = "prestige"
    base_url = 'https://api.prestigestudentliving.com/wp-json/wp/v2/locations?per_page=100'
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        # "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "en,fr;q=0.8,fr-FR;q=0.5,en-US;q=0.3",
        "Connection": "keep-alive",
        "Host": "api.prestigestudentliving.com",
        "Upgrade-Insecure-Requests": 1,
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:88.0) Gecko/20100101 Firefox/88.0"
    }

    def start_requests(self):
        yield Request(url=self.base_url, callback=self.parse_locations, headers=self.headers)

    def parse_locations(self, res):
        ROTATING_PROXY_LIST_PATH = proxy_list()

        location_dict = json.loads(res.text)

        for element in location_dict:
            for item in element["child_locations"]:
                location_id = item["term_id"]
                url = "https://api.prestigestudentliving.com/wp-json/wp/v2/rooms"
                url_rooms_location = f'{url}?locations={str(location_id)}'
                request_object = requests.get(url_rooms_location)
                data = request_object.json()
                for room in data:
                    url_room = f'{url}/{str(room["id"])}'
                    yield Request(url=url_room, callback=self.parse_room, dont_filter=True)

    def parse_room(self, res):
        room_dict = json.loads(res.text)

        building_description = room_dict["property"]["description"]
        building_description = re.sub(
            '<[^>]+>', '', building_description).strip().replace(
                "\n", "").replace("\r", "")

        property_number = room_dict['acf']['propertyAddress']['propertyNumber']
        street = room_dict['acf']['propertyAddress']['roadName']
        postcode = room_dict['acf']['propertyAddress']['postcode']
        city = room_dict['acf']['propertyAddress']['city']
        country = room_dict['acf']['propertyAddress']['country']

        building_item = BuildingItem({
            "name": room_dict["property"]["name"],
            "address": f'{property_number} {street}, {postcode} {city}, {country}',
            "city": city,
            "latitude": float(room_dict['acf']['coordinates']['lat']),
            "longitude": float(room_dict['acf']['coordinates']['lng']),
            "description": building_description,
            "operator": "Prestige Student Living",
        })

        # country
        building_item["country"] = get_country(
            building_item["latitude"], building_item["longitude"])

        room_description = room_dict['content']['rendered'].replace(
            '<p>', '').replace('</p>', '').replace('&#038;', ',').replace('\n', '')

        # room amenities
        amenities = [amenity["facility"]
                     for amenity in room_dict["acf"]["facilities"]]

        # building url
        start_url = "https://prestigestudentliving.com/student-accommodation/"
        building_slug = room_dict["property"]["slug"]
        building_url = f"{start_url}{building_item['city'].lower()}/{building_slug}"
        building_item["url"] = building_url

        # room url
        room_slug = room_dict["slug"].split(f"-{building_slug}")[0]
        room_url = f"{start_url}{building_item['city'].lower()}/{building_slug}/{room_slug}"

        room_item = RoomItem({
            "name": room_dict['title']['rendered'].split(",")[0],
            "description": room_description,
            "building_name": building_item['name'],
            "amenities": amenities,
            "url": room_url,
            # "availability": "available",
            "operator": building_item["operator"]
        })

        # availability
        rooms_available = room_dict['acf']['quantityAvailable']
        room_item["availability"] = ("sold out" if int(
            rooms_available) == 0 else "available")
        # if int(rooms_available) == 0:
        #     room_item["availability"] = "sold out"

        # room type
        room_item["type"] = get_room_type(room_item['name'])

        # building_api_url - to get "offers"
        building_url_id = room_dict['locations'][0]
        building_api_url = f'{res.url.split("rooms")[0]}locations/{building_url_id}'

        # contracts items
        for contract in room_dict["acf"]["contracts"]:
            utilities_included = [key for key, value in contract["contract"]
                                  ["utilities"].items() if value]

            contract_item = ContractItem({
                "description": contract["contract"]["title"],
                "room_name": room_item["name"],
                "building_name": building_item["name"],
                "utilities_included": utilities_included,
                "deposit": contract["contract"]["prices"][0]["depositPerPerson"],
                "booking_fee": contract["contract"]["prices"][0]["feePerPerson"],
                "url": room_item["url"],
                "availability": room_item["availability"],
            })

            # rents
            contract_item["rent_pw"] = float(
                contract["contract"]["prices"][0]["pricePerPersonPerWeek"])
            contract_item["rent_pm"] = pw_to_pm(contract_item["rent_pw"])

            # dates
            date_start = contract["contract"]["startDate"]
            date_end = contract["contract"]["endDate"]
            contract_item.update({
                "date_start": datetime.strptime(date_start, '%Y-%m-%d'),
                "date_end":  datetime.strptime(date_end, '%Y-%m-%d')
            })

            # currency
            contract_item["currency"] = get_currency(
                building_item["country"])

            # academic year
            year = contract_item["date_end"].year
            contract_item["academic_year"] = f'{year-1}/{year}'

            # tenancies
            contract_item["tenancy_weeks"] = days_to_weeks(
                contract_item["date_start"], contract_item["date_end"])
            contract_item["tenancy_months"] = days_to_months(
                contract_item["date_start"], contract_item["date_end"])

            # total rent
            contract_item["rent_total"] = contract_item["rent_pw"] * \
                contract_item["tenancy_weeks"]

            # tenancy_type
            contract_item["tenancy_type"] = get_tenancy_type(
                contract_item["tenancy_weeks"])

            # yield contractitem and combineditem
            yield Request(url=building_api_url, callback=self.parse_combined, meta={
                "contract_item": contract_item,
                "building_item": building_item,
                "room_item": room_item
            }, dont_filter=True)

            yield room_item

        yield building_item

    def parse_combined(self, res):
        contract_item = res.meta["contract_item"]
        building_item = res.meta["building_item"]
        room_item = res.meta["room_item"]

        # contract offers
        res_dict = json.loads(res.text)
        offer_text = [
            f'{element["post_title"]} - {element["post_content"]}' for element in res_dict["offers"]]
        if len(offer_text) != 0:
            contract_item["offers"] = offer_text

        # combined_item
        combined_item = CombinedItem()
        combined_item_info = combine_items(
            building_item, room_item, contract_item)
        combined_item.update(combined_item_info)

        yield contract_item
        yield combined_item
