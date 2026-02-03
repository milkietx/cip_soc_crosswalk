## helpers for cip to soc project
import sys
import pandas as pd
import os
import requests
import sqlite3

#%%helpers for the download data file
def create_cursor(spath):
    conn = sqlite3.connect(spath)
    conn.enable_load_extension(True)
    conn.execute('SELECT load_extension("mod_spatialite")')
    crsr = conn.cursor()
    return crsr

def create_conn(spath):
    conn = sqlite3.connect(spath)
    conn.enable_load_extension(True)
    conn.execute('SELECT load_extension("mod_spatialite")')
    return conn

def read_in_cip_soc() -> pd.core.frame.DataFrame:
    #this is drawn from the nces website
    cs = pd.read_excel(r"https://nces.ed.gov/ipeds/cipcode/Files/CIP2020_SOC2018_Crosswalk.xlsx",
                       sheet_name="CIP-SOC")
    return cs

def process_cip_soc(cs) -> pd.core.frame.DataFrame:
    #lets process cip to be ##.#### with trailing zeros for consistency
    #split along the decimal
    #first part of decimal - make sure its 2 digits with leading 0
    #second part of decimal - make sure its 4 digits with trailing 0
    cs["cip_join_key"] = cs['CIP2020Code'].astype(str).apply(lambda x: f"{x.split('.')[0].zfill(2)}.{x.split('.')[1].ljust(4,'0')}")
    return cs

def read_in_thecb(fp=r"C:\Users\cmg0530\Projects\cip_soc_crosswalk\Data Downloads\THECB") -> dict:
    #this is drawn from a series of downloads located here, but pulled from thecb site
    #source location = https://www.txhigheredaccountability.org/AcctPublic/InteractiveReport/AddReport
    
    #list all files
    all_files = os.listdir(fp)
    files = [y for y in all_files if y.endswith("csv")]
    
    #read into a dictionary named by filename
    f_dict = {}
    for z in files:
        try:
            print(f"reading in {z}")
            f = pd.read_csv(os.path.join(fp,z),header=1,encoding='ISO-8859-1')
            f_dict[z.split(".csv")[0]] = f
        except:
            print(f"couldn't read {z}")
    print("returning dict")
    return f_dict

def process_thecb(thecb_dict) -> pd.core.frame.DataFrame:

    #make one big dataframe
    bf = pd.DataFrame()
    for q in thecb_dict.keys():
        z = thecb_dict[q]
        z['table_name'] = q
        bf = pd.concat([bf,z])

    #process cip 
    #cip should be in format ##.#### with trailing zeros
    bf["cip_join_key"] = bf['CIPDesc'].apply(lambda x: x.split(" -")[0])
    bf["cip_join_key"] = bf['cip_join_key'].apply(lambda x: f"{x[:2]}.{x[2:6]}".ljust(7, '0'))

    #to add - processing name of institution to a geographic code (tbd which one)
    return bf  

def map_programs_to_schools(con):
    crsr = con.cursor()
    crsr.execute("DROP TABLE IF EXISTS join_program_occupations")
    crsr.execute("""CREATE TABLE 
                 join_program_occupations
                 AS 
                 select 
                    thecb.cip_join_key as cip_join_key,
                    thecb.dimyear as year,
                    thecb.levelgroupdesc as institution_type,
                    thecb.instlist as institution,
                    thecb.cipdesc as cip_description,
                    thecb.count as grad_count,
                    cip.soc2018code as soc_code,
                    cip.soc2018title as soc_title  FROM
          (SELECT * FROM ref_thecb_data) as thecb
          left join
          (SELECT * FROM ref_cip_soc_nces) as cip
          on thecb.cip_join_key = cip.cip_join_key""")
    con.commit()

