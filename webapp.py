from operator import itemgetter
import re
from flask import Flask, request, render_template, redirect, url_for, abort, flash, jsonify
# noinspection PyUnresolvedReferences
from flask.ext.login import LoginManager, login_user
# noinspection PyUnresolvedReferences
from flask.ext.security import login_required
from points.config import Config
from points.round import Round
from points.session import Session
from webapp.auth import User
from Levenshtein import distance


app = Flask(__name__, static_folder='webapp/static', template_folder='webapp/templates')
app.config.from_envvar('WEBAPP_SETTINGS')

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

config = Config()


@login_manager.user_loader
def load_user(user_id):
    return User.load_by_id(user_id)


@app.route('/login', methods=['GET', 'POST'])
def login():
    # just display a login page
    if request.method == 'GET':
        return render_template('login.html')

    # get credentials
    username = request.form['username']
    password = request.form['password']

    # validate credentials and load user
    user_obj = User.load_by_username_password(username=username, password=password)
    if user_obj is None:
        flash('Username or Password is invalid', 'error')
        return redirect(url_for('login'))

    # log in user
    login_user(user_obj)
    flash('Logged in successfully')
    return redirect(request.args.get('next') or url_for('admin'))


@app.route('/admin')
@login_required
def admin():
    return redirect(url_for("admin_season", selected_season=config.get_current_season_year()))


@app.route('/admin_season/<int:selected_season>')
@login_required
def admin_season(selected_season):
    # Get and validate season
    seasons = config.get_all_seasons()
    if not selected_season in seasons:
        abort(404, "Season data not found")
    season_data = config.get_season_data(selected_season)

    # Find similar drivers
    results_table = season_data.get_results_for_class()
    d = sorted([row["driver"] for row in results_table.table])

    similar_drivers = []
    for i in xrange(len(d)):
        for j in xrange(i + 1, len(d)):
            dist = distance(d[i], d[j])
            if dist <= 4:
                similar_drivers.append({"name1": d[i], "name2": d[j], "distance": dist})
    similar_drivers = sorted(similar_drivers, key=itemgetter("distance"))

    driver_name_corrections = config.get_driver_name_corrections(selected_season)

    return render_template("admin.html", seasons=seasons, selected_season=selected_season, season_data=season_data,
                           similar_drivers=similar_drivers, driver_name_corrections=driver_name_corrections)


@app.route('/admin_round/<int:selected_season>', methods=['POST'])
@login_required
def admin_round(selected_season):
    # Get and validate season
    seasons = config.get_all_seasons()
    if not selected_season in seasons:
        abort(404, "Season data not found")
    season_data = config.get_season_data(selected_season)

    action = request.form['action']
    selected_round = int(request.form['round'])
    round_obj = Round(config, selected_season, selected_round)

    # This is when we want to download a round from mylaps by URL
    if action == 'download':
        mylaps_url = request.form['url']
        mylaps_id_match = re.search(r'\d+', mylaps_url)
        if not mylaps_id_match:
            abort(500, "Cannot parse event id from: " + mylaps_url)

        mylaps_id = mylaps_id_match.group()
        print "Downloading round #%s year %s: %s" % (selected_round, selected_season, round_obj.get_url(mylaps_id))
        result = round_obj.download(mylaps_id)

        if not result:
            return abort(500, "Cannot download round data from: " + round_obj.get_url(mylaps_id))

        round_obj.store_mylaps_id(mylaps_id)
        season_data.calc_and_store_points()
        return jsonify()

    # This is when we want to delete stored data for a round
    if action == 'delete':
        print "Deleting stored data for round #%s year %s" % (selected_round, selected_season)
        round_obj.delete_stored_data()
        season_data.calc_and_store_points()
        return jsonify()

    return None


@app.route('/admin_session_points/<int:selected_season>/<int:selected_round>', methods=['POST'])
@app.route('/admin_session_points/<int:selected_season>/<int:selected_round>/<session_name>',
           methods=['GET', 'POST'])
