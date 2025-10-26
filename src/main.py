#!/usr/local/bin/python

import os
import math
import shutil
import json
import sys
import sqlite3
import pytz
import datetime
from jinja2 import Template, FileSystemLoader, Environment

VERSION = 'dev'

def log_message(message):
    current_time_utc = datetime.datetime.now(datetime.timezone.utc)
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

    # Create the 'tasks' table if it doesn't exist
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            user_id INTEGER,
            year INTEGER,
            day INTEGER,
            task INTEGER,
            timestamp INTEGER
        )
    ''')

    # Commit changes and close connection
    conn.commit()
    conn.close()

def get_human_time_from_seconds(seconds):
    days = seconds // (24 * 3600)
    seconds %= (24 * 3600)
    hours = seconds // 3600
    seconds %= 3600
    minutes = seconds // 60
    seconds %= 60

    if days > 0:
        return f"{days}d {hours:02d}:{minutes:02d}:{seconds:02d}"
    else:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

def get_data_from_json_file(file_name):
    with open(file_name, 'r') as file:
        data = json.load(file)
    return data

def get_data_from_sqlite(db_file_name, sql_query, parameters=None):
    try:
        conn = sqlite3.connect(db_file_name)  # Connect to the SQLite database
        cursor = conn.cursor()

        if parameters:
            cursor.execute(sql_query, parameters)
        else:
            cursor.execute(sql_query)

        rows = cursor.fetchall()  # Fetch all rows

        conn.close()  # Close the connection

        return rows

    except sqlite3.Error as e:
        print(f"Error retrieving data: {e}")
        return None

def get_year_data(file_name, year):
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
                'score': row[4],
                'days': get_days_for_year_user_id(db_file_name, row[0], row[1]),
            }
            data_array.append(row_dict)

        # Close the connection
        conn.close()

        return data_array

    except sqlite3.Error as e:
        print(f"Error retrieving data: {e}")
        return None

def get_stats_data(file_name, year):

    stats_data = {}

    for day in  get_days_in_year(year):
        stats_data[day] = { "gold" : 0, "silver": 0, "total": 0}

    try:
        conn = sqlite3.connect(file_name)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT day, task FROM tasks
            WHERE year = ?
        ''', (year,))

        rows = cursor.fetchall()

        for row in rows:
            day = int(row[0])
            task = int(row[1])
            if task == 1:
                stats_data[day]['total'] += 1
            elif task == 2:
                stats_data[day]['gold'] += 1

        max_total_stars = 0
        for day in stats_data:
            stats_data[day]['silver'] = stats_data[day]['total'] - stats_data[day]['gold']
            if stats_data[day]['total'] > max_total_stars:
                max_total_stars = stats_data[day]['total']

        users_in_one_star = max(1, math.ceil(max_total_stars / 41))

        for day in stats_data:
            stats_data[day]['silver_for_graph'] = math.ceil(stats_data[day]['silver'] / users_in_one_star)
            stats_data[day]['gold_for_graph'] = math.ceil(stats_data[day]['gold'] / users_in_one_star)

        stats_data['users_in_one_star'] = users_in_one_star

        conn.close()

        return stats_data

    except sqlite3.Error as e:
        print(f"Error retrieving data: {e}")
        return None

def get_distinct_user_ids(file_name):
    try:
        conn = sqlite3.connect(file_name)  # Connect to the SQLite database
        cursor = conn.cursor()

        # SQL query to select distinct user_ids from the 'years' table
        cursor.execute('SELECT DISTINCT user_id FROM years')

        # Fetch all distinct user_ids and store them in an array
        distinct_user_ids = [row[0] for row in cursor.fetchall()]

        # Close the connection
        conn.close()

        return distinct_user_ids

    except sqlite3.Error as e:
        print(f"Error retrieving distinct user_ids: {e}")
        return None

def get_user_task_data(db_file_name, user_id):
    sql_query = '''
        SELECT timestamp, year, day, task
        FROM tasks
        WHERE user_id = ?
        ORDER BY timestamp
    '''
    parameters = (user_id,)

    rows = get_data_from_sqlite(db_file_name, sql_query, parameters)

    first_task_to_timestamp = {}

    if rows is not None:
        user_year_data = []
        for row in rows:
            row_dict = {
                'timestamp': row[0],
                'date_time_eastern_time_zone': get_date_time_eastern_time_zone(row[0]),
                'year': row[1],
                'day': row[2],
                'task': row[3]
            }

            key = str(row[1]) + "_" + str(row[2])
            if row[3] == 1:
                first_task_to_timestamp[key] = row[0]
            if row[3] == 2:
                row_dict['time_from_first_star'] = get_human_time_from_seconds(int(row[0]) - int(first_task_to_timestamp[key]))
            user_year_data.append(row_dict)
        return user_year_data
    else:
        return None

