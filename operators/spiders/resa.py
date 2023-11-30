# project specific
from utilities import get_address, get_city, get_room_type, get_tenancy_type, days_to_weeks, days_to_months, combine_items, get_country, get_currency, pm_to_pw
from items import CampusItem, BuildingItem, RoomItem, ContractItem, CombinedItem
from scrapy import signals, Spider, Request
from scrapy.http import TextResponse
# external packages imports
import requests
import pdb
from unidecode import unidecode
# python packages imports
from datetime import datetime
import logging
logging.debug("This is a warning")


class ResaSpider(Spider):
    name = "resa"
    base_url = 'https://www.resa.es/en/'
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        # "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "en,fr;q=0.8,fr-FR;q=0.5,en-US;q=0.3",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        # "Host": "mireserva.resa.es",
        "Pragma": "no-cache",
        "Upgrade-Insecure-Requests": 1,
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:89.0) Gecko/20100101 Firefox/89.0"
    }

    mapping_rooms = {}

    # contrat room names : room detail - room names
    # update using the closed_spider method
    mapping_exceptions = {
        "Moncloa Residence Hall": {
            "confort single room": "habitacion individual confort",
            "large single room (for disabled)": "single large room"
        },
        "Residence Hall Paseo de la Habana": {
            "large exterior single room": "big single room",
            "single room": "single room / exterior single room",
            "exterior single room": "single room / exterior single room"
        },
        "Colegio Mayor Santa Maria del Estudiante": {
            "large double room": "double room"
        },
        "Erasmo Residence Hall": {
            "single studio with kitchen": "single studio",
            "double studio with kitchen": "double studio",
            "superior double studio with kitchen (single use)": "superior double studio (single use)",
            "superior double studio with kitchen": "superior double studio"
        },
        "Claudio Coello Residence Hall": {
            "single room": "single room / superior single room",
            "superior single room": "single room / superior single room"
        },
        "Vallehermoso Residence Hall": {
            "large double room": "double room",
            "large single room": "single room"
        },
        "Miguel Antonio Caro Residence Hall": {
            "double room": "habitacion doble",
            "large single room": "single room"
        },
        "Giner de los Rios Residence Hall": {
            "double studio with kitchen": "double studio",
            "single studio with kitchen": "single studio",
            "superior double studio with kitchen (single use)": "superior double studio",
            "superior double studio with kitchen": "superior double studio"
        },
        "Hernan Cortes Residence Hall": {
            "single studio with kitchen": "single room"
        },
        "Barcelona Diagonal Residence Hall": {
            "double room (single use)": "double room",
            "large double room with terrace": "large double room"
        },
        "Sant Jordi Residence Hall": {
            "double room with outdoor bathroom": "double room with exterior bathroom",
            "large double room with outdoor bathroom": "double room with exterior bathroom",
            "single room": "single room with en-suite",
            "superior double room (single use)": "double room with en-suite",
            "double room": "double room with en-suite"
        },
        "Residencia d'Investigadors": {
            "basic superior single room": "superior basic single room",
            "premium superior single room": "superior premium single room"
        },
        "La Ciutadella Residence Hall": {
            "superior individual studio with kitchen": "single studio",
            "double studio with kitchen": "double studio",
            "single studio with kitchen": "single studio"
        },
        "Blas de Otero Residence Hall": {
            "single estudio with kitchen": "single studio"
        },
        "San Mames Residence Hall": {
            "double studio": "double room",
        },
        "Tarragona Mediterrani Residence Hall": {
            "double studio with terrace": "double studio",
            "single studio with terrace": "single studio"
        },
        "O Castro Residence Hall": {
            "single studio with shared kitchen (l)": "single studio with shared kitchen"
        },
        "Lesseps Residence Hall": {
            "executive double studio (single use)": "double studio",
            "double room with kitchen (single use)": "double studio",
            "superior double studio with kitchen": "double studio",
            "double studio with kitchen": "double studio",
            "superior double studio with kitchen (single use)": "double studio",
            "single estudio with kitchen": "single studio",
            "executive double studio (resa inn)": "double studio"
        },
        "Pere Felip Monlau Residence Hall": {
            "single studio with shared kitchen (xxl)": "single studio with shared kitchen",
            "double studio with kitchen": "double studio",
            "single studio with shared kitchen (l)": "single studio with shared kitchen",
            "single studio with shared kitchen (xl)": "single studio with shared kitchen"
        },
        "Roberto de Nobili Residence Hall": {
            "single studio with kitchen": "single studio"
        },
        "Tomas Alfaro Fournier Residence Hall": {
            "single studio with kitchen": "single studio",
            "superior single studio with kitchen": "superior single studio",
            "double studio with kitchen": "double studio"
        },
        "Campus La Salle Residence Hall": {
            "double studio with kitchen": "double studio",
            "single studio with kitchen": "single studio",
            "large double studio with kitchen": "double studio"
        },
        "Francesc Giralt i Serra Residence Hall": {
            "double studio with kitchen": "double studio",
            "superior double studio with kitchen": "single studio",
            "single studio with kitchen": "single studio",
            "superior double studio with kitchen (single use)": "double studio"
        },
        "Hipatia Residence Hall": {
            "single studio with kitchen": "single studio",
            "superior single studio with kitchen": "superior single studio with kitchenette",
            "superior double studio with kitchen": "superior double studio",
            "superior double studio with kitchen (2 rooms)": "two beedroom apartment"
        },
        "Emperador Carlos V Residence Hall": {
            "superior single studio with shared kitchen": "single studio with shared kitchen",
            "superior single studio with shared kitchen and bat": "superior single studio with shared kitchen and bathroom",
            "large single room": "single room",
            "superior single studio with kitchen": "single room"
        },
        "Campus del Mar Residence Hall": {
            "single estudio with kitchen": "single studio"
        },
        "Torre Girona Residence Hall": {
            "single estudio with kitchen": "single studio",
            "superior double studio with kitchen": "superior double studio",
            "superior single studio": "single studio"
        },
        "Damia Bonet Residence Hall": {
            "double studio with kitchen": "double studio",
            "single studio with kitchen": "single studio",
            "superior double studio with kitchen": "double studio",
            "superior double studio with kitchen (single use)": "double studio"
        },
        "La Concepcion Residence Hall": {
            "double studio with kitchen (with 1 bathroom)": "double studio",
            "double studio with kitchen (with 2 bathrooms)": "double studio with two bathrooms",
            "single studio with kitchen": "single studio"
        },
        "Manuel Agud Querol Residence Hall": {
            "superior double studio with kitchen": "double studio with kitchen",
            "superior double studio with kitchen (single use)": "double studio with kitchen",
            "single studio with kitchen": "single studio"
        },
        "Colegio de Cuenca Residence Hall": {
            "superior double studio with kitchen (single use)": "single room superior",
            "single studio with shared kitchen": "single room with shared kitchen"
        },
        "Los Abedules Residence Hall": {
            "single studio with kitchen": "single studio"
        },
        "As Burgas Residence Hall": {
            "single studio with kitchen": "single room",
            "single studio with shared kitchen": "single room with shared kitchen",
            "superior double studio with kitchen (single use)": "double room",
            "superior double studio with kitchen": "double room",
        },
        "Campus Malaga Residence Hall": {
            "single studio with shared kitchen": "single room",
            "double studio": "double studio with kitchen",
        },
        "Campus de Montilivi Residence Hall": {
            "single studio with kitchen": "single studio",
            "single room in apt. duplex (5 pax)": "single duplex studio"
        },
        "Pius Font i Quer Residence Hall": {
            "single studio with kitchen": "single studio",
            "superior double studio with kitchen (single use)": "apartament",
            "superior double studio with kitchen": "apartament"
        },
        'Rector Ramon Carande Residence Hall': {
            "superior double studio with kitchen (single use)": "superior double studio",
            "double room in apt. duplex": "double room in duplex apartment",
            "large single room in duplex apth.": "single room in duplex apartment",
            "superior double studio with kitchen": "superior double studio",
            "single room in apt.duplex 3-4 pax.": "single room in duplex apartment"
        },
        'Siglo XXI Residence Hall': {
            "double room individual use": "single room"
        }
    }

    def start_requests(self):
        url_cities = f'{self.base_url}residences/'
        yield Request(url=url_cities, callback=self.parse_cities, headers=self.headers)

    def parse_cities(self, res):

        for bullet in res.css('div.residences-city-list').css('div.residence-city'):

            city = {
                "name": unidecode(bullet.css('h3::text').get()),
                "url": bullet.css('div.city-footer').css('a::attr(href)').get()
            }

            yield Request(url=city["url"], callback=self.parse_properties, meta={"city": city}, headers=self.headers)

    def parse_properties(self, res):
        city = res.meta['city']

        # if several properties in one city
        for el in res.css('div.contenedor_listado').css('div.listado-row'):

            # name
            name = el.css('div.nombre_residencia::text').get().replace(
                "\t", "").replace("\n", "").strip()
            name = unidecode(name)
            name = name.replace(". NEW!", "")
            name = name.strip()

            # address
            address = el.css('div.datos_residencia').css(
                'li.residencia_direccion').css('p::text').get().replace("\t", "").strip()
            address = unidecode(address)

            # url
            url = el.css(
                'div.ventajas_residencia + div').css('a::attr(href)').getall()
            url = [element for element in url if self.base_url in element]
            url = url[0]

            building_item = BuildingItem({
                "address": address,
                "city": city["name"],
                "name": name,
                "operator": "Resa",
                "url": url
            })

            # mapping_rooms for checks
            building_name = building_item["name"]
            building_url = building_item["url"]
            self.mapping_rooms[building_name] = {
                "rooms_marketed_url": "",
                "rooms_marketed": set(),
                "room_marketed_equivalent": set(),
                "room_contracts_url": "",
                "room_contracts": set()
            }

            yield Request(url=building_item["url"], callback=self.parse_property, meta={"building_item": building_item, "city": city}, dont_filter=True)

        # if  only one property in the city
        element = res.css('div.contenedor_listado')
        if not element:

            # name
            name = res.css(
                'div[id="datos-residencia-wrapper"]').css('h3::text').get()
            name = unidecode(name).strip()

            # address
            address = res.css('div.datos_residencia').css(
                'li.residencia_direccion').css('p::text').get().replace("\t", "").strip()

            # url
            url = res.url

            building_item = BuildingItem({
                "address": address,
                "city": city["name"],
                "name": name,
                "operator": "Resa",
                "url": url
            })

            # mapping_rooms for checks
            building_name = building_item["name"]
            building_url = building_item["url"]
            self.mapping_rooms[building_name] = {
                "rooms_marketed_url": "",
                "rooms_marketed": set(),
                "room_marketed_equivalent": set(),
                "room_contracts_url": "",
                "room_contracts": set()
            }

            yield Request(url=building_item["url"], callback=self.parse_property, meta={"building_item": building_item, "city": city}, dont_filter=True)

    def parse_property(self, res):
        building_item = res.meta["building_item"]
        city = res.meta["city"]

        # description
        description = res.css('div.descripcion_residencia').css(
            'p *::text').getall()
        if len(description) == 0:
            description = res.css('div.wpb_content_element').css(
                'p *::text').getall()

        description = "".join(description)
        description = description.replace(
            "\xa0", "").replace("\n", "").replace("\t", "")
        building_item["description"] = unidecode(description)

        # building coordinates
        script = res.css('script').getall()
        script = [el for el in script if "var geocoder" in el][0]
        start = script.find("var geo = ") + len("var geo = ")
        end = script.find("geo = geo.split")
        coordinates = script[start:end].replace(
            "\t", "").replace("\n", "").replace('"', '').replace(";", "").strip()
        coordinates = coordinates.split(",")
        building_item.update({
            "latitude": float(coordinates[0]),
            "longitude": float(coordinates[1])
        })

        # country
        building_item["country"] = get_country(
            building_item["latitude"], building_item["longitude"])

        # agreement with uni
        noms_uni = res.css('div.convenios').css('p > em::text').get()
        text_noms_uni = res.css('div.convenios').css('p::text').get()
        if noms_uni:
            noms_uni = noms_uni.strip()
        elif text_noms_uni:
            start = text_noms_uni.find("attached to") + len("attached to")
            end = text_noms_uni.find(" and")
            noms_uni = text_noms_uni[start:end].strip()

        if noms_uni:
            building_item["description"] = f'{building_item["description"]} noms_in_place: {True}, noms_uni: {noms_uni}'

            # campus item
            for el in res.css('select[id="university-select"]').css('option[data-geolocation]'):

                # test if geolocation is available
                geolocation_available = el.css('::attr(data-geolocation)').get()
                if len(geolocation_available) != 0:

                    # campus item
                    campus_item = CampusItem({
                        "latitude": float(el.css('::attr(data-geolocation)').get().split(",")[0]),
                        "longitude": float(el.css('::attr(data-geolocation)').get().split(",")[-1])
                    })

                    # campus name
                    name = el.css('::text').get()
                    campus_item["name"] = name.replace("\n", "").strip()

                    # institution
                    campus_item["institution"] = campus_item["name"]
                    # address
                    campus_item["address"] = get_address(
                        campus_item["latitude"], campus_item["longitude"])
                    # city
                    campus_item["city"] = get_city(
                        campus_item["latitude"], campus_item["longitude"])

                    yield campus_item

        # more property info url
        url_dict = {}
        for el in res.css('div.submenu_residencias').css(
                'ul').css('a'):
            dict_key = el.css('::text').get()
            url = el.css('::attr(href)').get()
            url_dict[dict_key] = url

        # update description
        building_item["description"] = {
            "description": building_item["description"]}

        for url in url_dict.values():

            # building stats
            if "who-lives-here" in url:

                # response
                request = requests.get(url)
                resp = TextResponse(body=request.content, url=url)

                # nb_residents
                nb_residents = resp.css('div[id="porcentajes"]').css(
                    'div.residentes').css('h2::text').get()

                # mix
                mix = resp.css('p.chart-legend::text').getall()
                mix = " and ".join(mix)

                # tops
                tops = [el.css('li::text').getall()
                        for el in resp.css('div.tops').css('ol')]

                # update description
                building_item["description"].update({
                    "residents": nb_residents,
                    "mix": mix,
                    "median age": resp.css('div[id="median-age-tooltip"]::text').get(),
                    "top countries": ", ".join(tops[0]),
                    "top provinces": unidecode(", ".join(tops[1])),
                    "top universities": ", ".join(tops[2]),
                    "top degrees": ", ".join(tops[3])
                })

        # if only one description element, convert dictionnary to list
        dict_keys = building_item["description"].keys()
        if len(dict_keys) == 1:
            building_item["description"] = building_item["description"]["description"]

        # room info
        url_room_info_value = [
            el for el in url_dict.values() if "rooms-and-prices" in el]
        url_room_info_key = [
            value for key, value in url_dict.items() if "rooms and prices" in key.lower()]

        if url_room_info_value:
            url_room_info = url_room_info_value[0]
            yield Request(url=url_room_info, callback=self.parse_room, meta={"building_item": building_item}, dont_filter=True)
        elif url_room_info_key:
            url_room_info = url_room_info_key[0]
            yield Request(url=url_room_info, callback=self.parse_room, meta={"building_item": building_item}, dont_filter=True)
        elif building_item["name"] == "Resa Patacona":
            building_item["description"] = f'Hotel - {building_item["description"]}'
        else:
            msg = f'room and contract not captured for building {building_item["name"]}'
            raise Exception(msg)

    def parse_room(self, res):
        building_item = res.meta["building_item"]
        building_name = building_item["name"]

        # facilities
        building_item["facilities"] = res.css('div.servicio_content').css(
            'div *::text').getall()

        # room_item
        for room in res.css('div.detalle_habitacion'):
            room_item = RoomItem({
                "availability": "available",
                "building_name": building_item["name"],
                "operator": building_item["operator"],
                "amenities": room.css('div.nombre_Servicio::text').getall(),
                "url": res.url
            })
            # room description
            room_description = room.css('div.detalle').css(
                'p.detalle *::text').getall()
            room_description = [el.replace("\t", "").replace(
                "\n", "").strip() for el in room_description]
            room_description = [el for el in room_description if el]
            room_item["description"] = "".join(room_description)

            # room_item name
            room_name = room.css('div.detalle').css('p.titulo::text').get()
            room_name = unidecode(room_name)
            room_item["name"] = room_name.lower().strip()

            # add to mapping_rooms, the list of rooms marketed
            self.mapping_rooms[building_name]["rooms_marketed"].add(
                room_item["name"])

            # add to mapping_rooms, the room_url
            self.mapping_rooms[building_name]["rooms_marketed_url"] = room_item["url"]

            # room type
            room_item["type"] = get_room_type(
                room_item["name"], room_item["amenities"])

            # contract info - url
            url_contracts = room.css('div.detalle').css(
                'a.boton::attr(href)').get()
            building_id = url_contracts.split('/')[-1]
            contract_timings = f'https://mireserva.resa.es/resa/api/residences/{building_id}'

            yield Request(url=contract_timings, callback=self.parse_timings,
                          meta={
                              "room_item": room_item,
                              "building_item": building_item,
                              "building_id": building_id
                          }, dont_filter=True)
        yield building_item

    def parse_timings(self, res):
        building_item = res.meta["building_item"]
        room_item = res.meta["room_item"]
        building_id = res.meta["building_id"]
        building_name = building_item["name"]

        # timings for full academic year
        timings = res.json()["result"]["periods"].get("full")

        if timings is None:
            room_item["availability"] = "sold out"

            # CombinedItem
            combined_item = CombinedItem()
            combined_item_info = combine_items(building_item, room_item)
            combined_item.update(combined_item_info)
            yield combined_item
            yield room_item

        else:
            timings = [
                dict for dict in timings if "appliedTo" not in dict.keys()]

            for el in timings:
                # dates
                date_start_str = el["from"].split("T")[0]
                date_end_str = el["to"].split("T")[0]

                # tenancy_info
                tenancy_info = {
                    "date_start": datetime.strptime(date_start_str, '%Y-%m-%d').date(),
                    "date_end": datetime.strptime(date_end_str, '%Y-%m-%d').date()
                }

                date_start = tenancy_info["date_start"]
                date_end = tenancy_info["date_end"]

                # tenancy_info.update
                tenancy_info.update({
                    "tenancy_months": days_to_months(
                        date_start, date_end),
                    "tenancy_weeks": days_to_weeks(
                        date_start, date_end),
                    "academic_year": f'{date_start.year}/{date_end.year}'
                })

                # tenancy type
                tenancy_info["tenancy_type"] = get_tenancy_type(
                    tenancy_info["tenancy_weeks"])

                # contracts_url
                contracts_url = f'https://mireserva.resa.es/resa/api/rooms-type/{building_id}/{date_start_str}'

                # test if room available
                response = requests.get(contracts_url)
                result = response.json()["resultType"]
                if result == "ROOMS_TYPE_NOT_FOUND":
                    room_item["availability"] = "sold out"

                    # CombinedItem
                    combined_item = CombinedItem()
                    combined_item_info = combine_items(building_item, room_item)
                    combined_item.update(combined_item_info)
                    yield combined_item
                    yield room_item

                else:
                    yield Request(url=contracts_url, callback=self.parse_contracts,
                                  meta={
                                      "room_item": room_item,
                                      "building_item": building_item,
                                      "building_id": building_id,
                                      "tenancy_info": tenancy_info
                                  }, dont_filter=True)

    def parse_contracts(self, res):
        building_item = res.meta["building_item"]
        room_item = res.meta["room_item"]
        building_id = res.meta["building_id"]
        building_name = building_item["name"]
        tenancy_info = res.meta["tenancy_info"]

        room_contracts_url = f'https://mireserva.resa.es/#/requestCalculator/{building_id}'

        # get all full academic year contracts for one room
        contract_details = {}

        for contract in res.json()["result"]:
            utilities_included = [element["name"]
                                  for element in contract["includes"]]
            for room in contract["types"]:
                # only get rates for full academic year, ignore short term (apart hotel)
                rent_pm = room.get("fullPeriodCost")
                if rent_pm:
                    room_name = unidecode(
                        room["name"]).strip().lower()
                    contract_details[room_name] = {
                        "rent_pm": rent_pm,
                        "utilities_included": utilities_included
                    }

        # if building_item["name"] == "Emperador Carlos V Residence Hall" and "superior single studio with kitchen" in contract_details.keys():
        #     pdb.set_trace()

        # update mapping rooms
        self.mapping_rooms[building_name].update({
            "room_contracts_url": room_contracts_url,
            "room_contracts": set(contract_details.keys())
        })

        # create contract_item for related room
        for room, contracts in contract_details.items():
            contract_item_update = False
            if room == room_item["name"]:
                contract_item_update = True
            elif building_name in self.mapping_exceptions.keys():
                if room in self.mapping_exceptions[building_name].keys():
                    if self.mapping_exceptions[building_name][room] == room_item["name"]:
                        contract_item_update = True

            if contract_item_update:

                # update room_marketed_equivalent
                self.mapping_rooms[building_name]["room_marketed_equivalent"].add(
                    room)

                # contract_item
                contract_item = ContractItem()

                # update tenancy_info
                contract_item.update(tenancy_info)

                contract_item.update({
                    "room_name": room_item["name"],
                    "utilities_included": contracts["utilities_included"],
                    "availability": "available",
                    "building_name": building_item["name"],
                    "url": room_item["url"],
                    "description": f'In booking system found on {room_contracts_url}, the room is also called "{room}"'
                })

                # currency
                contract_item["currency"] = get_currency(
                    building_item["country"])

                # rent_pm
                contract_item["rent_pm"] = float(
                    contracts["rent_pm"])

                # rent_pw
                contract_item["rent_pw"] = pm_to_pw(contract_item["rent_pm"])

                # rent_total
                contract_item["rent_total"] = contract_item["rent_pm"] * \
                    contract_item["tenancy_months"]

                # combined_item
                combined_item = CombinedItem()
                combined_item_info = combine_items(
                    building_item, room_item, contract_item)
                combined_item.update(combined_item_info)
                yield combined_item
                yield contract_item

        # # room is not included in list of contracts
        contract_available = False
        check_room = []
        if building_name in self.mapping_exceptions.keys():
            check_room = [key for key, value in self.mapping_exceptions[building_name].items(
            ) if value == room_item["name"]]
        if room_item["name"] in contract_details.keys():
            contract_available = True
        elif check_room:
            contract_available = True

        if not contract_available:
            room_item["availability"] = "sold out"

            # CombinedItem
            combined_item = CombinedItem()
            combined_item_info = combine_items(building_item, room_item)
            combined_item.update(combined_item_info)
            yield combined_item

        # yield room_item
        yield room_item

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super(ResaSpider, cls).from_crawler(crawler, *args, **kwargs)
        crawler.signals.connect(spider.spider_closed,
                                signal=signals.spider_closed)
        return spider

    def spider_closed(self, spider):
        # review mapping rooms: all room_contracts must have an equivalent in rooms_marketed (raise error)
        room_names_to_adjust = list()
        for building, rooms in self.mapping_rooms.items():
            if len(rooms["room_contracts"]) != len(rooms["room_marketed_equivalent"]):
                # review mapping_rooms for particular building and manually amend room_marketed_equivalent
                # compare rooms["room_contracts"] with rooms["rooms_marketed"] by entering in the prompt "building" and "rooms" and amend the dictionnary "mapping_exceptions"
                room_names_to_adjust.append({building: rooms})

        if len(room_names_to_adjust) != 0:
            msg = f'rooms in contracts not all captured for building {building}'
            raise Exception(msg)
