# project specific
from utilities import get_country, get_room_type, get_currency, pm_to_pw, days_to_months, months_to_weeks, get_tenancy_type, combine_items
from items import CampusItem, BuildingItem, RoomItem, ContractItem, CombinedItem, VenueItem
from scrapy import Spider, Request
from scrapy.http import TextResponse
# external packages imports
import pdb
import requests
# python packages imports
from pprint import pprint
from datetime import datetime
import urllib
import json
import logging
logging.debug("This is a warning")


def contract_details(contract_parameters, url_bookings):

    # get all parameters
    data = {"bookingTypes": [{"lookupValue": "ACADEMIC_YEAR"}, {"lookupValue": "FULL_YEAR"}, {"lookupValue": "SEMESTER"}, {
        "lookupValue": "SUMMMER"}, {"lookupValue": "VERY_SHORTSTAY"}, {"lookupValue": "SHORTSTAY"}]}
    url_post_request = "https://bookings.livensaliving.com//json-interface/rs/progressiveSearch/form"
    headers = {
        'Content-type': 'application/json',
        'Accept': 'application/json'
    }
    response = requests.post(url_post_request,
                             json=data,
                             headers=headers)
    data_fields = response.json()

    # get city_parameters
    city_parameters = [el["tags"] for el in response.json(
    )["categories"] if el["lookupValue"] == "AREA"][0]
    city_parameters = [
        el for el in city_parameters if el["lookupValue"] == contract_parameters["LOCATION"]][0]

    # get building parameters
    building_parameters = [el["tags"] for el in response.json(
    )["categories"] if el["lookupValue"] == "BUILDING"][0]
    building_parameters = [
        el for el in building_parameters if el["lookupValue"] == contract_parameters["BUILDING"]][0]

    # get property parameters
    room_parameters = [el["tags"] for el in response.json(
    )["categories"] if el["lookupValue"] == "PROPERTYTYPE"][0]
    room_parameters = [
        el for el in room_parameters if el["lookupValue"] == contract_parameters["ROOM_TYPE"]][0]

    # remove unecessary entries
    entries_to_remove = ('displayValue', 'count')
    for k in entries_to_remove:
        city_parameters.pop(k, None)
        building_parameters.pop(k, None)
        room_parameters.pop(k, None)

    # initial url parameters
    url_parameters = {
        "categories": [
            {"lookupValue": "AREA", "tags": [city_parameters]},
            {"lookupValue": "BUILDING", "tags": [building_parameters]},
            {"lookupValue": "PROPERTYTYPE", "tags": [room_parameters]}
        ]
    }

    # loop over period types (academic year, full year, semester)
    all_contracts = list()
    for period_type in response.json()["bookingTypes"]:

        # period type parameters
        url_parameters["bookingTypes"] = [
            {"lookupValue": period_type["lookupValue"]}]

        # get start_dates
        url_post_request = "https://bookings.livensaliving.com//json-interface/rs/progressiveSearch/form"
        response = requests.post(url_post_request,
                                 json=url_parameters,
                                 headers=headers)
        start_dates = []

        if response.json().get("messages") is None:

            for el in response.json()["startRanges"]:
                start_dates.append(el["from"])
                start_dates.append(el["to"])

            # get end_dates
            url_parameters["startDate"] = min(start_dates)
            url_post_request = "https://bookings.livensaliving.com//json-interface/rs/progressiveSearch/form"
            response = requests.post(url_post_request,
                                     json=url_parameters,
                                     headers=headers)
            end_dates = []
            for el in response.json()["endRanges"]:
                end_dates.append(el["from"])
                end_dates.append(el["to"])

            # get date ranges
            date_range = list()
            for start_date in start_dates:
                for end_date in end_dates:
                    date_range.append({
                        "from": start_date,
                        "to": end_date,
                    })

            # academic year
            current_year = min([el["from"] for el in date_range]).split("-")[0]
            academic_year = f'{current_year}/{int(current_year)+1}'

            # get contract details for all possible dates
            for dates in date_range:
                url_parameters.update({
                    "startDate": dates["from"],
                    "endDate": dates["to"]
                })
                url_post_request = "https://bookings.livensaliving.com//json-interface/rs/progressiveSearch/normalized-search"
                response = requests.post(url_post_request,
                                         json=url_parameters,
                                         headers=headers)

                # test if url parameters returned a valid period
                valid_url_parameters = (True if response.json().get(
                    "rooms") is not None else False)

                if valid_url_parameters:
                    # contracts
                    rooms = response.json()["rooms"].values()

                    contracts = [{
                        "room_id": el["id"],
                        "portfolio": response.json()["portfolios"][el["portfolioId"]]["displayValue"],
                        "lookupValue": response.json()["roomTypes"][el["roomTypeId"]]["lookupValue"]
                    } for el in rooms]

                    for element in response.json()["offers"]:
                        for contract in contracts:
                            if contract["room_id"] == element["roomId"]:
                                all_contracts.append({
                                    "portfolio": contract["portfolio"],
                                    "rent_pm": element["price"]["number"],
                                    "date_start": element["start"],
                                    "date_end": element["end"],
                                    "period_type": period_type["displayValue"],
                                    "period_type_url": period_type["lookupValue"],
                                    "academic_year": academic_year,
                                    "room_type_url": contract["lookupValue"]
                                })

        return [dict(t) for t in {tuple(d.items()) for d in all_contracts}]