def get_days_for_year_user_id(db_file_name, year, user_id):
    conn = sqlite3.connect(db_file_name)
    cursor = conn.cursor()

    cursor.execute('''
        select day from tasks where user_id = ? and year = ?
    ''', (user_id, year))

    rows = cursor.fetchall()
    conn.close()

    array = [0] * len(get_days_in_year(year))

    for row in rows:
        array[row[0]-1] += 1

    return array

def get_user_year_data(db_file_name, user_id):
    try:
        conn = sqlite3.connect(db_file_name)  # Connect to the SQLite database
        cursor = conn.cursor()

        # SQL query to fetch data for a specific user ordered by year
        cursor.execute('''
            SELECT year, stars, score FROM years
            WHERE user_id = ?
            ORDER BY year
        ''', (user_id,))

        # Fetch all rows as a list of tuples
        rows = cursor.fetchall()

        # Store the fetched rows in a list of dictionaries
        user_year_data = []
        for row in rows:
            row_dict = {
                'year': row[0],
                'stars': row[1],
                'score': row[2],
                'days': get_days_for_year_user_id(db_file_name, row[0], user_id),
            }
            user_year_data.append(row_dict)

        # Close the connection
        conn.close()

        return user_year_data

    except sqlite3.Error as e:
        print(f"Error retrieving data: {e}")
        return None

def get_day_data(db_file_name, user_id2user_name, year, day, task):
    sql_query = '''
        SELECT timestamp, user_id
        FROM tasks
        WHERE year = ? AND day = ? AND task = ?
        ORDER BY timestamp
    '''
    parameters = (year, day, task)

    rows = get_data_from_sqlite(db_file_name, sql_query, parameters)

    if task == 2:
        user_id_to_timestamp_map = {}
        first_task_rows = get_data_from_sqlite(db_file_name, sql_query, (year, day, 1))
        for row in first_task_rows:
            user_id_to_timestamp_map[row[1]] = row[0]

    if rows is not None:
        user_year_data = []
        for row in rows:
            row_dict = {
                'timestamp': row[0],
                'date_time_eastern_time_zone': get_date_time_eastern_time_zone(row[0]),
                'user_id': row[1],
                'user_name': user_id2user_name[row[1]],
            }
            if task == 2:
                row_dict['time_from_first_star'] = get_human_time_from_seconds(int(row[0]) - int(user_id_to_timestamp_map[row[1]]))
            user_year_data.append(row_dict)
        return user_year_data
    else:
        return None

def get_day_combined_data(db_file_name, user_id2user_name, year, day):
    # First stars ordered by timestamp
    first_rows = get_data_from_sqlite(
        db_file_name,
        '''
            SELECT timestamp, user_id
            FROM tasks
            WHERE year = ? AND day = ? AND task = 1
            ORDER BY timestamp
        ''',
        (year, day)
    ) or []

    # Second stars mapped by user_id
    second_rows = get_data_from_sqlite(
        db_file_name,
        '''
            SELECT timestamp, user_id
            FROM tasks
            WHERE year = ? AND day = ? AND task = 2
        ''',
        (year, day)
    ) or []

    user_to_second_ts = {row[1]: row[0] for row in second_rows}

    combined = []
    for ts_first, user_id in first_rows:
        row = {
            'user_id': user_id,
            'user_name': user_id2user_name[user_id],
            'first_timestamp': ts_first,
            'first_date_time_eastern_time_zone': get_date_time_eastern_time_zone(ts_first),
            'second_timestamp': None,
            'second_date_time_eastern_time_zone': '',
            'time_from_first_star': '',
        }
        ts_second = user_to_second_ts.get(user_id)
        if ts_second is not None:
            row['second_timestamp'] = ts_second
            row['second_date_time_eastern_time_zone'] = get_date_time_eastern_time_zone(ts_second)
            row['time_from_first_star'] = get_human_time_from_seconds(int(ts_second) - int(ts_first))
        combined.append(row)
    return combined

