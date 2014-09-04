import copy
from operator import itemgetter


class ResultsTableTeam():

    def __init__(self, standings, driver_teams):
        self.table = []
        self.standings = standings
        self.driver_teams = driver_teams
        self.team_prev_position_map = {}

    def get_table(self):
        return self.table

    def get_team_position_map(self):
        result = {}
        for line in self.table:
            result[line["team"]] = line["position"]
        return result

    def set_team_prev_position_map(self, position_map):
        self.team_prev_position_map = position_map

    def process(self):

        # Calculate points for each team
        for team_name, driver_list in self.driver_teams.iteritems():

            # Process each driver on the team
            dropped_points = 0
            total_points = 0
            driver_rows = []
            for driver_name in driver_list:

                # Find the corresponding driver's row in the overall standings
                driver_row = None
                for row in self.standings.get_table():
                    if row["driver"] == driver_name:
                        driver_row = copy.deepcopy(row)

                # Handle the situation when the driver is not found is overall standings
                if driver_row is None:
                    driver_rows.append({
                        "driver": driver_name
                    })
                else:
                    # Driver position does not matter here, so let's remove it
                    del driver_row["position"]

                    # Update corresponding team points
                    dropped_points += driver_row["dropped_points"]
                    total_points += driver_row["total_points"]
                    driver_rows.append(driver_row)

            # Sort driver rows by driver name
            driver_rows = sorted(driver_rows, key=itemgetter("driver"))

            # Add team row into the table
            table_line = {
                "team": team_name,
                "driver_rows": driver_rows,
                "dropped_points": dropped_points,
                "total_points": total_points
            }

            self.table.append(table_line)

        # sort the table
        self.table = sorted(self.table, key=itemgetter("total_points"), reverse=True)

        # assign positions
        position = 1
        line_prev = None
        for line in self.table:
            if line_prev is None or line["total_points"] != line_prev["total_points"]:
                line["position"] = position
            else:
                line["position"] = line_prev["position"]
            line_prev = line
            position += 1

        # look up position of each team before the round and see how it got changed
        for line in self.table:
            if line["team"] in self.team_prev_position_map:
                pos_prev = self.team_prev_position_map[line["team"]]
                line["position_change"] = line["position"] - pos_prev
            else:
                line["position_change"] = ""
