import requests
#import json

from multicorn import ForeignDataWrapper
from multicorn.utils import log_to_postgres
from logging import ERROR, INFO, WARNING

API_URL = "https://tampere.fluentprogress.fi/KuntoTampere/v1/snowplow"


class ForeignDataWrapperError(Exception):

    def __init__(self, message):
        log_to_postgres(message, ERROR)


class MissingOptionError(ForeignDataWrapperError):

    def __init__(self, option):
        message = "Missing option '%s'" % option
        super(MissingOptionError, self).__init__(message)


class OptionTypeError(ForeignDataWrapperError):

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
        self.nrows = self.get_option("nrows")
        try:
            if self.key == "?history=":
                self.url = API_URL + "/" + self.machines + self.key + self.nrows
            else:
                self.url = API_URL + self.key
        except ValueError as e:
            self.log("Invalid url value {}".format(options.get("url", "")))
            raise e

    def execute(self, quals, columns):
        data = self.get_data(quals, columns)
        if self.key == "/mt" or self.key == "/op" or self.key == "/mo":
            for item in data:
                ret = {'id': item['id'], 'name': item['name']}
                yield ret
        elif self.key == "?history=":
            try:
                for item in data['location_history']:
                    ret = {}
                    try:
                        ret.update({'id': self.machines})
                    except KeyError:
                        self.log("Snowplow FDW: Invalid JSON content")
                        ret.update({'id': None})
                    try:
                        ret.update({'timestamp': item['timestamp']})
                    except KeyError:
                        self.log("Snowplow FDW: Invalid JSON content")
                        ret.update({'timestamp': None})
                    try:
                        ret.update({'coords': item['coords']})
                    except KeyError:
                        self.log("Snowplow FDW: Invalid JSON content")
                        ret.update({'coords': None})
                    try:
                        ret.update({'events': item['events']})
                    except KeyError:
                        self.log("Snowplow FDW: Invalid JSON content")
                        ret.update({'events': None})
                    # Jos kaikki data olisi olemassa APIssa
                    #ret = {'id': avain, 'timestamp': item['timestamp'], 'coords': item['coords'], 'events': item['events']}
                    yield ret
            except KeyError:
                self.log("Snowplow FDW: Invalid JSON content")
                ret = {'id': None, 'timestamp': None, 'coords': None, 'events': None}
                yield ret
        elif self.key == "":
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

    def get_data(self, quals, columns):
        if self.key == "?history=":
            url = API_URL + "/" + self.machines + self.key + self.nrows
        else:
            url = API_URL + self.key
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