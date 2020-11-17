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
    DATA: ""
    #DATA: "/mo"
    # location historiat (ilman last locationeita) idlle 45, jos luetaan kerran minuutissa
    #DATA: "/45?history=12"
    # id avaimilla, kerran minuutissa
    #DATA: "?history=12"
    # id avaimilla, kerran tunnissa
    #DATA: "?history=720"
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
        avain = self.machines
        if self.key == DATA:
            data = self.get_data(avain, quals, columns)
            # mt, op, mo
            # for item in data:
            # ret = {'id': item['id'], 'name': item['name']}
            # location historyt
            #try:
                #for item in data['location_history']:
                    #ret = {}
                    #try:
                        #ret.update({'id': avain})
                    #except KeyError:
                        #self.log("Snowplow FDW: Invalid JSON content")
                        #ret.update({'id': None})
                        #return []
                    #try:
                        #ret.update({'timestamp': item['timestamp']})
                    #except KeyError:
                        #self.log("Snowplow FDW: Invalid JSON content")
                        #ret.update({'timestamp': None})
                        #return []
                    #try:
                        #ret.update({'coords': item['coords']})
                    #except KeyError:
                        #self.log("Snowplow FDW: Invalid JSON content")
                        #ret.update({'coords': None})
                        #return []
                    #try:
                        #ret.update({'events': item['events']})
                    #except KeyError:
                        #self.log("Snowplow FDW: Invalid JSON content")
                        #ret.update({'events': None})
                        #return []
                    # Jos kaikki data olisi olemassa APIssa
                    #ret = {'id': avain, 'timestamp': item['timestamp'], 'coords': item['coords'], 'events': item['events']}
                    #yield ret
            #except KeyError:
                #self.log("Snowplow FDW: Invalid JSON content")
                #ret = {'id': None, 'timestamp': None, 'coords': None, 'events': None}
                #yield ret
                #return []
            # last information
            for item in data:
                ret = {}
                try:
                    ret.update({'id': item['id']})
                except KeyError:
                    self.log("Snowplow FDW: Invalid JSON content")
                    ret.update({'id': None})
                try:
                    ret.update({'machine_type': item['machine_type']})
                except KeyError:
                    self.log("Snowplow FDW: Invalid JSON content")
                    ret.update({'machine_type': None})
                try:
                    ret.update({'last_timestamp': item['last_location']['timestamp']})
                except KeyError:
                    self.log("Snowplow FDW: Invalid JSON content")
                    ret.update({'last_timestamp': None})
                try:
                    ret.update({'last_coords': item['last_location']['coords']})
                except KeyError:
                    self.log("Snowplow FDW: Invalid JSON content")
                    ret.update({'last_coords': None})
                try:
                    ret.update({'last_events': item['last_location']['events']})
                except KeyError:
                    self.log("Snowplow FDW: Invalid JSON content")
                    ret.update({'last_events': None})
                yield ret
                # Versio, jossa otetaan huomioon vain edellisen kuukauden alusta aktiivisena olleet ajoneuvot
                #date_time_obj = datetime.datetime.strptime(item['last_location']['timestamp'], '%Y-%m-%d %H:%M:%S')
                #todaype = pendulum.now()
                #lastmonth = todaype.subtract(months=1)
                #if date_time_obj.year == (datetime.datetime.today()).year and date_time_obj.month >= lastmonth.month:
                    #ret = {'id': item['id'], 'machine_type': item['machine_type'], 'last_timestamp': item['last_location']['timestamp'],
                           #'last_coords': item['last_location']['coords'], 'last_events': item['last_location']['events']}
                    #yield ret

    def get_data(self, avain, quals, columns):
        url = API_URL.format(self.url)
        #url = API_URL.format("/"+avain+(self.url))
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