def upload_to_sqlite(
    crsr, con, df, table_name="test__", schema="dbo", drop=True, chunk_print_size=50
):
    """
    chunk_print_size = number of rows to print count when uploading
    """

    pd.options.mode.chained_assignment = None

    print("Writing DataFrame into sql table.")
    print(f"Table name: {schema}_{table_name}")

    # rename columns
    df.columns = [
        y.replace(" ", "_").replace(":", "").replace("(", "").replace(")", "").lower()
        for y in df.columns
    ]

    # default all to varchars
    columns = df.columns.tolist()
    format_columns = [f"{x} TEXT" for x in columns]

    # adjust formatting
    for x in columns:
        df[x] = df[x].astype(str)
        # adjust datetime
        if x in df.select_dtypes(include=["datetime64[ns, UTC]"]).columns.tolist():
            df[x] = df[x].dt.strftime("%Y-%m-%d")
        df[x] = df[x].str.replace(',', ' ')

    # if the drop parameter is True, then drop the existing table
    if drop == True:
        try:
            print("Trying to drop old table.")
            crsr.execute(
                f"""DROP TABLE IF EXISTS {schema}_{table_name};""")
            con.commit()
            print("Dropped!")
        except Exception as e:
            print("No existing table to drop.")
            print(f"Exception: {e}")

        try:
            print("Creating new sql table...")
            crsr.execute(
                fr"""CREATE TABLE IF NOT EXISTS {schema}_{table_name}(
                {",".join(format_columns)});""")
            con.commit()
            print("Done.")
        except Exception as e:
            print("Could not create new table.")
            print(f"Exception: {e}")

    print(f"Writing in {len(df)} rows.")

    print("Uploading...")
    for index, row in df.reset_index().iterrows():
        try:
            if index % chunk_print_size == 0:
                print(f"{index} out of {len(df)}")
            crsr.execute(
                f"""INSERT INTO {schema}_{table_name}
            ({",".join(columns)}) values ({",".join(["?"] * len(columns))})""",
                [x.replace(","," ") for x in row[1:].tolist()],
            )
        except Exception as e:
            print(f"Could not upload {index}")
            print(f"Exception: {e}")

    con.commit()
    print("Done!")

def make_table_spatial(crsr, con, geometry_type=None, wkt_col='geom_wkt',geometry_column='geometry',
                       srid='3857',
                       table_name="test__", schema="dbo"):
    """
    chunk_print_size = number of rows to print count when uploading
    """

    print(f"Table name: {schema}_{table_name}")
    print(f"Making it spatial on column {wkt_col}")

    #initalize if not already
    crsr = con.cursor()
    crsr.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='spatial_ref_sys'")
    if crsr.fetchone()[0] == 0:
        crsr.execute("SELECT InitSpatialMetadata(1)")

    #detect geometry type
    if geometry_type is None:
        crsr.execute(f"SELECT {wkt_col} FROM {schema}_{table_name} WHERE {wkt_col} IS NOT NULL LIMIT 1")
        sample_wkt = crsr.fetchone()
        if sample_wkt:
            wkt_text = sample_wkt[0]
            geometry_type = wkt_text.split('(')[0].strip().upper()
            print(f"Auto-detected geometry type: {geometry_type}")
        else:
            raise ValueError("Cannot auto-detect geometry type - no non-null WKT values found")
    
    # Add geometry column
    try:
        crsr.execute(f"SELECT AddGeometryColumn('{schema}_{table_name}', '{geometry_column}', {srid}, '{geometry_type}', 'XY')")
        con.commit()
        print(f"Added geometry column '{geometry_column}' to table '{schema}_{table_name}'")
    except sqlite3.OperationalError as e:
        if "already exists" in str(e).lower():
            print(f"Geometry column '{geometry_column}' already exists")
        else:
            raise
    
    # Convert WKT to geometry
    print(f"Converting WKT data to geometry...")
    
    update_query = f"""
        UPDATE {schema}_{table_name}
        SET {geometry_column} = GeomFromText({wkt_col}, {srid})
        WHERE {wkt_col} IS NOT NULL
        """
    crsr.execute(update_query)
    rows_updated = crsr.rowcount
    con.commit()
    print(f"Successfully converted {rows_updated} rows")
    
    # Create spatial index
    print(f"Creating spatial index...")
    try:
        crsr.execute(f"SELECT CreateSpatialIndex('{table_name}', '{geometry_column}')")
        con.commit()
        print(f"Spatial index created on '{geometry_column}'")
    except sqlite3.OperationalError as e:
        print(f"Note: Could not create spatial index - {e}")


#%% spatial helpers with google maps

def google_maps_geocode(address: str) -> tuple:
    base_url = "https://maps.googleapis.com/maps/api/geocode/json"
    api_key = "AIzaSyBOpbFJiufMf58LGcy9uJVGOXmuOpGERkg"
    params = {
        'address': address,
        'key': api_key
    }

    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status()
        
        data = response.json()
        
        if data['status'] == 'OK':
            location = data['results'][0]['geometry']['location']
            return location['lat'], location['lng'], 'OK'
        else:
            return None, None, data['status']
            
    except requests.exceptions.RequestException as e:
        return None, None, f'REQUEST_ERROR: {str(e)}'
    except (KeyError, IndexError) as e:
        return None, None, f'PARSE_ERROR: {str(e)}'
    

