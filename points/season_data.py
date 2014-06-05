import json
import os

from results_table import ResultsTable
from round import Round


class SeasonData():
    def __init__(self, data, config, year):
        self.data = data
        self.config = config
        self.year = year

    def get_rounds_list(self):
        rounds = []
        for round_num in xrange(self.get_total_rounds()):
            round_obj = Round(self.config, self.year, round_num + 1)
            rounds.append(round_obj)
        return rounds

    def get_rounds_completed(self):
        completed = 0
        for round_data in self.get_rounds_list():
            if round_data.exists():
                completed += 1
        return completed

    def get_total_rounds(self):
        return self.data["total_rounds"]

    def get_grop_rounds(self):
        return self.data["drop_rounds"]

    def is_score_points(self, ptype):
        return ptype in self.data

    def get_driver_points(self, ptype, pos_int):
        pos = str(pos_int)
        if not pos in self.data[ptype]:
            # Points are only awarded to top finishers ()
            return 0
        return self.data[ptype][pos]

    def get_driver_classes(self):
        return self.data["driver_classes"]

    def get_driver_teams(self):
        return self.data["driver_teams"]

    def get_directory(self):
        return self.config.get_results_directory() + "/" + str(self.year)

    def store_results_per_class(self, drivers, suffix=""):
        for dclass in self.get_driver_classes():
            # Filter out drivers which belong to this class
            table = ResultsTable(self.get_total_rounds(), self.get_grop_rounds())
            for driver in drivers:
                if dclass in driver.get_classes():
                    table.add_line(driver)
            table.process()

            # determine the directory
            dirname = self.get_directory()
            if not os.path.exists(dirname):
                os.makedirs(dirname)

            # determine the file
            fname = dirname + "/CLASS"
            if dclass:
                fname += "-" + dclass
            if suffix:
                fname += "-" + suffix
            fname += ".json"

            # store the table
            print "  [x] Saving results to '%s'" % fname
            with open(fname, "wb") as json_file:
                json.dump(table.get_table(), json_file, indent=4)

    def get_results_for_class(self, dclass=None):
        # Filter out drivers which belong to this class
        result = ResultsTable(self.get_total_rounds(), self.get_grop_rounds())

        # determine the directory
        dirname = self.get_directory()

        # determine the file
        fname = dirname + "/CLASS"
        if dclass:
            fname += "-" + dclass
        fname += ".json"

        # Read it
        if os.path.isfile(fname):
            result.set_table(json.load(open(fname)))
        return result

    def store_results_for_teams(self, drivers, suffix=""):
        table = ResultsTable(self.get_total_rounds(), self.get_grop_rounds())
        # table.process()
        return table

    def calc_and_store_points(self):
        # Read all rounds from JSON files
        rounds_json = []
        for round_num in xrange(self.get_total_rounds()):
            round_obj = Round(self.config, self.year, round_num + 1)
            if round_obj.exists():
                print "Reading round #%s: %s" % (round_num + 1, round_obj.get_directory())
                round_obj.read()
                rounds_json.append(round_obj)

        # Process each round/session and update driver points from CSV
        drivers_json = {}
        for round_obj in rounds_json:
            print "Processing round: %s" % round_obj.get_directory()
            round_obj.calc_points(drivers_json, self)
            round_obj.store_points()

        print "Points calculated (JSON), total number of drivers: %d" % len(drivers_json)

        # Construct table with results (JSON)
        self.store_results_per_class(drivers_json)
        self.store_results_for_teams(drivers_json)