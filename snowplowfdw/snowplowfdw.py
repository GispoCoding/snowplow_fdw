import requests
import datetime
import pendulum
#import json

from multicorn import ForeignDataWrapper
from multicorn.utils import log_to_postgres
from logging import ERROR, INFO, WARNING

API_URL = "https://tampere.fluentprogress.fi/KuntoTampere/v1/snowplow{}"
DATA = "data"

VALID_URLS = {
    #DATA: "/mt"
    #DATA: "/op"
    #DATA: ""
    #DATA: "/mo"
    # location historiat (ilman last locationeita), jos luetaan kerran minuutissa
    #DATA: "/45?history=12"
    # id avaimilla
    DATA: "?history=12"
}

class ForeignDataWrapperError(Exception):

    def __init__(self, message):
        log_to_postgres(message, ERROR)

class MissingOptionError(ForeignDataWrapperError):
    """
    Required option missing from __init__ (e.g. GeoJSON FDW requires a url
    option).
    """

    def __init__(self, option):
        message = "Missing option '%s'" % option
        super(MissingOptionError, self).__init__(message)


class OptionTypeError(ForeignDataWrapperError):
    """
    Option has wrong type (e.g. SRID must be an integer).
    """

    def __init__(self, option, option_type):
        message = "Option %s is not of type %s" % (option, option_type)
        super(OptionTypeError, self).__init__(message)

class SnowplowForeignDataWrapper(ForeignDataWrapper):

    def __init__(self, options, columns):
        super(SnowplowForeignDataWrapper, self).__init__(options, columns)
        self.options = options
        self.columns = columns
        self.key = self.get_option("url")
        self.machines = self.get_option("machines")
        try:
            self.url = VALID_URLS.get(self.key)
        except ValueError as e:
            self.log("Invalid url value {}".format(options.get("url", "")))
            raise e

    def execute(self, quals, columns):
        #avain = (VALID_URLS.get(self.key)).split('?')[0]
        avain = self.machines
        if self.key == DATA:
            data = self.get_data(avain, quals, columns)
            # mt, op, mo
            # for item in data:
            # ret = {'id': item['id'], 'name': item['name']}
            for item in data["location_history"]:
                # tiettyyn idseen liittyva history
                ret = {'id': avain, 'timestamp': item['timestamp'], 'coords': item['coords'], 'events': item['events']}
                yield ret
            # last information
            #for item in data:
                #date_time_obj = datetime.datetime.strptime(item['last_location']['timestamp'], '%Y-%m-%d %H:%M:%S')
                #todaype = pendulum.now()
                #lastmonth = todaype.subtract(months=1)
                #if date_time_obj.year == (datetime.datetime.today()).year and date_time_obj.month >= lastmonth.month:
                    #ret = {'id': item['id'], 'machine_type': item['machine_type'], 'last_timestamp': item['last_location']['timestamp'],
                           #'last_coords': item['last_location']['coords'], 'last_events': item['last_location']['events']}
                    #yield ret

    def get_data(self, avain, quals, columns):
        #url = API_URL.format(self.url)
        url = API_URL.format("/"+avain+(self.url))
        return self.fetch(url)

    def fetch(self, url):
        self.log("URL is: {}".format(url), INFO)
        try:
            response = requests.get(url)
        except requests.exceptions.ConnectionError as e:
            self.log("Snowplow FDW: unable to connect to {}".format(url))
            return []
        except requests.exceptions.Timeout as e:
            self.log("Snowplow FDW: timeout connecting to {}".format(url))
            return []
        if response.ok:
            try:
                #return json.loads(response.content)
                return response.json()
            except ValueError as e:
                self.log("Snowplow FDW: invalid JSON")
                return []
        else:
            self.log("Snowplow FDW: server returned status code {} with text {} for url {}".format(response.status_code,
                                                                                              response.text, url))
            return []

    def get_option(self, option, required=True, default=None, option_type=str):
        if required and option not in self.options:
            raise MissingOptionError(option)
        value = self.options.get(option, default)
        if value is None:
            return None
        try:
            return option_type(value)
        except ValueError as e:
            raise OptionTypeError(option, option_type)

    def log(self, message, level=WARNING):
        log_to_postgres(message, level)