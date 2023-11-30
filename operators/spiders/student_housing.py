# project specific
from utilities import get_country, get_room_type, combine_items, get_currency, days_to_weeks, days_to_months, get_tenancy_type, pw_to_pm
from items import CampusItem, BuildingItem, RoomItem, ContractItem, CombinedItem, VenueItem
from scrapy import Spider, Request
# external packages imports
import pdb
import requests
# python packages imports
import urllib
from datetime import datetime
import json
from pprint import pprint
import logging
logging.debug("This is a warning")


class StudentHousingSpider(Spider):
    name = "student_housing"
    base_url = "https://thestudenthousingcompany.com"
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en,fr;q=0.8,fr-FR;q=0.5,en-US;q=0.3",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Pragma": "no-cache",
        "Upgrade-Insecure-Requests": 1,
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:89.0) Gecko/20100101 Firefox/89.0"
    }

    uni_scheme = {
        "Bailey Point": "University of Bournemouth",
        "The Courtrooms": "University of Bristol"
    }

    def start_requests(self):
        url = f'{self.base_url}/global/united-kingdom'
        yield Request(url=url, callback=self.parse_cities, headers=self.headers)

    def parse_cities(self, res):
        for el in res.css('li.navigation__item--child'):
            city = {
                "name": el.css('a.navigation__link::text').get(),
                "url":  f"{self.base_url}{el.css('a.navigation__link::attr(href)').get()}"
            }
            if "united-kingdom" in city["url"]:
                yield Request(url=city["url"], callback=self.parse_properties, meta={"city": city}, headers=self.headers, dont_filter=True)

    def parse_properties(self, res):
        city = res.meta["city"]

        # coordinates of buildings in the city
        url_coordinates = res.css(
            'div.google-maps__map').css('::attr(data-info-link)').get()
        url_coordinates = f'{self.base_url}{url_coordinates}'
        response = requests.get(url_coordinates)
        coordinates = {}
        for building in response.json()["markers"]:
            coordinates[building["title"]] = {
                "latitude": float(building["lat"]),
                "longitude": float(building["lng"])
            }

        # loop through buildings for each city
        for el in res.css('article.comparison-carousel__item'):
            building_item = BuildingItem({
                "city": city["name"],
                "description": el.css('div.comparison-carousel__item-text').css('p::text').get(),
                "operator": "The Student Housing Company"
            })

            # building name
            name = el.css('h4.comparison-carousel__item-title::text').get()
            building_item["name"] = name.replace("\r", "").replace("\n", "")

            # building coordinates
            building_item.update({
                "latitude": coordinates[building_item["name"]]["latitude"],
                "longitude": coordinates[building_item["name"]]["longitude"]
            })

            # building country
            building_item["country"] = get_country(
                building_item["latitude"], building_item["longitude"])

            # building url
            building_url = el.css('a.cm-cta__button::attr(href)').get()
            building_item["url"] = f'{self.base_url}{building_url}'

            yield Request(url=building_item["url"], callback=self.parse_property, meta={"building_item": building_item}, headers=self.headers, dont_filter=True)

    def parse_property(self, res):
        building_item = res.meta["building_item"]

        # building address
        building_item["address"] = res.css(
            'div.residence__contact-details').css('p::text').get()

        # contract utilities_included
        features = res.css(
            'section.icon-logo--type5 *::text').getall()
        features = [el.replace("\r", "").replace(
            "\n", "").strip() for el in features]
        features = [el for el in features if el]
        index_start = features.index("And more...")
        utilities_included = features[1:index_start - 1]

        # building facilities
        facilities = features[index_start+1:]
        features = res.css('section.icon-logo--type1-2 *::text').getall()
        features = [el.replace("\r", "").replace(
            "\n", "").strip() for el in features]
        features = [el for el in features if el]
        features = features[1:]
        features.extend(facilities)
        building_item["facilities"] = f'{", ".join(features)}.'

        if building_item["name"] in self.uni_scheme.keys():
            building_item["university_affiliated"] = self.uni_scheme[building_item["name"]]

            # combined_item
            combined_item = CombinedItem()
            combined_item_info = combine_items(building_item)
            combined_item.update(combined_item_info)

            # yields
            yield combined_item
            yield building_item

        else:
            url_rooms = f'{building_item["url"]}/rooms'
            yield Request(url=url_rooms, callback=self.parse_scheme, meta={"building_item": building_item, "utilities_included": utilities_included}, headers=self.headers, dont_filter=True)

    def parse_scheme(self, res):
        building_item = res.meta["building_item"]
        utilities_included = res.meta["utilities_included"]

        # script
        script = [el.replace("\r", "").replace("\n", "") for el in res.css(
            'script::text').getall() if "residenceExternalId" in el]

        try:
            script = script[0]
        except IndexError as e:
            msg = f'property likely to be managed by university: {e}'
            # in that case, update self.uni_scheme
            raise Exception(msg)

        start = script.find("searchData.results = ") + \
            len("searchData.results = ")
        script = script[start:-1]
        room_info = json.loads(script)

        for el in room_info["groups"][0]["roomTypes"]:

            room_item = RoomItem({
                "building_name": building_item["name"],
                "operator": building_item["operator"],
                "name": el["name"],
                "url": el["link"]
            })

            yield Request(url=room_item["url"], callback=self.parse_room, meta={"building_item": building_item, "utilities_included": utilities_included, "room_item": room_item}, headers=self.headers, dont_filter=True)

    def parse_room(self, res):
        building_item = res.meta["building_item"]
        utilities_included = res.meta["utilities_included"]
        room_item = res.meta["room_item"]

        # room availability
        availability = res.css('div.product__soldout-message::text').get()
        room_item["availability"] = (
            "sold out" if availability else "available")

        # room description
        room_item["description"] = res.css(
            'div.product__description').css('p::text').get()

        # room amenities
        amenities = res.css(
            'article.icon-logo__item').css('h6.icon-logo__item-title::text').getall()
        amenities = [el.replace("\r", "").replace("\n", "") for el in amenities]
        room_item["amenities"] = f'{", ".join(amenities)}.'

        # room type
        room_item["type"] = get_room_type(room_item["name"])

        # contract_info
        contract_info = {
            "building_name": building_item["name"],
            "utilities_included": f'{", ".join(utilities_included)}.',
            "room_name": room_item["name"],
            "currency": get_currency(
                building_item["country"])
        }

        # offers & "availability"
        offers = res.css('p.product__image-promo::text').get()
        if offers:
            if "sold out" in offers.lower():
                room_item["availability"] = "sold out"
            else:
                contract_info["offers"] = offers.replace("*", "")

            contract_info["availability"] = room_item["availability"]

        # url_contract info
        url_contract_info = res.css(
            'tenancy-options::attr(tenancies-link)').get()

        if url_contract_info:
            url_contract = f'{self.base_url}{url_contract_info}'

            yield Request(url=url_contract, callback=self.parse_contract, meta={
                "room_item": room_item,
                "building_item": building_item,
                "contract_info": contract_info
            }, dont_filter=True)

        else:
            # combined_item
            combined_item = CombinedItem()
            combined_item_info = combine_items(building_item, room_item)
            combined_item.update(combined_item_info)

            # yields
            yield combined_item
            yield room_item
            yield building_item

    def parse_contract(self, res):
        room_item = res.meta["room_item"]
        building_item = res.meta["building_item"]
        contract_info = res.meta["contract_info"]

        response = res.json()

        # tenancies
        for tenancy in response["tenancy-options"]:

            # academic_year
            start_year = tenancy["fromYear"]
            end_year = tenancy["toYear"]
            contract_info["academic_year"] = f'{start_year}/{end_year}'

            for tenancy_option in tenancy["tenancyOption"]:

                # max start date
                today = datetime.now()
                today = today.date()

                # date_start
                date_start = tenancy_option["startDate"]
                date_start = datetime.strptime(date_start, "%Y-%m-%d")
                contract_info["date_start"] = max(date_start.date(), today)

                # date_end
                date_end = tenancy_option["endDate"]
                date_end = datetime.strptime(date_end, "%Y-%m-%d")
                contract_info["date_end"] = date_end.date()

                # tenancies
                contract_info.update({
                    "tenancy_weeks": days_to_weeks(date_start, date_end),
                    "tenancy_months": days_to_months(date_start, date_end)
                })

                # tenancy_type
                contract_info["tenancy_type"] = get_tenancy_type(
                    contract_info["tenancy_weeks"])

                # paramters for url with prices
                parameters = {
                    "roomTypeId": response["room"]["id"],
                    "residenceExternalId": response["residence"]["id"],
                    "tenancyOptionId": tenancy_option["id"],
                    "academicYearId": tenancy["academicYearId"],
                    "maxNumOfFlatmates": 7,
                    "sortDirection": False,
                    "pageNumber": 1,
                    "pageSize": 6,
                    "pricePerNightOriginal": response["room"]["minPricePerNight"],
                    "bedId": None  # null
                }

                # start date and end dates
                start_date = tenancy_option["formattedLabel"].split(
                    "-")[0].strip()
                end_date = tenancy_option["formattedLabel"].split(
                    "-")[-1].strip()

                # add day on special occasion when it's missing
                if "between" in start_date:
                    start_date = start_date.split("between")[-1].strip()
                    start_day = datetime.strptime(
                        start_date, "%d %b %Y").strftime("%a")
                    start_date = f'{start_day[:3]}, {start_date}'
                    end_day = datetime.strptime(
                        end_date, "%d %b %Y").strftime("%a")
                    end_date = f'{end_day[:3]}, {end_date}'

                # parameters start and end dates
                parameter_start_date = start_date.replace(" ", "+")
                parameters["tenancyStartDate"] = f'{parameter_start_date}+03:00:00+GMT'
                parameter_end_date = end_date.replace(" ", "+")
                parameters["tenancyEndDate"] = f'{parameter_end_date}+03:00:00+GMT'

                # parameter: buildingIds
                url_building_ids = "https://thestudenthousingcompany.com/residence-property?residenceId="
                url_building_ids = f'{url_building_ids}{response["residence"]["id"]}'
                response_buildings = requests.get(url_building_ids)
                building_ids = [el["id"]
                                for el in response_buildings.json()["property"]["buildings"]]
                parameters["buildingIds"] = ",".join(building_ids)

                # parameter: floorIndexes
                floor_indexes = set()
                for building in response_buildings.json()["property"]["buildings"]:
                    for floor in building["floors"]:
                        floor_indexes.add(floor["index"])

                floor_indexes = [int(el)
                                 for el in floor_indexes if el.is_integer()]

                parameters["floorIndexes"] = ",".join(map(str, floor_indexes))

                # parameter: totalPriceOriginal
                query_start_date = datetime.strptime(
                    start_date, "%a, %d %b %Y")

                query_end_date = datetime.strptime(
                    end_date, "%a, %d %b %Y")
                query_params = {
                    "pricePerNight": parameters["pricePerNightOriginal"],
                    # REFORMAT DATES
                    "tenancyStartDate": query_start_date.strftime("%Y-%m-%d"),
                    "tenancyEndDate": query_end_date.strftime("%Y-%m-%d")
                }
                query_string = urllib.parse.urlencode(query_params)
                url_price = "https://thestudenthousingcompany.com/total-price?"
                url_price = f'{url_price}{query_string}'
                parameters["totalPriceOriginal"] = requests.get(url_price).json()[
                    "totalPriceValue"]

                # prices details
                url_prices_details = "https://thestudenthousingcompany.com/flats-with-beds?"
                query_string = urllib.parse.urlencode(parameters, safe="=,+")
                url_prices_details = f'{url_prices_details}{query_string}'
                response_prices = requests.get(url_prices_details)

                # prices
                room_prices = set()
                for floor in response_prices.json()["flats"]["floors"]:
                    for flats in floor["flats"]:
                        price = flats["weekPriceLabel"].split(
                            "/")[0].replace("£", "")
                        room_prices.add(float(price))

                # contract items
                for rent_pw in room_prices:

                    contract_item = ContractItem()
                    contract_item.update(contract_info)

                    contract_item.update({
                        "rent_pw": rent_pw,
                        "rent_pm": pw_to_pm(rent_pw),
                        "rent_total": rent_pw * contract_info["tenancy_weeks"]
                    })

                    # contract url
                    contract_url = "https://thestudenthousingcompany.com/booking-flow-page?residenceContentId="
                    contract_item["url"] = f'{contract_url}{response["residence"]["contentId"]}'

                    # combined_item
                    combined_item = CombinedItem()
                    combined_item_info = combine_items(
                        building_item, room_item, contract_item)
                    combined_item.update(combined_item_info)

                    # yields
                    yield combined_item
                    yield room_item
                    yield building_item
                    yield contract_item

                    # https://thestudenthousingcompany.com/flats-with-beds?roomTypeId=eyJ0eXBlIjoiUm9vbVR5cGUiLCJpZCI6MTU0MX0=&residenceExternalId=eyJ0eXBlIjoiUHJvcGVydHkiLCJpZCI6MTk3fQ==&tenancyOptionId=eyJ0eXBlIjoiVGVuYW5jeU9wdGlvbiIsImlkIjoxNDU3fQ==&tenancyStartDate=Sun,+01+Aug+2021+03:00:00+GMT&tenancyEndDate=Sun,+12+Sep+2021+03:00:00+GMT&academicYearId=eyJ0eXBlIjoiQWNhZGVtaWNZZWFyIiwiaWQiOjMzN30=&maxNumOfFlatmates=7&buildingIds=eyJ0eXBlIjoiQnVpbGRpbmciLCJpZCI6NjAxfQ==,eyJ0eXBlIjoiQnVpbGRpbmciLCJpZCI6NjA1fQ==,eyJ0eXBlIjoiQnVpbGRpbmciLCJpZCI6NjA5fQ==,eyJ0eXBlIjoiQnVpbGRpbmciLCJpZCI6NjEzfQ==,eyJ0eXBlIjoiQnVpbGRpbmciLCJpZCI6NjE3fQ==,eyJ0eXBlIjoiQnVpbGRpbmciLCJpZCI6NjIxfQ==,eyJ0eXBlIjoiQnVpbGRpbmciLCJpZCI6NjI1fQ==&floorIndexes=0,1,2,3,0&sortDirection=false&pageNumber=1&pageSize=6&totalPriceOriginal=473.99998800000003&pricePerNightOriginal=11.285714&bedId=null
