import requests
import re

from multicorn import ForeignDataWrapper
from multicorn.utils import log_to_postgres
from logging import ERROR, INFO, WARNING


class ForeignDataWrapperError(Exception):

    def __init__(self, message):
        log_to_postgres(message, ERROR)


class MissingOptionError(ForeignDataWrapperError):

    def __init__(self, option):
        message = f"Missing option {option}"
        super(MissingOptionError, self).__init__(message)


class OptionTypeError(ForeignDataWrapperError):

    def __init__(self, option, option_type):
        message = f"Option {option} is not of type {option_type}"
        super(OptionTypeError, self).__init__(message)


class SnowplowForeignDataWrapper(ForeignDataWrapper):

    def __init__(self, options, columns):
        super(SnowplowForeignDataWrapper, self).__init__(options, columns)
        self.options = options
        self.columns = columns
        self.urlop = self.get_option("url")
        try:
            self.url = self.urlop
        except ValueError as e:
            self.log("Invalid url value {}".format(options.get("url", "")))
            raise e

    def execute(self, quals, columns):
        data = self.get_data(quals, columns)
        if "/mt" in self.urlop or "/op" in self.urlop or "/mo" in self.urlop:
            for item in data:
                ret = {'id': item['id'], 'name': item['name']}
                yield ret
        elif "history" in self.urlop:
            try:
                for item in data['location_history']:
                    ret = {}
                    try:
                        result = re.search('snowplow/(.*)\\?history', self.urlop)
                        self.machines = result.group(1)
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
                    #ret = {'id': self.machines, 'timestamp': item['timestamp'], 'coords': item['coords'], 'events': item['events']}
                    yield ret
            except KeyError:
                self.log("Snowplow FDW: Invalid JSON content")
                ret = {'id': None, 'timestamp': None, 'coords': None, 'events': None}
                yield ret
        else:
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
        url = self.urlop
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