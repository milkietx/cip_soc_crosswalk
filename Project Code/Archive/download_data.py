## the aim of this code is to download all programs from THECB
##source location = https://www.txhigheredaccountability.org/AcctPublic/InteractiveReport/AddReport

import sys
sys.path.append(r'C:\Users\cmg0530\Projects\cip_soc_crosswalk\Project Code\codelib')
from helpers import *
import pandas as pd
import os

def main():
    #download cip soc and process 
    csdf = read_in_cip_soc()
    csdf = process_cip_soc(csdf)

    #download thecb and process
    thecb_dict = read_in_thecb()
    tdf = process_thecb(thecb_dict)

    #connect to database
    db_path = r'C:\\Users\\cmg0530\\Projects\\cip_soc_crosswalk\\Databases\\cipsoc.sqlite'
    con = create_conn(db_path)

    #upload two tables cip to soc to database: cip-soc and thecb data
    upload_to_sqlite(con.cursor(), 
                    con, 
                    csdf, 
                    table_name="cip_soc_nces",
                    schema="ref", 
                    drop=True, 
                    chunk_print_size=1000)

    upload_to_sqlite(con.cursor(), 
                    con, 
                    tdf, 
                    table_name="thecb_data",
                    schema="ref", 
                    drop=True, 
                    chunk_print_size=1000)

    #need a general function that can map education data with occupation data 
    map_programs_to_schools(con)

    #build out a final table that looks like:
        #program - institution - occupation
    all_df = pd.read_sql("select * from join_program_occupations",con=con)
    all_df_filt = all_df.query("year == '2023'")
    all_df_filt.to_excel(r"C:\Users\cmg0530\Projects\cip_soc_crosswalk\Data Downloads\Sample Exports\test.xlsx")


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
