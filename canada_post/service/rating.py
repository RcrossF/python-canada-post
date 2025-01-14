"""
GetRates Canada Post API
https://www.canadapost.ca/cpo/mc/business/productsservices/developers/services/rating/default.jsf
"""
import logging
from canada_post.service import ServiceBase, Service
from canada_post.errors import CanadaPostError
from lxml import etree
import requests

class GetRates(ServiceBase):
    URL = "https://{server}/rs/ship/price"
    headers = {'Accept': "application/vnd.cpc.ship.rate-v2+xml",
               'Content-type': "application/vnd.cpc.ship.rate-v2+xml",
               "Accept-language": "en-CA",
        }
    log = logging.getLogger('canada_post.service.rating.GetRates')

    def get_url(self):
        return self.URL.format(server=self.get_server())

    def __call__(self, parcel, origin, destination):
        """
        Call the GetRates service
        """
        self.log.info("Getting rates for parcel: %s, from %s to %s", parcel,
                      origin, destination)
        request_tree = etree.Element(
            'mailing-scenario', xmlns="http://www.canadapost.ca/ws/ship/rate-v2")
        def add_child(child_name, parent=request_tree):
            return etree.SubElement(parent, child_name)
        add_child("customer-number").text = str(self.auth.customer_number)
        if self.auth.contract_number:
            add_child("contract-id").text = str(self.auth.contract_number)

        # parcel characteristics
        par_chars = add_child("parcel-characteristics")
        add_child("weight", par_chars).text = str(parcel.weight)

        # par_chars/dimensions
        if all((parcel.length > 0, parcel.width > 0, parcel.height > 0)):
            dims = add_child("dimensions", par_chars)
            add_child("length", dims).text = str(parcel.length)
            add_child("width", dims).text = str(parcel.width)
            add_child("height", dims).text = str(parcel.height)

        add_child("origin-postal-code").text = origin.postal_code

        # destination
        dest = add_child("destination")
        if destination.country_code == "CA":
            doms = add_child("domestic", dest)
            add_child("postal-code", doms).text = destination.postal_code
        elif destination.country_code == "US":
            us = add_child("united-states", dest)
            add_child("zip-code", us).text = destination.postal_code
        else:
            # international shipping
            intr = add_child("international", dest)
            add_child("country-code", intr).text = destination.country_code

        url = self.get_url()
        self.log.info("Using url %s", url)
        request = etree.tostring(request_tree, pretty_print=self.auth.debug).decode('utf-8')
        self.log.debug("Request xml: %s", request)
        response = requests.post(url, data=request, headers=self.headers,
                                 auth=self.userpass())
        self.log.info("Request returned with status %s", response.status_code)
        self.log.debug("Request returned content: %s", response.content)
        if not response.ok:
            restree = etree.XML(response.content.decode('utf-8').replace(' xmlns="',
                                                         ' xmlnamespace="'))
            error_code = restree.find(".//code").text
            if error_code.isdigit():
                error_code = int(error_code)
            message = restree.find(".//description").text

            raise CanadaPostError(error_code, message)

        # this is a hack to remove the namespace from the response, since this
        #breaks xpath lookup in lxml
        restree = etree.XML(response.content.decode('utf-8').replace(' xmlns="',
                                                     ' xmlnamespace="').encode('utf-8'))
        services = [Service(xml_subtree=price)
                    for price in restree.findall("price-quote")]

        return services
