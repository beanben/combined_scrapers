# project specific
from scrapy.http import TextResponse
# external packages imports
import requests
import re
import pdb
from unidecode import unidecode
# python packages imports
from collections import OrderedDict


def get_address(lat, lng):
    geo_url = f'https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lng}'
    response = requests.get(geo_url)

    response = TextResponse(body=response.content, url=geo_url)

    amenity = response.css('amenity::text').get()
    building_name = response.css('building::text').get()
    number = response.css('house_number::text').get()
    street = response.css('road::text').get()
    postcode = response.css('postcode::text').get()
    city = response.css('city::text').get()

    address_elements = OrderedDict({
        "amenity": amenity,
        "building_name": building_name,
        "number": number,
        "street": street,
        "postcode": postcode,
        "city": city
    })

    address_elements = OrderedDict({k: v for k,
                                    v in address_elements.items() if v is not None})

    address = ", ".join(list(address_elements.values()))

    return address


def get_city(lat, lng):
    geo_url = f'https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lng}'
    response = requests.get(geo_url)
    response = TextResponse(body=response.content, url=geo_url)
    city = response.css('city::text').get()
    if city == "City of Westminster":
        city = "London"
    return city


def get_country(lat, lng):
    geo_url = f'https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lng}'
    response = requests.get(geo_url)
    response = TextResponse(body=response.content, url=geo_url)
    country = unidecode(response.css('country::text').get())
    if country == "Eire / Ireland":
        country = "Republic of Ireland"
    if country == "Espana":
        country = "Spain"
    return country


def get_room_type(room_name, room_amenities=None):

    room_name = room_name.lower()

    # room types
    non_ensuites = ["twin", "non-ensuite",
                    "non ensuite", "double room", "double studio"]
    ensuites = ["ensuite", "en suite", "en-suite",
                "single studio with shared kitchen"]
    studios = ["studio", "1-bed", "1 bed", "one bed",
               "penthouse", "individual apartment", "duplex"]

    # conditions
    non_ensuite_conditions = [el in room_name for el in non_ensuites]
    ensuite_conditions = [el in room_name for el in ensuites]
    studio_conditions = [el in room_name for el in studios]

    # add conditions based on room amenities
    if room_amenities is not None:

        # format room_amenities as a string
        room_amenities = ", ".join(room_amenities)
        room_amenities = room_amenities.lower()

        # add conditions
        non_ensuite_conditions.extend([
            "shared bathroom" in room_amenities,
            "2 single beds" in room_amenities
        ])
        ensuite_conditions.extend([
            "bathroom fully equipped" in room_amenities and "single room" in room_name,
            "bathroom fully equipped" in room_amenities and "shared kitchen" in room_name,
            "en suite bathroom" in room_amenities and "individual room" in room_name,
            "en suite bathroom" in room_amenities and "single" in room_name,
            "en suite bathroom" in room_amenities and "individual" in room_name,
            "en suite bathroom" in room_amenities and "apart" in room_name
        ])

    # allocation of room type
    if any(non_ensuite_conditions):
        room_type = "non-ensuite"
    elif any(ensuite_conditions):
        room_type = "ensuite"
    elif any(studio_conditions):
        room_type = "studio"
    else:
        room_type = "non-ensuite"

    return room_type


def get_tenancy_type(tenancy_weeks):
    if tenancy_weeks < 50:
        tenancy_type = "shorter tenancy"
    else:
        tenancy_type = "longer tenancy"
    return tenancy_type


def get_currency(country):
    country = country.lower()
    eur_countries = ["republic of ireland", "spain", "portugal"]
    if country == "united kingdom":
        return "GBP"
    if any(el in country for el in eur_countries):
        return "EUR"


def days_to_weeks(date_start, date_end):
    tenancy_days = (date_end - date_start).days
    return round(int(tenancy_days)/7, 1)


def days_to_months(date_start, date_end):
    tenancy_days = (date_end - date_start).days
    return round(int(tenancy_days)/30, 1)


def weeks_to_months(weeks):
    return round(weeks / 52 * 12, 1)


def months_to_weeks(months):
    return round(months / 12 * 52, 1)


def pw_to_pm(rent_pw):
    return round(rent_pw * 52 / 12, 2)


def pm_to_pw(rent_pm):
    return round(rent_pm * 12 / 52, 2)


def combine_items(building_item, room_item=None, contract_item=None):
    if room_item and contract_item:
        return {
            "academic_year": contract_item.get("academic_year"),
            "address": building_item.get("address"),
            "contract__availability": contract_item.get("availability"),
            "contract__currency": contract_item.get("currency"),
            "building_description": building_item.get("description"),
            "building_name": building_item.get("name"),
            "building_url": building_item.get("url"),
            "building_university_affiliated": building_item.get("university_affiliated"),
            "city": building_item.get("city"),
            "country": building_item.get("country"),
            "contract__date_end": contract_item.get("date_end"),
            "contract__date_start": contract_item.get("date_start"),
            "contract__utilities_included": contract_item.get("utilities_included"),
            "latitude": building_item.get("latitude"),
            "longitude": building_item.get("longitude"),
            "room_amenities": room_item.get("amenities"),
            "rent_pw": contract_item.get("rent_pw"),
            "rent_pm": contract_item.get("rent_pm"),
            "rent_total": contract_item.get("rent_total"),
            "room_name": room_item.get("name"),
            "room_type": room_item.get("type"),
            "tenancy_type": contract_item.get("tenancy_type"),
            "tenancy_weeks": contract_item.get("tenancy_weeks"),
            "tenancy_months": contract_item.get("tenancy_months"),
            "offers": contract_item.get("offers"),
            "operator": building_item.get("operator")
        }
    elif room_item:
        return {
            "address": building_item.get("address"),
            "contract__availability": room_item.get("availability"),
            "building_description": building_item.get("description"),
            "building_name": building_item.get("name"),
            "city": building_item.get("city"),
            "country": building_item.get("country"),
            "latitude": building_item.get("latitude"),
            "longitude": building_item.get("longitude"),
            "room_amenities": room_item.get("amenities"),
            "room_name": room_item.get("name"),
            "room_type": room_item.get("type"),
            "building_url": building_item.get("url"),
            "operator": building_item.get("operator"),
        }
    else:
        return {
            "address": building_item.get("address"),
            "building_description": building_item.get("description"),
            "building_name": building_item.get("name"),
            "building_url": building_item.get("url"),
            "building_university_affiliated": building_item.get("university_affiliated"),
            "city": building_item.get("city"),
            "country": building_item.get("country"),
            "latitude": building_item.get("latitude"),
            "longitude": building_item.get("longitude"),
            "operator": building_item.get("operator")
        }