#%% spatial helpers
def geocode(street_address,city,state,zipcode):
    #using a&m api service
    api_key = "437826a6a5eb4eb499eecf01560e583d"
    api_url = "https://geoservices.tamu.edu/Api/Geocode/V5/"
    print(f"{street_address} {city} {state} {zipcode}")
   
    payload = {'apiKey': api_key, 
                'version':'5.0.0',
                'format':'json',
                'streetAddress':street_address,#should be like 4221 Cole Ave
                'city':city,
                'state':state,
                'zip':zipcode,
                'notStore':'true'} # Example parameters
    
    response = requests.get(api_url, params=payload)

    try:
        if response.status_code == 200:
            print("Success")
        lat = response.json()['data']['results'][0]['latitude']
        lon = response.json()['data']['results'][0]['longitude']
    except:
        print("Could not geocode")
        lat = None
        lon = None
    z = (lat,lon)
    return z

def parse_address_thecb(sd) -> dict:
    parsed_dict = {}
    for _,x in sd.iterrows():
        parsed_dict[x['Institution Name']] = {'streetAddress': x['Address'],
                                              'City':x['City'],
                                              'Zip Code':x['Zip Code'],
                                              'State':'Texas'}
    return parsed_dict

def geocode_thecb_addresses(parsed_dict) -> dict:
    geocodes = {}
    for key in parsed_dict.keys():
        lat_lng = geocode(street_address=parsed_dict[key]['streetAddress'],
                city=parsed_dict[key]['City'],
                state=parsed_dict[key]['State'],
                zipcode=parsed_dict[key]['Zip Code'])
        geocodes[key] = lat_lng
    return geocodes

