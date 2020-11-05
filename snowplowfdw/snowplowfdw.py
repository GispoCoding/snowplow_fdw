import json
from multicorn import ForeignDataWrapper, Qual
from logging import INFO
import requests

API_URL = "https://tampere.fluentprogress.fi/KuntoTampere/v1/snowplow/{}"
MACHINES="?"
MACHINE_TYPES="mt"

VALID_URLS = {
    # groups: "groups"
    MACHINES: "?",
    MACHINE_TYPES: "mt"
}


class SnowplowForeignDataWrapper(ForeignDataWrapper):

    def __init__(self, options, columns):
        super(SnowplowForeignDataWrapper, self).__init__(options, columns)
        self.key = self.get_option("url")
        #self.columns = columns
        #J self.category_type = self.get_option("category", required=False, default=VALID_CATEGORY_TYPES[REGION])
        #J self.srid = self.get_option("srid", required=False, default=3067, option_type=int)
        try:
            self.url = VALID_URLS.get(self.key)
        except ValueError as e:
            self.log("Invalid url value {}".format(options.get("url", "")))
            raise e

    #def execute(self, quals, columns):
        #for index in range(20):
            #line = {}
            #for column_name in self.columns:
                #line[column_name] = '%s %s' % (column_name, index)
                #line[column_name] = '%s' % ()
            #yield line

    def execute(self, quals, columns):
        if self.key == MACHINES:
            data = self.get_data(quals, columns)
            for item in data:
                ret = {'id': item['id'], 'machine_type': item['machine_type'], 'last_timestamp': item['last_location']['timestamp'],
                       'last_location': item['last_location']['coords'], 'last_event': item['last_location']['events']}
                yield ret
        elif self.key == MACHINE_TYPES:
            data = self.get_data(quals, columns)
            for item in data:
                ret = {'id': item['id'], 'name': item['name']}
                yield ret

    def get_data(self, quals, columns):
        url = API_URL.format(self.url)
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
                return json.loads(response.content)
            except ValueError as e:
                self.log("Snowplow FDW: invalid JSON")
                return []
        else:
            self.log("Snowplow FDW: server returned status code {} with text {} for url {}".format(response.status_code,
                                                                                              response.text, url))
            return []