def get_days_in_year(year):
    now = get_dt_now_eastern_time_zone()

    max_days = 13 if year >= 2025 else 26

    if now.year == year and now.month == 12:
        return list(range(1, min(now.day + 1, max_days)))
    else:
        return list(range(1, max_days))

def get_user_id_to_user_name_map(db_file_name):
    try:
        conn = sqlite3.connect(db_file_name)  # Connect to the SQLite database
        cursor = conn.cursor()

        # SQL query to get distinct user_id and corresponding user_name
        cursor.execute('''
            SELECT user_id, MIN(user_name) AS user_name
            FROM years
            GROUP BY user_id
        ''')

        # Fetch all rows as a list of tuples
        rows = cursor.fetchall()

        # Create a dictionary mapping user_id to user_name
        user_id_to_user_name_map = {user_id: user_name for user_id, user_name in rows}

        # Close the connection
        conn.close()

        return user_id_to_user_name_map

    except sqlite3.Error as e:
        print(f"Error retrieving data: {e}")
        return None

def get_date_time_eastern_time_zone(timestamp):

    dt = datetime.datetime.fromtimestamp(timestamp)

    et = pytz.timezone('US/Eastern')

    str = dt.astimezone(et).isoformat()
    str = str.replace('T', ' ')
    str = str.replace('-04:00', ' -04:00')
    str = str.replace('-05:00', ' -05:00')

    return str

def get_dt_now_eastern_time_zone():

    dt = datetime.datetime.now()

    et = pytz.timezone('US/Eastern')

    return dt.astimezone(et)

def get_users_totals(db_file_name):
    """
    Returns list of dicts: {user_id, user_name, total_stars}
    """
    rows = get_data_from_sqlite(
        db_file_name,
        '''
        SELECT user_id,
               MIN(user_name) AS user_name,
               SUM(stars)      AS total_stars
        FROM years
        GROUP BY user_id
        ORDER BY total_stars DESC, user_name ASC
        '''
    ) or []
    return [
        {'user_id': r[0], 'user_name': r[1], 'total_stars': r[2]}
        for r in rows
    ]

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

            for day_id in data['members'][user_id]['completion_day_level']:
                for task_id in data['members'][user_id]['completion_day_level'][day_id]:
                    ts = data['members'][user_id]['completion_day_level'][day_id][task_id]['get_star_ts']

                    cursor.execute('''
                        INSERT INTO tasks (user_id, year, day, task, timestamp)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (user_id, year, day_id, task_id, ts))

    conn.commit()
    conn.close()


    create_file_from_jinja('/app/src/index.jinja2', '/output/index.html', {'year':reversed_years[0]})

    data = {
        'reversed_years': reversed_years,
    }

    user_id2user_name = get_user_id_to_user_name_map(db_file_name)

    for year in years:
        log_message('Working on year ' + str(year))
        days = get_days_in_year(year)
        create_file_from_jinja('/app/src/year.jinja2', '/output/' + str(year) + '/index.html', {'current_year':year,'reversed_years':reversed_years, "year_data": get_year_data(db_file_name, year), 'days': days})
        create_file_from_jinja('/app/src/stats.jinja2', '/output/' + str(year) + '/stats/index.html', {'current_year':year,'reversed_years':reversed_years, 'days': days, 'stats_data':get_stats_data(db_file_name, year)})

        for day in days:
            create_file_from_jinja(
                '/app/src/day.jinja2',
                '/output/' + str(year) + '/' + str(day) + '/index.html',
                {
                    'current_year': year,
                    'current_day': day,
                    'reversed_years': reversed_years,
                    'days': days,
                    'day_combined_data': get_day_combined_data(db_file_name, user_id2user_name, year, day),
                }
            )

    log_message('Working on users')

    create_file_from_jinja(
        '/app/src/users.jinja2',
        '/output/users/index.html',
        {
            'reversed_years': reversed_years,
            'users': get_users_totals(db_file_name)
        }
    )

    for user_id in get_distinct_user_ids(db_file_name):
        create_file_from_jinja(
            '/app/src/user.jinja2',
            '/output/user/' + str(user_id) + '/index.html',
            {
                'reversed_years': reversed_years,
                'user_id': user_id,
                'user_name': user_id2user_name[user_id],
                'user_year_data': get_user_year_data(db_file_name, user_id),
                'user_task_data': get_user_task_data(db_file_name, user_id),
            })

    log_message('Finished')
