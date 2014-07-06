import argparse
from points.config import Config
from webapp.auth import User


parser = argparse.ArgumentParser(description='Manages users for the admin web app')
parser.add_argument('command', nargs='?', help='Action to execute (add/delete/list/login)')
parser.add_argument('-u', '--username', help='Username')
parser.add_argument('-p', '--password', help='Password')

if __name__ == "__main__":
    args = vars(parser.parse_args())
    config = Config()

    # Display all users
    if args["command"] == "list":
        users = User.load_all(config)
        if users:
            print "Found %d users:" % len(users)
            for user in users:
                print "%s - %s" % (user['username'], user['password'])
        else:
            print "No users found"

    # Add a new user
    if args["command"] == "add":
        users = User.store_username_password(args['username'], args['password'], config)
        print "Added user %s to the database" % args['username']

    # Delete a user
    if args["command"] == "delete":
        users = User.remove_by_username(args['username'], config)
        print "Removed user %s from the database" % args['username']

    # Test login
    if args["command"] == "login":
        user = User.load_by_username_password(args['username'], args['password'], config)
        if user:
            print "Login successful with username '%s'!" % args['username']
        else:
            print "Login failed with username '%s'!" % args['username']
