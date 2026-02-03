## the aim of this code is to download all programs from THECB
##source location = https://www.txhigheredaccountability.org/AcctPublic/InteractiveReport/AddReport

import sys
sys.path.append(r'C:\Users\cmg0530\Projects\cip_soc_crosswalk\Project Code\codelib')
from helpers import *
import pandas as pd
import os

def main():
    #download cip soc and process 
    def process_addresses_for_schools() -> pd.core.frame.DataFrame:
        sd = pd.read_csv(r"C:\Users\cmg0530\Projects\cip_soc_crosswalk\Data Downloads\Spatial Data\thecb_addresses_02_03_2026.csv")
        sd['combined_address'] = sd.apply(lambda x: f"{x['Address']} {x['City']}, TX {x['Zip Code']}",axis=1)
        sd['geocode_response'] = sd.apply(lambda x: google_maps_geocode(x['combined_address']),axis=1)
        sd['lat'] = sd['geocode_response'].str[0]
        sd['lon'] = sd['geocode_response'].str[1]
        return sd


    #connect to database
    sd = process_addresses_for_schools()
    db_path = r'C:\\Users\\cmg0530\\Projects\\cip_soc_crosswalk\\Databases\\cipsoc.sqlite'
    con = create_conn(db_path)
    import geopandas as gpd
    gsd = gpd.GeoDataFrame(sd,geometry=gpd.points_from_xy(sd['lon'],sd['lat']),crs='EPSG:4326')
    gsd['geom_wkt'] = gsd.apply(lambda x: x['geometry'].wkt,axis=1)
    gsdu = gsd.drop(columns=['geocode_response','geometry'])


    #upload table to sqlite
    upload_to_sqlite(con.cursor(), 
                    con, 
                    gsdu, 
                    table_name="thecb_geocode",
                    schema="ref", 
                    drop=True, 
                    chunk_print_size=1000)

    #make the table spatial
    make_table_spatial(con.cursor(), 
                       con,
                       wkt_col='geom_wkt',
                       geometry_column='geometry',
                       srid='3857',
                       table_name="thecb_geocode", 
                       schema="ref")

    #build out a final table that looks like:
        #program - institution - occupation
    all_df = pd.read_sql("select * from join_program_occupations",con=con)
    all_df_filt = all_df.query("year == '2023'")
    all_df_filt.to_excel(r"C:\Users\cmg0530\Projects\cip_soc_crosswalk\Data Downloads\Sample Exports\test.xlsx")

if __name__ == "__main__":
    main()
#%% future or other functions as needed
#upload to interactive portal for editing
    #(link to interactive portal for editing)
    #function that pulls from the sqlite3

#re-download and upload into database with edits/additions
    #function that pulls from wherever this works

#download programs from thecb

#upload into database

#link programs to occupations via cip soc

#save to database

#pull from database
