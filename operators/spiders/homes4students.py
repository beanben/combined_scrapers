# project specific
from utilities import get_country, combine_items, get_currency, get_tenancy_type, days_to_weeks, days_to_months, get_room_type, pw_to_pm
from items import RoomItem, BuildingItem, ContractItem, CombinedItem
from scrapy import Spider, Request
from scrapy.spiders import XMLFeedSpider
from settings import ROTATING_PROXY_LIST_PATH, proxy_list
# external packages imports
import pdb
# python packages imports
import json
import re
from datetime import datetime
import logging
logging.debug("This is a warning")


class Homes4StudentsSpider(XMLFeedSpider):
    name = "homes_for_students"
    start_urls = [
        'https://api.wearehomesforstudents.com/room-sitemap.xml'
    ]
    namespaces = [('n', 'http://www.sitemaps.org/schemas/sitemap/0.9')]
    itertag = 'n:loc'
    iterator = 'xml'

    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        # "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "en,fr;q=0.8,fr-FR;q=0.5,en-US;q=0.3",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Host": "api.wearehomesforstudents.com",
        "Pragma": "no-cache",
        "TE": "Trailers",
        "Upgrade-Insecure-Requests": 1,
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:88.0) Gecko/20100101 Firefox/88.0"
    }

    index_proxy = 0

    def parse_node(self, res, node):
        url = node.css('::text').get()

        # update proxies
        self.index_proxy += 1
        if self.index_proxy % 30 == 0:
            print("self.index_proxy:", self.index_proxy)
            ROTATING_PROXY_LIST_PATH = proxy_list()

        # testing
        # if "court-yard" in url:
        yield Request(url=url, callback=self.parse_room, headers=self.headers)

    def parse_room(self, res):
        room_dict = json.loads(res.text)

        building_item = BuildingItem({
            "name": room_dict['property']['name'],
            "address": room_dict['property']['acf']['locationAddress'],
            "operator": "Homes for Students"
        })

        # building_description
        building_description = room_dict["property"]["description"]
        building_item["description"] = re.sub(
            '<[^>]+>', '', building_description).strip().replace(
                "\n", "").replace("\r", "")

        # city
        city = room_dict['acf']['propertyAddress']['city']
        if len(city) == 0:
            city = room_dict['related_rooms'][0]['acf']['propertyAddress']['city']
        building_item["city"] = city

        # coordinates
        try:
            location_coordinates = room_dict['property']['acf']['locationCoordinates']
            building_item["latitude"] = float(
                location_coordinates["locationLat"])
            building_item["longitude"] = float(
                location_coordinates["locationLng"])
        except KeyError:
            location_coordinates = room_dict["acf"]["coordinates"]
            building_item["latitude"] = float(location_coordinates["lat"])
            building_item["longitude"] = float(location_coordinates["lng"])

        # country
        building_item["country"] = get_country(
            building_item["latitude"], building_item["longitude"])

        # room description
        room_description = room_dict['content']['rendered'].replace(
            '<p>', '').replace('</p>', '').replace('&#038;', ',').replace('\n', '')

        # room amenities
        amenities = [amenity["facility"]
                     for amenity in room_dict["acf"]["facilities"]]

        # building url
        building_slug = room_dict["property"]["slug"]
        base_url = "https://wearehomesforstudents.com/student-accommodation/"
        building_item["url"] = f"{base_url}{building_item['city'].lower()}/{building_slug}"

        # room url
        room_slug = room_dict["slug"].split(f"-{building_slug}")[0]
        room_url = f"{base_url}{building_item['city'].lower()}/{building_slug}/{room_slug}"

        room_item = RoomItem({
            "name": room_dict['title']['rendered'].split(",")[0],
            "description": room_description,
            "building_name": building_item['name'],
            "amenities": amenities,
            "url": room_url,
            # "availability": "available",
            "operator": building_item["operator"]
        })

        # room availability
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

            # contract_item
            contract_item = ContractItem({
                "description": contract["contract"]["title"],
                "room_name": room_item["name"],
                "building_name": building_item["name"],
                "deposit": contract["contract"]["prices"][0]["depositPerPerson"],
                "booking_fee": contract["contract"]["prices"][0]["feePerPerson"],
                "url": room_item["url"],
                "availability": room_item["availability"]
            })

            # utilities_included
            contract_item["utilities_included"] = [key for key, value in contract["contract"]
                                                   ["utilities"].items() if value]

            # dates
            date_start = contract["contract"]["startDate"]
            contract_item["date_start"] = datetime.strptime(
                date_start, '%Y-%m-%d')
            date_end = contract["contract"]["endDate"]
            contract_item["date_end"] = datetime.strptime(date_end, '%Y-%m-%d')

            # rent
            contract_item["rent_pw"] = float(
                contract["contract"]["prices"][0]["pricePerPersonPerWeek"])
            contract_item["rent_pm"] = pw_to_pm(contract_item["rent_pw"])

            # currency
            contract_item["currency"] = get_currency(
                building_item["country"])

            # academic year
            year = contract_item["date_end"].year
            contract_item["academic_year"] = f'{year-1}/{year}'

            # tenancy
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

            yield Request(url=building_api_url, callback=self.parse_combined, meta={
                "building_item": building_item,
                "room_item": room_item,
                "contract_item": contract_item,
            }, dont_filter=True)
            yield room_item

        yield building_item

    def parse_combined(self, res):
        building_item = res.meta["building_item"]
        room_item = res.meta["room_item"]
        contract_item = res.meta["contract_item"]

        # contract offers
        res_dict = json.loads(res.text)
        offers = [
            f'{element["post_title"]} - {element["post_content"]}' for element in res_dict["offers"]]
        if offers:
            contract_item["offers"] = offers

        # combined_item
        combined_item = CombinedItem()
        combined_item_info = combine_items(
            building_item, room_item, contract_item)
        combined_item.update(combined_item_info)

        yield contract_item
        yield combined_item
