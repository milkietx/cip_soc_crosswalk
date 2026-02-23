## helpers for cip to soc project
import sys
import pandas as pd
import os
import requests
import sqlite3
import os                                                                                                                                                                                                          
from dotenv import load_dotenv, find_dotenv
from pathlib import Path
import sqlite3
import duckdb
import geopandas as gpd
load_dotenv(Path(r"C:\Users\cmg0530\Projects\cip_soc_crosswalk\.env"))

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

def map_programs_to_schools_duckdb(con):

    con.execute("DROP TABLE IF EXISTS join_program_occupations")
    con.execute("""CREATE TABLE 
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
        if x not in ['geom_wkt','wkt_geom']:
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
                [x for x in row[1:].tolist()],
            )
        except Exception as e:
            print(f"Could not upload {index}")
            print(f"Exception: {e}")

    con.commit()
    print("Done!")

def make_table_spatial(crsr, con, geometry_type=None, wkt_col='geom_wkt',geometry_column='geometry',
                       srid=4326,
                       table_name="test__", schema="dbo"):
    """
    chunk_print_size = number of rows to print count when uploading
    """

    print(f"Table name: {schema}_{table_name}")
    print(f"Making it spatial on column {wkt_col}")

    #initalize if not already
    con.execute("SELECT load_extension('mod_spatialite')")
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
    api_key = os.getenv("MAPS_API_KEY")
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
    
#%% build spatial files into database

def get_all_files_os_walk(directory_path: str)-> list:
    file_list = []
    for root, _, files in os.walk(directory_path):
        for file in files:
            # Construct the full file path
            full_path = os.path.join(root, file)
            file_list.append(full_path)
    return file_list

def unzip_gis_files(folder:str,out_folder:str):
    import zipfile
    fps = get_all_files_os_walk(directory_path=folder)
    pdict = {}
    for z in fps:
        n = z.split('2020_')[-1].split(".zip")[0]
        pdict[n] = z
    #unzip to new folder
    for fn in pdict.keys():
        print(fn)
        with zipfile.ZipFile(pdict[fn], 'r') as zip_ref:
            zip_ref.extractall(os.path.join(out_folder,f"{fn}"))

def bulk_reproject_gis_files(folder:str,outfolder:str,new_crs:int)->str:
    import geopandas as gpd
    
    #check if output exists
    if not os.path.exists(outfolder):
        os.makedirs(outfolder)
        
    #read in files from folder that contains everything you want reprojected
    file_list = []
    for root, _, files in os.walk(folder):
        for file in files:
            # Construct the full file path
            full_path = os.path.join(root, file)
            if full_path.endswith(".shp"):
                file_list.append(full_path)

    #loop through and reproject everything and save back to disk
    for x in file_list:
        print(f"{x.split("\\")[-1]}")
        f_in = gpd.read_file(x)
        f_out = f_in.copy()
        f_out = f_out.to_crs(f"EPSG:{new_crs}")
        f_out.to_file(os.path.join(outfolder,x.split("\\")[-1]))

    #return outfolder path
    return outfolder


def generate_bulk_upload_list_from_folder(folder=r"C:\Users\cmg0530\Projects\cip_soc_crosswalk\Data Downloads\Spatial Data\NHGIS\GIS Data\Reprojected") -> list:
    fold = [x[0] for x in os.walk(folder)][0]
    fl =  [x[2] for x in os.walk(folder)][0]
    bulk_upload_file_list = [os.path.join(fold,q) for q in fl if q.endswith(".shp")]
    return bulk_upload_file_list


def bulk_upload_to_sqlite(bulk_upload_file_list:str, db_path:str,schema:str):
    import geopandas as gpd
    from shapely.geometry.polygon import Polygon
    from shapely.geometry.multipolygon import MultiPolygon

    for x in bulk_upload_file_list:
        #read in file and convert geometry to geom_wkt
        print(x)
        tf = gpd.read_file(x)
        crs = tf.geometry.crs.to_epsg()
        try:
            tf["geometry"] = [MultiPolygon([feature]) if isinstance(feature, Polygon) else feature for feature in tf["geometry"]]
        except:
            print("Not a polygon or multipolygon shape")
        tf['geom_wkt'] = tf.apply(lambda x: x['geometry'].wkt,axis=1)
        tf = tf.drop(columns=['geometry'])

        #table name
        title = x.split("\\")[-1][0:-4]

        #upload to sqlite 
        con = create_conn(db_path)
        upload_to_sqlite(con.cursor(),
                         con,
                         tf,
                         title,
                         schema,
                         drop=True,
                         chunk_print_size=5000)

        #make spatial in sqlite
        make_table_spatial(con.cursor(), 
                       con,
                       wkt_col='geom_wkt',
                       geometry_column='geometry',
                       srid=crs,
                       table_name=title, 
                       schema=schema)
    


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

#%%
#duck db additions


def connect_duckdb(filepath,spatial=True):
    import duckdb
    import os
    if os.path.exists(filepath):
        print(f"Creating database at {filepath}")
        conn = duckdb.connect(filepath)
        conn.install_extension('spatial')
    else:
        conn = duckdb.connect(filepath)
    conn.load_extension("spatial")
    return conn

def load_from_df(conn:duckdb.DuckDBPyConnection,
                  df,
                  table_name:str,
                  drop:bool=False):
    #load spatial extension
    conn.execute("LOAD spatial;")

    conn.register("df_view", df)
    
    if drop == True:
        try:
            conn.execute(f"DROP TABLE {table_name}")
        except:
            print("Table is new")

    # Create the table with a proper GEOMETRY column
    conn.execute(f"""
        CREATE TABLE {table_name} AS
        SELECT * 
        FROM df_view""")
    
    conn.execute(f"""DROP VIEW df_view;""")
    conn.commit()

def load_from_gdf(conn:duckdb.DuckDBPyConnection,
                  gdf,
                  table_name:str,
                  geom_col_name:str='geom'):
    #load spatial extension
    #add better documenation and try except blocks for error testing
    conn.execute("LOAD spatial;")

    # Register the GeoDataFrame as a view, converting geometry to WKB for DuckDB
    gdf["geom_wkb"] = gdf.geometry.to_wkb()
    
    #Get the CRS
    crs_wkt = gdf.crs.to_wkt()
    
    df = gdf.drop(columns="geometry")  # drop original geometry column

    conn.register("gdf_view", df)
    
    try:
        conn.execute(f"DROP TABLE {table_name}")
    except:
        print("Table is new")
    # Create the table with a proper GEOMETRY column
    conn.execute(f"""
        CREATE TABLE {table_name} AS
        SELECT * EXCLUDE (geom_wkb),
            ST_Transform(
            ST_GeomFromWKB(geom_wkb),
            '{crs_wkt}',
            '{crs_wkt}',
            always_xy := true
        ) AS {geom_col_name}
        FROM gdf_view
    """)

    conn.execute(f"""DROP VIEW gdf_view;""")
    conn.commit()
    