def clean_up(geocodes,parsed_dict)->dict:
    #get those that have no matches and fix the addresses using the parsed dict
    checks = []
    for q in geocodes_v2.keys():
        if geocodes_v2[q] == (0,0):
            checks.append(q)
    revised_parsed_dict = {}
    for q in checks:
        revised_parsed_dict[q] = f_parsed_dict[q]
    #manual edit
    f_parsed_dict = {'nan': {'streetAddress': 'nan', 'City': 'nan', 'Zip Code': 'nan', 'State': 'Texas'},
 'Abilene Christian University': {'streetAddress': ' 1600 Campus Ct',
  'City': 'Abilene',
  'Zip Code': '79601',
  'State': 'Texas'},
 'Amarillo College': {'streetAddress': '2201 S Washington St',
  'City': 'Amarillo',
  'Zip Code': '79109',
  'State': 'Texas'},
 'Baylor University': {'streetAddress': '1311 S 5th St',
  'City': 'Waco',
  'Zip Code': '76706',
  'State': 'Texas'},
 'College of Biblical Studies': {'streetAddress': '7000 Regency Square Blvd',
  'City': 'Houston',
  'Zip Code': '77036',
  'State': 'Texas'},
 'Dallas College Brookhaven Campus': {'streetAddress': '3939 Valley View Lane',
  'City': 'Farmers Branch',
  'Zip Code': '75244-4906',
  'State': 'Texas'},
 'East Texas Baptist University': {'streetAddress': '1 Tiger Drive',
  'City': 'Marshall',
  'Zip Code': '75670',
  'State': 'Texas'},
 'El Paso Community College District': {'streetAddress': '100 W Rio Grande Ave',
  'City': 'El Paso',
  'Zip Code': '79902',
  'State': 'Texas'},
 'Frank Phillips College': {'streetAddress': '1301 Roosevelt St',
  'City': 'Borger',
  'Zip Code': '79007',
  'State': 'Texas'},
 'Hardin-Simmons University': {'streetAddress': '2200 Hickory St',
  'City': 'Abilene',
  'Zip Code': '79601',
  'State': 'Texas'},
 'Houston City College - Northeast Campus': {'streetAddress': '555 Community College Dr',
  'City': 'Houston',
  'Zip Code': '77013',
  'State': 'Texas'},
 'Jarvis Christian University': {'streetAddress': '80 Private Road 7631',
  'City': 'Hawkins',
  'Zip Code': '75765',
  'State': 'Texas'},
 'Lamar University': {'streetAddress': '4400 Martin L King Pkwy',
  'City': 'Beaumont',
  'Zip Code': '77705',
  'State': 'Texas'},
 'Laredo College': {'streetAddress': '1947 Lamar Rd',
  'City': 'Laredo',
  'Zip Code': '78040-4395',
  'State': 'Texas'},
 'Lone Star College - University Park': {'streetAddress': '20515 TX-249 S',
  'City': 'Houston',
  'Zip Code': '77070',
  'State': 'Texas'},
 'Northeast Texas Community College': {'streetAddress': '2886 FM 1735',
  'City': 'Mount Pleasant',
  'Zip Code': '75455',
  'State': 'Texas'},
 'Prairie View A&M University': {'streetAddress': '100 University Dr',
  'City': 'Prairie View',
  'Zip Code': '77446',
  'State': 'Texas'},
 'Sam Houston State University College of Osteopathic Medicine': {'streetAddress': '925 City Central Ave',
  'City': 'Conroe',
  'Zip Code': '77304',
  'State': 'Texas'},
 'SHSU Polytechnic College': {'streetAddress': 'nan',
  'City': 'nan',
  'Zip Code': 'nan',
  'State': 'Texas'},
 'Southwestern Christian College': {'streetAddress': '200 Bowser Cir',
  'City': 'Terrell',
  'Zip Code': '75160',
  'State': 'Texas'},
 'Sul Ross State University': {'streetAddress': '300 Centennial Dr',
  'City': 'Alpine',
  'Zip Code': '79830',
  'State': 'Texas'},
 'Sul Ross State University Rio Grande College': {'streetAddress': '3107 Bob Rogers Dr',
  'City': 'Eagle Pass',
  'Zip Code': '78852',
  'State': 'Texas'},
 'Texas A&M Health Science Center': {'streetAddress': '8441 John Sharp Pkwy',
  'City': 'Bryan',
  'Zip Code': '77807',
  'State': 'Texas'},
 'Texas A&M University': {'streetAddress': '400 Bizzell St',
  'City': 'College Station',
  'Zip Code': '77840',
  'State': 'Texas'},
 'Texas A&M University at Galveston': {'streetAddress': '200 Seawolf Pkwy',
  'City': 'Galveston',
  'Zip Code': '77554',
  'State': 'Texas'},
 'Texas Southmost College': {'streetAddress': '80 Ft Brown St',
  'City': 'Brownsville',
  'Zip Code': '78520',
  'State': 'Texas'},
 'Texas State Technical College-CONNECT': {'streetAddress': 'nan',
  'City': 'nan',
  'Zip Code': 'nan',
  'State': 'Texas'},
 'Texas State Technical College-East Williamson': {'streetAddress': '1600 Innovation Blvd',
  'City': 'Hutto',
  'Zip Code': '78634',
  'State': 'Texas'},
 'Texas State Technical College-Harlingen': {'streetAddress': '21 Ash St',
  'City': 'Harlingen',
  'Zip Code': '78550-3697',
  'State': 'Texas'},
 'Texas State Technical College-Marshall': {'streetAddress': '2650 E End Blvd S',
  'City': 'Marshall',
  'Zip Code': '75672',
  'State': 'Texas'},
 'Texas Tech University SCHOOL of Veterinary Medicine': {'streetAddress': '7671 Evans Dr',
  'City': 'Amarillo',
  'Zip Code': '79106',
  'State': 'Texas'},
 'The University of Texas at Austin': {'streetAddress': '2515 Speedway Dr',
  'City': 'Austin',
  'Zip Code': '78712',
  'State': 'Texas'},
 'Tyler Junior College': {'streetAddress': '1400 E 5th St',
  'City': 'Tyler',
  'Zip Code': '75701',
  'State': 'Texas'},
 'University of Houston College of Medicine': {'streetAddress': '5055 Medical Cir',
  'City': 'Houston',
  'Zip Code': '77204',
  'State': 'Texas'},
 'University of the Incarnate Word': {'streetAddress': '4301 Broadway',
  'City': 'San Antonio',
  'Zip Code': '78209',
  'State': 'Texas'},
 'Victoria College': {'streetAddress': '2200 E Red River St',
  'City': 'Victoria',
  'Zip Code': '77901',
  'State': 'Texas'}}

    return revised_parsed_dict

geocodes_v2 = geocode_thecb_addresses(f_parsed_dict)
f_parsed_dict_v2 = clean_up(geocodes_v2,f_parsed_dict)