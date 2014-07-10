import ujson as json
import os

from operator import itemgetter
from results_table import ResultsTable
from results_table_team import ResultsTableTeam
from round import Round
from tinydb import where


class SeasonData():
    def __init__(self, data, config, year):
        # Store season parameters
        self.data = data
        self.config = config
        self.year = year

        # Precreate the list of rounds
        self.rounds_list = []
        for round_num in xrange(self.get_total_rounds()):
            round_obj = Round(self.config, self.year, round_num + 1)
            self.rounds_list.append(round_obj)

    def get_rounds_list(self):
        return self.rounds_list

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

    def get_driver_teams(self):
        return self.data["driver_teams"]

    def is_score_points(self, ptype):
        return ptype in self.data

    def get_driver_classes(self):
        return self.data["driver_classes"]

    def get_driver_points(self, ptype, pos_int):
        pos = str(pos_int)
        if not pos in self.data[ptype]:
            # Points are only awarded to top finishers
            return 0
        return self.data[ptype][pos]

    def get_directory(self):
        return self.config.get_results_directory() + "/" + str(self.year)

    def count_approved_sessions(self):
        session_data_table = self.config.get_db_connection().table('session_data')
        results = session_data_table.search(
            (where('season') == self.year)
        )
        if not results:
            return 0
        return len(results)

    def count_total_sessions(self):
        rounds = self.get_rounds_list()
        result = 0
        for r in rounds:
            if r.exists():
                result += r.count_total_sessions()
        return result

    def is_approved(self):
        return self.count_approved_sessions() >= self.count_total_sessions()

    def get_results_for_class(self, dclass=None):
        # Filter out drivers which belong to this class
        result = ResultsTable(self.get_total_rounds(), self.get_grop_rounds(), self.get_rounds_list())

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

    def load_point_adjustments_flat(self):
        session_adjustments = self.config.get_db_connection().table('session_adjustments')
        list_of_adjustments = session_adjustments.search(
            (where('season') == self.year)
        )
        list_of_adjustments = sorted(list_of_adjustments, key=itemgetter("round", "session_name", "driver_name"))
        return list_of_adjustments

    def load_point_adjustments(self):
        session_adjustments = self.config.get_db_connection().table('session_adjustments')
        list_of_adjustments = session_adjustments.search(
            (where('season') == self.year)
        )
        result = {}
        for item in list_of_adjustments:
            if not item['driver_name'] in result:
                result[item['driver_name']] = []
            result[item['driver_name']].append(item)

        return result

    def calc_and_store_points(self):
        # Read all rounds from JSON files
        rounds_json = []
        for round_num in xrange(self.get_total_rounds()):
            round_obj = Round(self.config, self.year, round_num + 1)
            if round_obj.exists():
                print "Reading round #%s: %s" % (round_num + 1, round_obj.get_directory())
                round_obj.read()
                rounds_json.append(round_obj)

        # Process and store driver points for each individual round
        drivers = {}
        for round_obj in rounds_json:
            print "Processing round: %s" % round_obj.get_directory()
            round_obj.calc_points(drivers, self)
            round_obj.store_points()

        # Calculate and store results for each class
        standings = None
        for dclass in self.get_driver_classes():
            # Filter out drivers which belong to this class
            table = ResultsTable(self.get_total_rounds(), self.get_grop_rounds(), self.get_rounds_list())
            for driver in drivers:
                if dclass in driver.get_classes():
                    table.add_line(driver)
            table.process()

            # Store final standings
            if not dclass:
                standings = table

            # Determine the directory
            dirname = self.get_directory()
            if not os.path.exists(dirname):
                os.makedirs(dirname)

            # Determine the file
            fname = dirname + "/CLASS"
            if dclass:
                fname += "-" + dclass
            fname += ".json"

            # Store the table
            print "  [x] Saving results to '%s'" % fname
            with open(fname, "wb") as json_file:
                json.dump(table.get_table(), json_file)

        # Calculate and store results for teams
        table_team = ResultsTableTeam(standings, self.get_driver_teams())

        # Determine the directory
        fname = self.get_directory() + "/CLASS-TEAMS.json"

        # Store the table
        print "  [x] Saving results to '%s'" % fname
        with open(fname, "wb") as json_file:
            json.dump(table_team.get_table(), json_file)

        print "Points calculated, total number of drivers: %d" % len(drivers)
