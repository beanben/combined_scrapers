# project specific
from utilities import get_country, combine_items, get_currency, get_tenancy_type, get_room_type, pw_to_pm, weeks_to_months
from items import BuildingItem, CampusItem, RoomItem, CombinedItem, ContractItem
from scrapy import Spider, Request
# external packages imports
import requests
import pdb
# python packages imports
import re
import json
import urllib
import logging
logging.debug("This is a warning")


class StudentRoostSpider(Spider):
    name = "student_roost"
    base_url = 'https://www.studentroost.co.uk'
    headers = {
        'Accept': 'application/json, text/plain, */*',
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept-Language': 'en,fr;q=0.8,fr-FR;q=0.5,en-US;q=0.3',
        'Connection': 'keep-alive',
        'Pragma': 'no-cache',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.16; rv:86.0) Gecko/20100101 Firefox/86.0',
    }
    query_params = {
        'filter[section]': "",
        'filter[relatedTo]': "",
        'filter[orderBy]': "",
        'expand': "",
        'year': ""
    }

    def start_requests(self):
        url = self.base_url + '/locations'
        yield Request(url=url, callback=self.parse_cities, headers=self.headers)

    def parse_cities(self, res):
        script = [script for script in res.css('script').getall()
                  if 'window.megaMenu' in script]
        start = script[0].find("window.megaMenu = ") + len("window.megaMenu = ")
        end = script[0].find("window.kinetix")
        dict_json = json.loads(script[0][start:end].strip()[:-1])

        script_year = [script for script in res.css('script').getall()
                       if 'window.kinetix' in script]
        start = script_year[0].find(
            "window.kinetix = ") + len("window.kinetix = ")
        end = script_year[0].find("window.craftPreview")
        current_year = json.loads(
            script_year[0][start:end].strip()[:-1])["year"]

        for city_detail in dict_json["locations"]["links"][0]:
            city = {
                "id": city_detail["id"],
                "name": city_detail["name"],
                "url": self.base_url + city_detail["url"],
            }

            expand__prop_n_uni = "descendants,heroImage,previewImage,hoverImage,backgroundImage,pageBuilder.grid.itemIcon,pageBuilder.images,pageBuilder.step.stepIcon,pageBuilder.linkBlock.linkImage,pageBuilder.award.itemImage,pageBuilder.faq,blogCategory,articleBuilder,articleBuilder.image,blogHeroImage,blogImage,carousel,landmarks,detailedFeatures.icon,kinetixRoom,accommodation,pageHero.backgroundImage,referAFriendContent.voucher,contactDetails,modalImage,clearingBannerCta,videoUrl,offer,semesterAccommodation,semesterAccommodation.accommodation,semesterAccommodation.accommodation.carousel,semesterAccommodation.accommodation.offer,socialLinks.socialIcon,roomsTenancies.icon,propertyHighlights.icon,propertyInfoBoxes.image,whatsHere,whatsHereOverview,roomDetails.icon,tenancyDetails.icon,featuredReview.image,thingsToDo,thingsToDoCarousel,transportCarousel,whatsOn,whatsOnCarousel,additionalInfo,additionalInfoCarousel,notice,noticeHero,noticeHero.noticeLink,whyChooseUs.stepIcon,whyChooseUs.stepSvg,notifications.icon,defaultAccommodation,accommodationOverride,accommodationOverride.heroImage,accommodationOverride.carousel,accommodationOverride.offer,accommodationOverride.offer.icon,accommodationOverride.offerHero,accommodationOverride.offerIcon,accommodationOverride.detailedFeatures.icon,accommodationOverride.notifications.icon,accommodationOverride.whatsHere,accommodationOverride.whatsHereOverview,roomOverride,brochure.pdf,copyList,propertyPageBuilder,propertyPageBuilder.events.media,offer.icon,offerHero,offerIcon,mapOverlay,locationFaq,locationFaq.faq,hubspotForms"

            query_params = self.query_params.copy()
            query_params["filter[section]"] = "accommodation"
            query_params["filter[relatedTo]"] = city["id"]
            query_params["filter[orderBy]"] = 'lft ASC'
            query_params["expand"] = expand__prop_n_uni

            # properties - next academic year:
            query_params["year"] = f'{current_year} - {current_year + 1}'
            query_string = urllib.parse.urlencode(query_params)
            url_properties = f'https://www.studentroost.co.uk/api/entries?{query_string}'

            yield Request(url=url_properties, callback=self.parse_properties, meta={"city": city, "year": current_year, "query_params": query_params}, headers=self.headers, dont_filter=True)

            # unis - next academic year:
            query_params = self.query_params.copy()
            query_params["filter[section]"] = "university"
            query_params["filter[relatedTo]"] = city["id"]
            query_params["expand"] = expand__prop_n_uni
            query_params["year"] = f'{current_year} - {current_year + 1}'
            query_string = urllib.parse.urlencode(query_params)
            url_uni = f'https://www.studentroost.co.uk/api/entries?{query_string}'
            yield Request(url=url_uni, callback=self.parse_campus, meta={"city": city}, headers=self.headers, dont_filter=True)

    def parse_properties(self, res):
        city = res.meta["city"]
        year = res.meta["year"]

        for property in res.json():

            if "-offer" not in property["slug"]:
                building_id = property["id"]

                building_item = BuildingItem({
                    "city": city["name"],
                    "name": property["title"],
                    "url": f'{self.base_url}/{property["url"]}',
                    "description": property["fields"]["introText"].replace('\n', "").strip(),
                    "facilities": [facility["fields"]["featureTitle"]
                                   for facility in property["whatsHere"]],
                    "operator": "Student Roost",
                })

                #  address
                if property["fields"]["mapLocation"]["parts"]["number"]:
                    number = property["fields"]["mapLocation"]["parts"]["number"]
                    street = property["fields"]["mapLocation"]["parts"]["address"]
                    town = property["fields"]["mapLocation"]["parts"]["city"]
                    postcode = property["fields"]["mapLocation"]["parts"]["postcode"]
                    country = property["fields"]["mapLocation"]["parts"]["country"]
                    building_item["address"] = f'{number} {street}, {town} {postcode}, {country}'
                else:
                    building_item["address"] = property["fields"]["mapLocation"]["address"]
                    country = property["fields"]["mapLocation"]["address"].split(
                        ",")[-1]

                # lattitude and longitude
                longitude = property["fields"]["mapLocation"]["lng"]
                latitude = property["fields"]["mapLocation"]["lat"]
                if latitude:
                    building_item.update({
                        "latitude": float(latitude),
                        "longitude": float(longitude)
                    })
                    # country
                    building_item["country"] = get_country(
                        building_item["latitude"], building_item["longitude"])
                # else:
                #     building_item.update({
                #         "latitude": "n/a",
                #         "longitude": "n/a"
                #     })

                # offers
                offers = "n/a"
                if property["offerHero"]:
                    offer = property["offerHero"][0]["title"]
                    amount = [int(s) for s in offer.split() if s.isdigit()]
                    if amount and "discount" in offer.lower():
                        amount = amount[0]
                        offers = f'£{amount} discount'

                # if building_item["name"] == "Portsburgh Court":
                yield Request(url=building_item["url"], callback=self.parse_rooms, meta={
                    "building_item": building_item,
                    "year": year,
                    "offers": offers,
                    "building_id": building_id
                }, headers=self.headers)

    def parse_campus(self, res):
        city = res.meta["city"]
        if len(res.text) > 6:
            for campus in res.json():
                campus_item = CampusItem({
                    "name": campus["title"],
                    "institution": campus["title"],
                    "city": city["name"],
                    "latitude": float(campus["fields"]["mapLocation"]["lat"]),
                    "longitude": float(campus["fields"]["mapLocation"]["lng"]),
                    "address": campus["fields"]["mapLocation"]["address"],
                })
                yield campus_item

    def parse_rooms(self, res):
        building_id = res.meta["building_id"]
        building_item = res.meta["building_item"]
        current_year = res.meta["year"]
        offers = res.meta["offers"]

        expand__rooms = "descendants,heroImage,previewImage,hoverImage,backgroundImage,pageBuilder.grid.itemIcon,pageBuilder.images,pageBuilder.step.stepIcon,pageBuilder.linkBlock.linkImage,pageBuilder.award.itemImage,pageBuilder.faq,blogCategory,articleBuilder,articleBuilder.image,blogHeroImage,blogImage,carousel,landmarks,detailedFeatures.icon,kinetixRoom,accommodation,pageHero.backgroundImage,referAFriendContent.voucher,contactDetails,modalImage,clearingBannerCta,videoUrl,offer,semesterAccommodation,semesterAccommodation.accommodation,semesterAccommodation.accommodation.carousel,semesterAccommodation.accommodation.offer,socialLinks.socialIcon,roomsTenancies.icon,propertyHighlights.icon,propertyInfoBoxes.image,whatsHere,whatsHereOverview,roomDetails.icon,tenancyDetails.icon,featuredReview.image,thingsToDo,thingsToDoCarousel,transportCarousel,whatsOn,whatsOnCarousel,additionalInfo,additionalInfoCarousel,notice,noticeHero,noticeHero.noticeLink,whyChooseUs.stepIcon,whyChooseUs.stepSvg,notifications.icon,defaultAccommodation,accommodationOverride,accommodationOverride.heroImage,accommodationOverride.carousel,accommodationOverride.offer,accommodationOverride.offer.icon,accommodationOverride.offerHero,accommodationOverride.offerIcon,accommodationOverride.detailedFeatures.icon,accommodationOverride.notifications.icon,accommodationOverride.whatsHere,accommodationOverride.whatsHereOverview,roomOverride,brochure.pdf,copyList,propertyPageBuilder,propertyPageBuilder.events.media,propertyPageBuilder.image,offer.icon,offerHero,offerIcon,mapOverlay,locationFaq,locationFaq.faq,hubspotForms,steps.stepIcon,bookingJourney.assetImage,bookingJourney.listPlainText,badge"

        query_params = self.query_params.copy()
        query_params["filter[section]"] = "room"
        query_params["filter[relatedTo]"] = building_id
        query_params["filter[orderBy]"] = 'lft ASC'
        query_params["expand"] = expand__rooms

        # current academic year
        query_params["year"] = f'{current_year-1} - {current_year}'
        query_string = urllib.parse.urlencode(query_params)
        url_room__curent = f'https://www.studentroost.co.uk/api/entries?{query_string}'
        yield Request(url=url_room__curent, callback=self.parse_room_info, meta={"building_item": building_item, "year": current_year-1, "offers": offers}, headers=self.headers, dont_filter=True)

        # next academic year
        query_params["year"] = f'{current_year} - {current_year+1}'
        query_string = urllib.parse.urlencode(query_params)
        url_room__next = f'https://www.studentroost.co.uk/api/entries?{query_string}'
        yield Request(url=url_room__next, callback=self.parse_room_info, meta={"building_item": building_item, "year": current_year, "offers": offers}, headers=self.headers, dont_filter=True)

    def parse_room_info(self, res):
        building_item = res.meta["building_item"]
        year = res.meta["year"]
        offers = res.meta["offers"]

        if "-aub" not in building_item["url"]:

            for room in res.json():
                # if detail available for the academic year (query string is correct)
                if room["fields"]["priceFrom"] or room["fields"]["priceOverride"]:
                    # room name
                    room_name = room["title"]

                    # rent pw
                    rent_pw = float(room["fields"]["priceFrom"])
                    if not rent_pw:
                        rent_pw = float(room["fields"]["priceOverride"])

                    # room amenities
                    room_amenities = [detail["fields"]["featureTitle"]
                                      for detail in room["roomDetails"]]

                    # room description:
                    try:
                        room_description = room["tenancyDetails"][1]["fields"]["featureTitle"]
                    except IndexError:
                        room_description = room["roomDetails"][0]["fields"]["featureTitle"]

                    # tenancy description
                    tenancy_description = ", ".join(filter(
                        None, [element["fields"]["featureTitle"] for element in room["tenancyDetails"]]))

                    # room availability
                    if room["fields"]["roomAvailability"]:
                        rooms_available = int(
                            room["fields"]["roomAvailability"])
                    else:
                        rooms_available = 0

                    room_availability = (
                        "sold out" if rooms_available == 0 else "available")
                    # if rooms_available == 0:
                    #     room_availability = "sold out"
                    # else:
                    #     room_availability = "available"

                    # tenancy
                    tenancy = [s.replace("-", " ").replace(str(year), " ").replace(
                        str(year+1), " ") for s in tenancy_description.split(',') if "week" in s]
                    tenancy = [int(s) for s in " ".join(
                        tenancy).split(" ") if s.isdigit()]
                    if len(tenancy) == 0:
                        tenancy_description += ", 51-week tenancy assumed"
                        tenancy = [51]

                    for tenancy_week in tenancy:

                        room_item = RoomItem({
                            "building_name": building_item["name"],
                            "operator": building_item["operator"],
                            "description": room_description,
                            "amenities": room_amenities,
                            "name": room_name,
                            "url": building_item["url"],
                            "availability": room_availability,
                        })

                        # room type
                        room_item["type"] = get_room_type(room_item["name"])

                        contract_item = ContractItem({
                            "building_name": building_item["name"],
                            "room_name": room_item["name"],
                            "academic_year": f'{year}/{year + 1}',
                            "rent_pw": rent_pw,
                            "rent_pm": pw_to_pm(rent_pw),
                            "description": tenancy_description,
                            "offers": offers,
                            "tenancy_weeks": tenancy_week,
                            "tenancy_months": weeks_to_months(tenancy_week),
                            "url": building_item["url"],
                            "availability": room_availability,
                        })

                        # currency
                        contract_item["currency"] = get_currency(
                            building_item["country"])

                        # # room available
                        # room_item["availability"] = "available"

                        # rent total
                        contract_item["rent_total"] = rent_pw * tenancy_week

                        # tenancy_type
                        contract_item["tenancy_type"] = get_tenancy_type(
                            contract_item["tenancy_weeks"])

                        # combined_item
                        combined_item = CombinedItem()
                        combined_item_info = combine_items(
                            building_item, room_item, contract_item)
                        combined_item.update(combined_item_info)

                        if building_item["address"]:
                            yield room_item
                            yield building_item
                            yield combined_item
                            yield contract_item