class LivensaSpider(Spider):
    name = "livensa"
    base_url = 'https://en.livensaliving.com/'
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        # "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "en,fr;q=0.8,fr-FR;q=0.5,en-US;q=0.3",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Pragma": "no-cache",
        "Upgrade-Insecure-Requests": 1,
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:89.0) Gecko/20100101 Firefox/89.0"
    }

    def start_requests(self):
        countries_urls = [
            "student-accommodation-spain/",
            "student-accommodation-portugal/"
        ]
        for url in countries_urls:
            country_url = f'{self.base_url}{url}'
            yield Request(url=country_url, callback=self.parse_cities, headers=self.headers)

    def parse_cities(self, res):
        cities = res.css(
            'li.addressBox__item-accordion').css('li.accordion-plug--item')
        for el in cities:
            city = {
                "name": el.css('a::text').get(),
                "url": el.css('a::attr(href)').get()
            }
            yield Request(url=city["url"], callback=self.parse_properties, headers=self.headers, dont_filter=True, meta={"city": city})

    def parse_properties(self, res):
        city = res.meta["city"]

        properties = res.css('div.section__content').css('div.textBox')
        for el in properties:
            building_item = BuildingItem({
                "city": city["name"],
                "operator": "Livensa Living",
                "url": el.css('a::attr(href)').get()
            })

            # description
            description = el.css(' *::text').getall()
            description = [elem.replace("\t", "").replace(
                "\n", "").replace("\r", "") for elem in description]
            building_item["description"] = "".join(description)

            yield Request(url=building_item["url"], callback=self.parse_scheme, dont_filter=True, meta={"building_item": building_item})

    def parse_scheme(self, res):
        building_item = res.meta["building_item"]

        # building_name
        building_item["name"] = res.css('span.name-livensa::text').get()

        # building address
        address = res.css(
            'div.residencia__section--1').css('ul.iconsList').css('p *::text').getall()
        address = [el.replace("\t", "") for el in address]
        building_item["address"] = " ".join(address)

        # building facilities
        facilities = res.css(
            'div.slider-sync-nav').css('p.text-icon::text').getall()
        building_item["facilities"] = f'{", ".join(facilities)}.'

        # building coordinates
        coordinates = res.css('div.mapBox').css('div::attr(data-ysl-map)').get()
        coordinates = coordinates.replace(
            "\t", "").replace("\r", "").replace("\n", "")
        coordinates = coordinates.replace(
            "\\t", "").replace("\\r", "").replace("\\n", "")
        coordinates = coordinates.replace("\\", "")
        coordinates = coordinates.replace(
            'class="', "class='").replace('">', "'>")
        coordinates = json.loads(coordinates)
        coordinates = coordinates["args"]["center"]
        building_item.update({
            "latitude": float(coordinates["lat"]),
            "longitude": float(coordinates["lng"])
        })

        # country of building
        building_item["country"] = get_country(
            building_item["latitude"], building_item["longitude"])

        # offer
        contract_offer = res.css('div.section__semester').css(
            'p.semester__tit *::text').getall()
        contract_offer = "".join(contract_offer)

        # room amenities
        room_amenities = res.css(
            'div.residencia__section--5').css('p::text').getall()
        room_amenities = [el.replace("\xa0", " ").replace(
            ".", "") for el in room_amenities]
        room_amenities = [el.replace("- ", "") for el in room_amenities]
        room_amenities = f'{", ".join(room_amenities)}.'

        # get url_bookings parameteres
        data = {"buildingCode": res.css(
            'div[id="building-form"]').css('::attr(building)').get()}
        headers = {
            'Content-type': 'application/json',
            'Accept': 'application/json'
        }
        url_post_request = "https://bookings.livensaliving.com//json-interface/rs/marketing/marketingCollections"
        response = requests.post(url_post_request,
                                 json=data,
                                 headers=headers)

        for room_type in response.json()["locations"][0]["buildings"][0]["roomTypes"]:
            room_item = RoomItem({
                "building_name": building_item["name"],
                "operator": building_item["operator"],
                "name": room_type["displayValue"],
                "type": get_room_type(room_type["displayValue"]),
                "url": res.url
            })

            # room_description
            room_description = [el["value"].strip(
            ) for el in room_type["details"] if el["type"] == "DESCRIPTION"]
            if room_description:
                room_item["description"] = room_description[0]

            # room amenities
            room_amenities = [el["value"].strip(
            ) for el in room_type["details"] if el["type"] == "SHORT_DESCRIPTION"]
            if room_amenities:
                room_item["amenities"] = room_amenities[0]

            # marketing rent
            marketing_rent = room_type.get("marketingRent")
            if marketing_rent is not None:
                marketing_rent = marketing_rent["number"]

            # room available
            room_item["availability"] = (
                "available" if marketing_rent is not None else "sold out")

            if room_item["availability"] == "sold out":

                # combined_item
                combined_item = CombinedItem()
                combined_item_info = combine_items(
                    building_item, room_item)
                combined_item.update(combined_item_info)

                # yields
                yield combined_item
                yield building_item
                yield room_item

            else:

                # get contract info
                contract_parameters = {
                    "BUILDING": res.css(
                        'div[id="building-form"]').css('::attr(building)').get(),
                    "LOCATION": response.json()["locations"][0]["lookupValue"],
                    "ROOM_TYPE": room_type["lookupValue"]
                }
                url_bookings = res.css(
                    'div[id="building-form"]').css('::attr(book)').get()
                url_bookings = url_bookings.replace("<BUILDING>", contract_parameters["BUILDING"]).replace(
                    "<LOCATION>", contract_parameters["LOCATION"]).replace("<ROOM_TYPE>", contract_parameters["ROOM_TYPE"])

                contracts = contract_details(
                    contract_parameters, url_bookings)

                for contract in contracts:
                    contract_item = ContractItem({
                        "academic_year": contract["academic_year"],
                        "availability": "available",
                        "building_name": building_item["name"],
                        "currency": get_currency(building_item["country"]),
                        "date_end": datetime.strptime(contract["date_end"], "%Y-%m-%d").date(),
                        "date_start": datetime.strptime(contract["date_start"], "%Y-%m-%d").date(),
                        "offers": contract_offer,
                        "rent_pm": float(contract["rent_pm"]),
                        "rent_pw": pm_to_pw(float(contract["rent_pm"])),
                        "room_name": room_item["name"],
                        "url": res.url,
                        "description": f'contract in place for the {contract["period_type"]}'
                    })

                    # tenancy_months
                    contract_item["tenancy_months"] = days_to_months(
                        contract_item["date_start"], contract_item["date_end"])

                    # tenancy_weeks
                    contract_item["tenancy_weeks"] = months_to_weeks(
                        contract_item["tenancy_months"])

                    # tenancy_type
                    contract_item["tenancy_type"] = get_tenancy_type(
                        contract_item["tenancy_weeks"])

                    # rent_total
                    contract_item["rent_total"] = contract_item["tenancy_months"] * \
                        contract_item["rent_pm"]

                    # contract url
                    contract_url = f'{url_bookings};SEARCH_DATE:{contract["date_start"]};SEARCH_END_DATE:{contract["date_end"]};BOOKINGTYPES:{contract["period_type_url"]}'
                    contract_item["url"] = (contract_url if requests.get(
                        contract_url).status_code == 200 else res.url)

                    # combined_item
                    combined_item = CombinedItem()
                    combined_item_info = combine_items(
                        building_item, room_item, contract_item)
                    combined_item.update(combined_item_info)

                    # yields
                    yield combined_item
                    yield contract_item
                    yield room_item
                    yield building_item