@login_required
def admin_session_points(selected_season, selected_round, session_name=None):
    # Get and validate season
    seasons = config.get_all_seasons()
    if not selected_season in seasons:
        abort(404, "Season data not found")
    season_data = config.get_season_data(selected_season)

    # Get parameters from POST call, if they are not passed through GET
    if not session_name:
        session_name = request.form['session_name']
    session_type, session_id = Session.parse_name_into_stype_sid(session_name)

    # Load objects
    round_obj = Round(config, selected_season, selected_round)
    session_obj = Session(config, round_obj, session_type, session_id)

    # Update session approval status
    if 'action' in request.form and request.form['action'] == 'set_approval_status':
        status = request.form['status'] == 'approved'

        print "Changing session approved status (%s, %s, %s) to %s" % (
            selected_season, selected_round, session_obj.get_name(), status)
        session_obj.store_approved_status(status)

        return jsonify()

    # Update driver points
    if 'action' in request.form and request.form['action'] == 'adjust_driver_position':
        driver_name = request.form['driver_name']
        move_type = request.form['move_type']
        positions = int(request.form['positions'])
        if move_type == 'up':
            positions = -positions

        session_obj.store_adjustment_of_driver_position(driver_name, positions)
        season_data.calc_and_store_points()

        return jsonify()

    if 'action' in request.form and request.form['action'] == 'clear_driver_adjustments':

        driver_name = request.form['driver_name']
        session_obj.clear_adjustments_for_driver(driver_name)
        season_data.calc_and_store_points()

        return jsonify()

    # Load session points and display the table
    session_obj.load_points()

    # Display standings for the session (with appropriate points)
    return render_template("admin_session_points.html", selected_season=selected_season,
                           selected_round=selected_round, round_obj=round_obj, session_obj=session_obj)


@app.route('/admin_round_points/<int:selected_season>/<int:selected_round>')
@login_required
def admin_round_points(selected_season, selected_round):
    # Get and validate season
    seasons = config.get_all_seasons()
    if not selected_season in seasons:
        abort(404, "Season data not found")

    round_obj = Round(config, selected_season, selected_round)
    round_obj.load_points()

    return render_template("admin_round_points.html", selected_season=selected_season,
                           selected_round=selected_round, round_obj=round_obj)


@app.route('/admin_driver_names/<int:selected_season>', methods=['POST'])
@login_required
def admin_driver_names(selected_season):
    # Get and validate season
    seasons = config.get_all_seasons()
    if not selected_season in seasons:
        abort(404, "Season data not found")
    season_data = config.get_season_data(selected_season)

    action = request.form['action']
    name_incorrect = request.form['name_incorrect'].strip()
    name_correct = request.form['name_correct'].strip()

    if not name_incorrect:
        return None

    if not name_correct:
        return None

    # This is when we want to download a round from mylaps by URL
    if action == 'add_correction':
        print "Adding driver name correction: '%s' -> '%s'" % (name_incorrect, name_correct)
        config.add_driver_name_correction(selected_season, name_incorrect, name_correct)
        season_data.calc_and_store_points()
        return jsonify()

    # This is when we want to delete stored data for a round
    if action == 'delete_correction':
        print "Deleting driver name correction: '%s' -> '%s'" % (name_incorrect, name_correct)
        config.delete_driver_name_correction(selected_season, name_incorrect, name_correct)
        season_data.calc_and_store_points()
        return jsonify()

    return None


@app.route('/season_overview/<int:selected_season>')
def season_overview(selected_season):
    # Get and validate season
    seasons = config.get_all_seasons()
    if not selected_season in seasons:
        abort(404, "Season data not found")
    season_data = config.get_season_data(selected_season)
    return render_template("main.html", seasons=seasons, selected_season=selected_season, season_data=season_data)


@app.route('/championship_table/<int:selected_season>/<driver_class>')
def championship_table(selected_season, driver_class):
    # Get and validate season
    seasons = config.get_all_seasons()
    if not selected_season in seasons:
        abort(404, "Season data not found")
    season_data = config.get_season_data(selected_season)

    # Get and driver class
    dclass = driver_class.split("_")[1]
    dclass = re.sub("[^A-Z]", "", dclass)

    # Get results table
    table = season_data.get_results_for_class(dclass)
    return render_template("championship.html", selected_season=selected_season, season_data=season_data, table=table,
                           dclass=dclass)


@app.route('/round_table/<int:selected_season>/<int:selected_round>')
def round_table(selected_season, selected_round):
    # Get and validate season
    seasons = config.get_all_seasons()
    if not selected_season in seasons:
        abort(404, "Season data not found")
    season_data = config.get_season_data(selected_season)

    table = season_data.get_results_for_class()
    table.strip_to_round(selected_round)

    return render_template("round.html", seasons=seasons, selected_season=selected_season,
                           selected_round=selected_round, season_data=season_data, table=table)


@app.route('/')
def main_page():
    return redirect(url_for("season_overview", selected_season=config.get_current_season_year()))


if __name__ == "__main__":
    # TODO: move to config
    app.run(host="0.0.0.0", port=4567, threaded=True)