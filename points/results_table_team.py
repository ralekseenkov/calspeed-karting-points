import copy
from operator import itemgetter


class ResultsTableTeam():

    def __init__(self, standings, driver_teams):
        self.table = []
        self.process(standings, driver_teams)

    def get_table(self):
        return self.table

    def process(self, standings, driver_teams):

        # Calculate points for each team
        for team_name, driver_list in driver_teams.iteritems():

            # Process each driver on the team
            dropped_points = 0
            total_points = 0
            driver_rows = []
            for driver_name in driver_list:

                # Find the corresponding driver's row in the overall standings
                driver_row = None
                for row in standings.get_table():
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
