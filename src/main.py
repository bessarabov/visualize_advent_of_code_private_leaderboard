#!/usr/local/bin/python

import os
import shutil
import json
import sqlite3
from datetime import datetime, timezone
from jinja2 import Template, FileSystemLoader, Environment

VERSION = 'dev'

def log_message(message):
    current_time_utc = datetime.now(timezone.utc)
    timestamp_iso8601 = current_time_utc.replace(microsecond=0, tzinfo=None).isoformat() + 'Z'
    print(f"{timestamp_iso8601} {message}")

def create_file_from_jinja(jinja_file_name, output_file_name, data):

    output_directory = os.path.dirname(output_file_name)
    if output_directory and not os.path.exists(output_directory):
        os.makedirs(output_directory)

    # Get the directory of the Jinja2 template file
    jinja_dir = os.path.dirname(os.path.abspath(jinja_file_name))

    # Create a Jinja2 Environment and load the template from the specified file
    env = Environment(loader=FileSystemLoader(jinja_dir))
    template = env.get_template(os.path.basename(jinja_file_name))

    # Render the template with the provided data
    output_text = template.render(data)

    # Write the rendered output to the output file
    with open(output_file_name, 'w') as output_file:
        output_file.write(output_text)

def copy_all_files_from_to(from_dir, to_dir):
    # Ensure 'to_dir' exists or create it if not
    if not os.path.exists(to_dir):
        os.makedirs(to_dir)

    # Get all files and directories in 'from_dir'
    files_to_copy = os.listdir(from_dir)

    # Iterate through each file/directory and copy it to 'to_dir'
    for file_or_dir in files_to_copy:
        source = os.path.join(from_dir, file_or_dir)
        destination = os.path.join(to_dir, file_or_dir)

        if os.path.isdir(source):
            # If it's a directory, copy recursively
            shutil.copytree(source, destination)
        else:
            # If it's a file, copy it directly
            shutil.copy2(source, destination)

def get_years_from_files(directory):
    years = []
    for filename in os.listdir(directory):
        if filename.endswith('.json'):
            file_year = filename.split('.')[0]
            try:
                year = int(file_year)
                years.append(year)
            except ValueError:
                pass
    years.sort()
    return years

def create_sqlite3_tables(file_name):
    # Connect to SQLite database (creates one if it doesn't exist)
    conn = sqlite3.connect(file_name)
    cursor = conn.cursor()

    # Create the 'years' table if it doesn't exist
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS years (
            year INTEGER,
            user_id INTEGER,
            user_name TEXT,
            stars INTEGER,
            score INTEGER
        )
    ''')

    # Commit changes and close connection
    conn.commit()
    conn.close()

def get_data_from_json_file(file_name):
    with open(file_name, 'r') as file:
        data = json.load(file)
    return data

def get_data_as_array_of_dicts(file_name, year):
    try:
        conn = sqlite3.connect(file_name)  # Connect to the SQLite database
        cursor = conn.cursor()

        # SQL query to fetch data for a specific year ordered by score in descending order
        cursor.execute('''
            SELECT * FROM years
            WHERE year = ?
            ORDER BY score DESC
        ''', (year,))

        # Fetch all rows as a list of tuples
        rows = cursor.fetchall()

        # Store the fetched rows in an array of dictionaries
        data_array = []
        for row in rows:
            row_dict = {
                'year': row[0],
                'user_id': row[1],
                'user_name': row[2],
                'stars': row[3],
                'score': row[4]
            }
            data_array.append(row_dict)

        # Close the connection
        conn.close()

        return data_array

    except sqlite3.Error as e:
        print(f"Error retrieving data: {e}")
        return None

if __name__ == '__main__':
    log_message('Started visualize_advent_of_code_private_leaderboard:' + VERSION)

    copy_all_files_from_to('/app/src/static/', '/output/static/')

    years = get_years_from_files('/input/')
    reversed_years = list(reversed(years))


    db_file_name = '/output/db.db'
    create_sqlite3_tables(db_file_name)


    conn = sqlite3.connect(db_file_name)
    cursor = conn.cursor()

    for year in years:
        data = get_data_from_json_file('/input/' + str(year) + '.json')
        for user_id in data['members']:

            user_name = data['members'][user_id]['name']
            if user_name == None:
                user_name = "(anonymous user #" + user_id + ")"
            stars = data['members'][user_id]['stars']
            score = data['members'][user_id]['local_score']

            cursor.execute('''
                INSERT INTO years (year, user_id, user_name, stars, score)
                VALUES (?, ?, ?, ?, ?)
            ''', (year, user_id, user_name, stars, score))

    conn.commit()
    conn.close()


    create_file_from_jinja('/app/src/index.jinja2', '/output/index.html', {'year':reversed_years[0]})

    data = {
        'reversed_years': reversed_years,
    }

    for year in years:
        create_file_from_jinja('/app/src/year.jinja2', '/output/' + str(year) + '/index.html', {'current_year':year,'reversed_years':reversed_years, "year_data": get_data_as_array_of_dicts(db_file_name, year)})
