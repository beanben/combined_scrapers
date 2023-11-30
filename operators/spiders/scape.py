# project specific
from utilities import get_country, get_room_type, combine_items, get_currency, days_to_weeks, days_to_months, get_tenancy_type, pw_to_pm
from items import CampusItem, BuildingItem, RoomItem, ContractItem, CombinedItem, VenueItem
from scrapy import Spider, Request
# external packages imports
import pdb
import requests
# python packages imports
from datetime import datetime
from pprint import pprint
import logging
logging.debug("This is a warning")


class ScapeSpider(Spider):
    name = "scape"
    base_url = "https://www.scape.com"
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en,fr;q=0.8,fr-FR;q=0.5,en-US;q=0.3",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Pragma": "no-cache",
        "Upgrade-Insecure-Requests": 1,
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:89.0) Gecko/20100101 Firefox/89.0"
    }

    def start_requests(self):
        url_countries = ['/en-uk', '/en-ie']
        for url_country in url_countries:
            url = f'{self.base_url}{url_country}'
            yield Request(url=url, callback=self.parse_properties, headers=self.headers, meta={"url_country": url_country})

    def parse_properties(self, res):
        url_country = res.meta["url_country"]
        parameters = url_country.split('-')
        query_parameters = {
            "path": f'/{parameters[-1]}',
            "lang": f'{parameters[0].replace("/","")}'
        }
        url_request = f'{self.base_url}/drupal/json?path={query_parameters["path"]}&lang={query_parameters["lang"]}'
        response = requests.get(url_request)

        # url_properties
        for property in response.json()["locations"]:
            building_item = BuildingItem({
                "city": property["city_name"],
                "latitude": float(property["lat"]),
                "longitude": float(property["lng"]),
                "operator": "Scape"
            })

            # bulding url
            try:
                building_item_url = property["buttons"][0]["url"]
            except:
                building_item_url = property["url"].split(
                    "student-accommodation/")[-1]
                if res.url[-1] == "/":
                    building_item_url = f'{res.url}student-accommodation/{building_item_url}'
                else:
                    building_item_url = f'{res.url}/student-accommodation/{building_item_url}'
            building_item["url"] = building_item_url

            # building country
            building_item["country"] = get_country(
                building_item["latitude"], building_item["longitude"])

            yield Request(url=building_item["url"], callback=self.parse_property, meta={"building_item": building_item, "query_parameters": query_parameters}, headers=self.headers)

    def parse_property(self, res):
        building_item = res.meta["building_item"]
        query_parameters = res.meta["query_parameters"]

        # json with building info
        # query_parameters["path"] = res.url.split("en-")[1]
        query_parameters_path = res.url.split("https://www.scape.com/en-")[1]
        if query_parameters_path[-1] == "/":
            query_parameters_path = query_parameters_path[:-1]
        url_request = f'{self.base_url}/drupal/json?path=/{query_parameters_path}&lang={query_parameters["lang"]}'
        response = requests.get(url_request)
        response_json = response.json()

        # building description
        building_description = response_json["columns_description"]
        building_description = building_description.replace(
            "\r", "").replace("\n", "").replace("<br>", "")
        building_item["description"] = building_description.split("See more")[
            0].strip()

        # building facilities
        facilities = [facility["caption"] for facility in response_json["slides"]
                      if facility["caption"] != "The Building" and facility["caption"] != "Travel times"]
        building_item["facilities"] = f'{", ".join(facilities)}.'

        # url with parameter for contracts
        # query_parameters_info = res.url.split(f'{self.base_url}/')[-1]
        # query_parameters_info = query_parameters_info[3:]
        # query_parameters_path = f'/{query_parameters_info}'
        query_parameters_path = res.url.split("https://www.scape.com/en-")[1]
        if query_parameters_path[-1] == "/":
            query_parameters_path = query_parameters_path[:-1]
        url_request = f'{self.base_url}/drupal/json?path=/{query_parameters_path}&lang={query_parameters["lang"]}'
        response = requests.get(url_request)
        response_json = response.json()
        pex_id = response_json["pex_id"]

        # url with contracts info & building name & address
        post_parametre = {"criteria": {"location": [pex_id]}}
        url_post_request = "https://www.scape.com/pex/json-interface/rs/webService/searchAvailability"
        headers = {
            'Content-type': 'application/json',
            'Accept': 'application/json'
        }
        response_contracts = requests.post(url_post_request,
                                           json=post_parametre,
                                           headers=headers)
        response_contracts_json = response_contracts.json()
        building_item.update({
            "name": response_contracts_json["locations"][0]["building"]["displayValue"],
            "address": response_contracts_json["locations"][0]["building"]["address"]
        })

        # dictionary with contract info
        response_contracts_json = response_contracts_json["locations"][0]["roomTypes"]
        contract_info = {
            "building_name": building_item["name"]
        }
        for room in response_contracts_json:
            room_name = room["roomType"]["displayValue"]
            contract_info[room_name] = list()

            for contract in room["rooms"]:
                date_start = contract["availability"]["start"]
                date_end = contract["availability"]["end"]
                academic_year = contract["availability"]["displayValue"].split(
                    " - ")[0]
                academic_year = academic_year.split(" ")[0]

                contract_detail = {
                    "date_start": datetime.strptime(date_start, '%Y-%m-%d').date(),
                    "date_end": datetime.strptime(date_end, '%Y-%m-%d').date(),
                    "rent_pw": contract["price"],
                    "academic_year": f'20{academic_year.split("/")[0].strip()}/20{academic_year.split("/")[-1].strip()}'
                }

                contract_info[room_name].append(contract_detail)

        # loop through rooms
        for room in response_json["room_types"]:
            url_room = room["url"].split("/")[-1]
            url_room = f'{res.url}/{url_room}'

            # eliminate fake rooms
            fake_room = False
            if len(room["field_room_type_nid"]) == 0:
                fake_room = True

            if not fake_room:
                yield Request(url=url_room, callback=self.parse_rooms, meta={"building_item": building_item, "query_parameters": query_parameters, "contract_info": contract_info}, headers=self.headers)

        yield building_item

    def parse_rooms(self, res):
        building_item = res.meta["building_item"]
        query_parameters = res.meta["query_parameters"]
        contract_info = res.meta["contract_info"]

        # json with rooms info
        # query_parameters_info = res.url.split(f'{self.base_url}/')[-1]
        # query_parameters_info = query_parameters_info[3:]
        # query_parameters_path = f'/{query_parameters_info}'
        query_parameters_path = res.url.split("https://www.scape.com/en-")[1]
        if query_parameters_path[-1] == "/":
            query_parameters_path = query_parameters_path[:-1]
        url_request = f'{self.base_url}/drupal/json?path=/{query_parameters_path}&lang={query_parameters["lang"]}'
        response = requests.get(url_request)
        response_json = response.json()

        for room in response_json["rooms"]:
            room_item = RoomItem({
                "building_name": building_item["name"],
                "description": room["description"],
                "name": room["title"],
                "operator": building_item['operator'],
                "type": get_room_type(room['title']),
                "url": res.url
            })

            # room availability
            room_item["availability"] = (
                "available" if room_item["name"] in contract_info.keys() else "sold out")

            if room_item["availability"] == "sold out":
                # combined_item
                combined_item = CombinedItem()
                combined_item_info = combine_items(
                    building_item, room_item)
                combined_item.update(combined_item_info)

                # yields
                yield combined_item
                yield room_item

            else:
                # contract items
                for contract in contract_info[room_item["name"]]:
                    contract_item = ContractItem({
                        "academic_year": contract["academic_year"],
                        "availability": "available",
                        "building_name": building_item["name"],
                        "date_end": contract["date_end"],
                        "date_start": contract["date_start"],
                        "rent_pw": contract["rent_pw"],
                        "room_name": room_item["name"],
                        "tenancy_weeks": days_to_weeks(contract["date_start"], contract["date_end"]),
                        "tenancy_months": days_to_months(contract["date_start"], contract["date_end"]),
                        "url": res.url
                    })

                    contract_item.update({
                        "currency": get_currency(building_item["country"]),
                        "rent_pm": pw_to_pm(contract_item["rent_pw"]),
                        "rent_total": contract_item["rent_pw"] * contract_item["tenancy_weeks"],
                        "tenancy_type": get_tenancy_type(contract_item["tenancy_weeks"])
                    })

                    # if contract_item["academic_year"] == "2021/2021":
                    #     pdb.set_trace()

                    # combined_item
                    combined_item = CombinedItem()
                    combined_item_info = combine_items(
                        building_item, room_item, contract_item)
                    combined_item.update(combined_item_info)

                    # yields
                    yield combined_item
                    yield room_item
                    yield contract_item
