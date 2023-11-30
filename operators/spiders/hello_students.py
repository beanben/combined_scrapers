# project specific
from utilities import get_country, combine_items, get_currency, get_tenancy_type, get_room_type, pw_to_pm, weeks_to_months
from items import BuildingItem, RoomItem, CombinedItem, ContractItem
from scrapy import Spider, Request, FormRequest
# external packages imports
import pdb
# python packages imports
import re
import json
import requests
import logging
logging.debug("This is a warning")


class HelloStudentSpider(Spider):
    name = "hello_students"
    base_url = 'https://www.hellostudent.co.uk'
    headers = {
        'Accept': 'application/json, text/plain, */*',
        # 'Accept-Encoding': 'gzip, deflate, br',
        'Accept-Language': 'en,fr;q=0.8,fr-FR;q=0.5,en-US;q=0.3',
        'Connection': 'keep-alive',
        'Pragma': 'no-cache',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.16; rv:86.0) Gecko/20100101 Firefox/86.0',
    }

    def start_requests(self):
        url = self.base_url + '/locations/'
        yield Request(url=url, callback=self.parse_cities, headers=self.headers)

    def parse_cities(self, res):
        for city in res.css('select.js-select-redirect').css('option'):
            city = {
                "name": city.css('option::text').get(),
                "url": city.css('option::attr(value)').get()
            }
            if city["url"]:
                url = self.base_url + city["url"]
                yield Request(url=url, callback=self.parse_properties, meta={"city": city}, headers=self.headers)

    def parse_properties(self, res):
        for property in res.css('div.card-group__item'):
            property = {
                "name": property.css('h4.heading::text').get(),
                "url": property.css('div.card__footer').css('a::attr(href)').get()
            }
            yield Request(url=property["url"], callback=self.parse_building, meta={"city": res.meta["city"], "property": property}, headers=self.headers)

    def parse_building(self, res):
        address = "".join(res.css(
            'div.card--flat').css('div.card__content').css('p::text').getall()).replace('\n', "").replace('\t', "").strip()
        city = res.meta["city"]["name"]
        name = res.meta["property"]["name"]

        building_item = BuildingItem({
            "city": city,
            "name": name.encode("ascii", "ignore"),
            "url": res.url,
            "address": address.encode("ascii", "ignore"),
            "description": "".join(res.css('section.panel').css('p *::text').getall()).encode("ascii", "ignore"),
            "operator": "Hello Student",
            # "facilities": "n/a"
        })

        # coordinates
        google_map = res.css(
            'div.card--flat').css('div.card__content').css('p').css('a::attr(href)').get()
        if google_map:
            pattern = "/@(.*?)/data="
            coordinates = re.search(pattern, google_map).group(1)
            latitude = float(coordinates.split(',')[0])
            longitude = float(coordinates.split(',')[1])
        else:
            # https://postcodes.io/postcodes/m130ft
            postcode = " ".join(address.split(',')[-1].split(" ")[-2:])
            url_coordinates = f'https://postcodes.io/postcodes/{postcode}'
            request = requests.get(url_coordinates)
            latitude = float(request.json()["result"]["latitude"])
            longitude = float(request.json()["result"]["longitude"])

        building_item.update({
            "latitude": latitude,
            "longitude": longitude
        })
        # country
        building_item["country"] = get_country(
            building_item["latitude"], building_item["longitude"])

        message = res.css('div.t-center').css('p::text').get()

        url = "https://embedded-empiricweb-live.navondemand.co.uk/DynamicsNav/Call"
        payload = {"route": "propertylist", "command": "", "data": "{}"}

        yield FormRequest(url=url, callback=self.get_parameters, method="POST", formdata=payload, headers=self.headers, dont_filter=True, meta={"building_item": building_item, "message": message})

    def get_parameters(self, res):
        building_item = res.meta["building_item"]
        res_dict = json.loads(res.text)
        prop_param = {
            property["urlName"]: {
                "propertyNo": property["propertyNo"],
                "startDates": property["startDates"]
            } for property in res_dict["list"]["property"]}

        building_slug = building_item["url"].split('/')[-2]
        payload_param = prop_param.get(building_slug)
        if payload_param:
            payload = {
                "route": "unitlist",
                "command": "",
                "data": {"list": {"filter": {
                    "propertyNoFilter": payload_param["propertyNo"],
                    "dateFilter": payload_param["startDates"].split(',')[0]}}}
            }
            payload["data"] = json.dumps(payload["data"]).replace('"', '\"')
            yield FormRequest(url=res.url, callback=self.parse_rooms, method="POST", formdata=payload, headers=self.headers, dont_filter=True, meta={"building_item": building_item})

    def parse_rooms(self, res):
        building_item = res.meta["building_item"]
        res_dict = json.loads(res.text)

        property = res_dict['list']['property']
        for room in property:

            # room_item
            room_item = RoomItem({
                "building_name": building_item["name"],
                "name": room["unitDescription"],
                "url": building_item["url"],
                # "description": "n/a",
                # "amenities": "n/a",
                "operator": building_item["operator"],
                "availability": "available"
            })

            # room type
            room_item["type"] = get_room_type(room_item['name'])

            # availability
            rooms_available = int(room["noOfUnits"])
            if rooms_available == 0:
                room_item["availability"] = "sold out"

            # contract items
            contract_item = ContractItem({
                "building_name": building_item["name"],
                "room_name": room_item["name"],
                "rent_pw": float(room["pricePerWeek"]),
                "rent_pm": pw_to_pm(float(room["pricePerWeek"])),
                "date_end": room["endDate"],
                "date_start": room["startDate"],
                "tenancy_weeks": int(room["leaseLength"]),
                "tenancy_months": weeks_to_months(int(room["leaseLength"])),
                "url": room_item["url"],
                "availability": room_item["availability"],
                # "deposit": "n/a",
                # "description": "n/a",
                # "offers": "n/a",
                # "utilities_included": "n/a",
                # "booking_fee": "n/a"
            })
            # currency
            contract_item["currency"] = get_currency(
                building_item["country"])

            # contract academic year
            year = int(f'20{contract_item["date_end"].split("/")[-1]}')
            academic_year = f'{year-1}/{year}'
            contract_item["academic_year"] = academic_year

            # contract total rent
            contract_item["rent_total"] = contract_item["tenancy_weeks"] * \
                contract_item["rent_pw"]

            # tenancy type
            contract_item["tenancy_type"] = get_tenancy_type(
                contract_item["tenancy_weeks"])

            # combined_item
            combined_item = CombinedItem()
            combined_item_info = combine_items(
                building_item, room_item, contract_item)
            combined_item.update(combined_item_info)

            yield contract_item
            yield room_item
            yield combined_item

        yield building_item
