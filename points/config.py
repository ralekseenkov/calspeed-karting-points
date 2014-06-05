import json
from season_data import SeasonData
from tinydb import TinyDB, where
from tinydb.storages import JSONStorage
from tinydb.middlewares import ConcurrencyMiddleware


class Config():
    def __init__(self):
        with open("conf/config.json", "rb") as json_file:
            self.data = json.load(json_file)
        self.db_connection = TinyDB(self.get_db_directory() + '/tinydb/db.json',
                                    storage=ConcurrencyMiddleware(JSONStorage))

    def get_db_connection(self):
        return self.db_connection

    def get_all_seasons(self):
        return sorted((c["season_year"] for c in self.data["super_series"]), reverse=True)

    def get_current_season_year(self):
        return max(e["season_year"] for e in self.data["super_series"])

    def get_db_directory(self):
        return self.data["db_directory"]

    def get_results_directory(self):
        return self.data["results_directory"]

    def get_mylaps_event_page_url_web(self):
        return self.data["mylaps_event_page_url_web"]

    def get_mylaps_event_page_url(self):
        return self.data["mylaps_event_page_url"]

    def get_mylaps_session_page_url(self):
        return self.data["mylaps_session_page_url"]

    def get_season_data(self, year):
        for season in self.data["super_series"]:
            if season["season_year"] == year:
                data = json.load(open(season["season_file"]))
                return SeasonData(data["season_data"], self, year)
        raise LookupError("Can't look up season data")

    def get_driver_name_corrections(self, year):
        corrections_table = self.get_db_connection().table('driver_name_corrections')
        return corrections_table.search(where('season') == year)

    def get_driver_name_corrections_as_dict(self, year):
        corrections_table = self.get_db_connection().table('driver_name_corrections')
        entries = corrections_table.search(where('season') == year)
        result = {}
        for c in entries:
            result[c['name_incorrect']] = c['name_correct']
        return result

    def add_driver_name_correction(self, year, name_incorrect, name_correct):
        corrections_table = self.get_db_connection().table('driver_name_corrections')
        corrections_table.insert(
            {
                'season': year,
                'name_incorrect': name_incorrect,
                'name_correct': name_correct
            }
        )

    def delete_driver_name_correction(self, year, name_incorrect, name_correct):
        corrections_table = self.get_db_connection().table('driver_name_corrections')
        corrections_table.remove(
            (where('season') == year) &
            (where('name_incorrect') == name_incorrect) &
            (where('name_correct') == name_correct)
        )
