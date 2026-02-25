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
                leg.GEOID as MSA,
                leg.NAMELSAD as MSA_name
                FROM ref_thecb_geocode as r
    JOIN geom_US_cbsa_2020 as leg
    on ST_Intersects(r.geom,leg.geom);""")

    #campuses-counties
    con.sql("""CREATE TEMP TABLE county_match AS 
                SELECT r."Institution Name", 
                r."System Name",
                leg.GISJOIN, 
                leg.GEOID as COUNTY,
                leg.NAMELSAD as COUNTY_name
                FROM ref_thecb_geocode as r
    JOIN geom_US_county_2020 as leg
    on ST_Intersects(r.geom,leg.geom);""")

    #campuses-state sen
    con.sql("""CREATE TEMP TABLE lower_leg_match AS
                SELECT r."Institution Name", 
                r."System Name",
                leg.GISJOIN, 
                leg.GEOID as ST_LEG_LOWER,
                leg.NAMELSAD as ST_LEG_LOWER_name
                FROM ref_thecb_geocode as r
    JOIN geom_US_stleg_up_2020 as leg
    on ST_Intersects(r.geom,leg.geom);""")

    #campuses-state leg
    con.sql("""CREATE TEMP TABLE upper_leg_match AS
                SELECT r."Institution Name", 
                r."System Name",
                leg.GISJOIN, 
                leg.GEOID as ST_LEG_UPPER,
                leg.NAMELSAD as ST_LEG_UPPER_name
                FROM ref_thecb_geocode as r
    JOIN geom_US_stleg_lo_2020 as leg
    on ST_Intersects(r.geom,leg.geom);""")

    con.execute("""DROP TABLE if exists xwalk_institution_geography """)
    
    con.sql("""CREATE TABLE xwalk_institution_geography AS
            SELECT r."Institution Name", 
                r."System Name",
                a.MSA,
            a.MSA_name,
                b.COUNTY,
            b.COUNTY_name,
                c.ST_LEG_LOWER,
            c.ST_LEG_LOWER_name,
                d.ST_LEG_UPPER,
            d.ST_LEG_UPPER_name,
            FROM ref_thecb_geocode as r
            JOIN msa_match as a 
            ON r."Institution Name" = a."Institution Name"
            JOIN county_match as b
            ON r."Institution Name" = b."Institution Name"
            JOIN lower_leg_match as c
            ON r."Institution Name" = c."Institution Name"
            JOIN upper_leg_match as d
            ON r."Institution Name" = d."Institution Name"
            """)
    
    con.commit()

