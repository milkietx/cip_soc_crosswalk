## the aim of this code is to download all programs from THECB
##source location = https://www.txhigheredaccountability.org/AcctPublic/InteractiveReport/AddReport

import sys
sys.path.append(r'C:\Users\cmg0530\Projects\cip_soc_crosswalk\Project Code\codelib')
from helpers import *
import pandas as pd
import os

def main():
    #connect to db
    db_path = r'C:\Users\cmg0530\Projects\cip_soc_crosswalk\Databases\cip_soc_duck.db'
    con = connect_duckdb(db_path)
    
    #make the connections
    #campuses-msa
    con.sql("""CREATE TEMP TABLE msa_match AS 
                SELECT r."Institution Name", 
                r."System Name",
                leg.GISJOIN, 
                leg.GEOID as COUNTY
                FROM ref_thecb_geocode as r
    JOIN geom_US_cbsa_2020 as leg
    on ST_Intersects(r.geom,leg.geom);""")

    #campuses-counties
    con.sql("""CREATE TEMP TABLE county_match AS 
                SELECT r."Institution Name", 
                r."System Name",
                leg.GISJOIN, 
                leg.GEOID as COUNTY
                FROM ref_thecb_geocode as r
    JOIN geom_US_county_2020 as leg
    on ST_Intersects(r.geom,leg.geom);""")

    #campuses-state sen
    con.sql("""CREATE TEMP TABLE lower_leg_match AS
                SELECT r."Institution Name", 
                r."System Name",
                leg.GISJOIN, 
                leg.GEOID as ST_LEG_LOWER
                FROM ref_thecb_geocode as r
    JOIN geom_US_stleg_up_2020 as leg
    on ST_Intersects(r.geom,leg.geom);""")

    #campuses-state leg
    con.sql("""CREATE TEMP TABLE upper_leg_match AS
                SELECT r."Institution Name", 
                r."System Name",
                leg.GISJOIN, 
                leg.GEOID as ST_LEG_UPPER
                FROM ref_thecb_geocode as r
    JOIN geom_US_stleg_lo_2020 as leg
    on ST_Intersects(r.geom,leg.geom);""")


import geopandas as gpd
a = gpd.read_file(r"C:\Users\cmg0530\Projects\cip_soc_crosswalk\Data Downloads\Spatial Data\NHGIS\Unzipped Folders\us_metdiv_2020\US_metdiv_2020.shp")
    

if __name__ == "__main__":
    main()
