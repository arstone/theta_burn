import mysql.connector
from mysql.connector import Error
from dateutil.rrule import rrule, DAILY
from datetime import datetime
from holidays import UnitedStates
from dotenv import load_dotenv
import os

class credentials:
   db_host = None
   db_user = None
   db_password = None
   db_name = None
   
load_dotenv('../.env')

credentials.db_host = os.getenv('db_host')
credentials.db_user = os.getenv('db_user')
credentials.db_password = os.getenv('db_password')
credentials.db_name = os.getenv('db_name')

try:
    # Establish the connection
    connection = mysql.connector.connect(
        host=credentials.db_host,
        user=credentials.db_user,
        password=credentials.db_password,
        database=credentials.db_name
    )

    if connection.is_connected():
        cursor = connection.cursor()

        # Generate all dates from 2019 to 2050
        start_date = datetime(2019, 1, 1)
        end_date = datetime(2050, 12, 31)
        dates = list(rrule(DAILY, dtstart=start_date, until=end_date))

        # Check if each date is a US holiday
        us_holidays = UnitedStates(years=range(2019, 2051))

        for date in dates:
            is_holiday = date in us_holidays
            is_weekday = date.weekday() < 5  # 0-4 denotes Monday to Friday

            # Insert the date into the calendar table
            insert_query = """
            INSERT INTO calendar (date, year, quarter, month, month_name, 
                                  short_month_name, day, day_name, week, 
                                  weekday, is_weekday, is_holiday)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            record = (date, date.year, (date.month - 1) // 3 + 1, date.month, date.strftime('%B'),
                      date.strftime('%b'), date.day, date.strftime('%A'), date.strftime('%U'),
                      date.weekday(), is_weekday, is_holiday)
            cursor.execute(insert_query, record)

        # Commit the transaction
        connection.commit()

        print("Calendar table populated successfully")

except Error as e:
    print("Error while connecting to MariaDB", e)

finally:
    if connection.is_connected():
        cursor.close()
        connection.close()
        print("MariaDB connection is closed")