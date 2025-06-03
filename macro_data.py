import pandas as pd
import pymysql
import os
from dotenv import load_dotenv
load_dotenv()

def get_property_details(agreement_number):
    """
    Fetches property details from MySQL database for a specific agreement number.
    Returns project_name, house_address, house_number, apartment_number, agreement_price and agreement_date
    """
    try:
        connection = pymysql.connect(
            host=os.getenv('MYSQL_HOST'),
            port=int(os.getenv('MYSQL_PORT')),
            database=os.getenv('MYSQL_DATABASE'),
            user=os.getenv('MYSQL_USER'),
            password=os.getenv('MYSQL_PASSWORD')
        )

        with connection.cursor() as cursor:
            query = """
                SELECT 
                    c.complex_name AS project_name,
                    c.geo_street_name AS house_address,
                    c.geo_house AS house_number,
                    b.estate_rooms AS apartment_number,
                    a.deal_price AS agreement_price,
                    a.agreement_date AS agreement_date
                FROM (
                    SELECT 
                        d.estate_sell_id,
                        d.deal_price,
                        d.agreement_date
                    FROM estate_deals d
                    WHERE d.agreement_number = %s
                ) a
                LEFT JOIN (
                    SELECT 
                        es.estate_sell_id,
                        es.estate_rooms,
                        es.estate_floor,
                        es.estate_area,
                        es.house_id
                    FROM estate_sells es
                    WHERE es.deal_id IS NOT NULL
                ) b
                ON a.estate_sell_id = b.estate_sell_id
                LEFT JOIN (
                    SELECT 
                        h.id,
                        h.complex_name,
                        h.geo_city_name,
                        h.geo_street_name,
                        h.geo_house
                    FROM estate_houses h
                ) c
                ON b.house_id = c.id
            """
            cursor.execute(query, (agreement_number,))
            result = cursor.fetchone()
            
            if result:
                property_details = {
                    'project_name': result[0] or '',
                    'house_address': result[1] or '',
                    'house_number': result[2] or '',
                    'apartment_number': result[3] or '',
                    'agreement_price': result[4] or 0,
                    'agreement_date': pd.to_datetime(result[5]) or ''
                }
                return property_details
            else:
                return {
                    'project_name': '',
                    'house_address': '',
                    'house_number': '',
                    'apartment_number': '',
                    'agreement_price': 0,
                    'agreement_date': ''
                }

    except pymysql.MySQLError as e:
        print(f"Database error: {e}")
        return {
            'project_name': '',
            'house_address': '',
            'house_number': '',
            'apartment_number': '',
            'agreement_price': 0,
            'agreement_date': '',
            'error': str(e)
        }
    finally:
        if 'connection' in locals() and connection.open:
            connection.close()