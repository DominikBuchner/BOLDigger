import openpyxl, datetime
import pandas as pd
import numpy as np
import PySimpleGUI as sg
from string import punctuation
from string import digits
from pathlib import Path


def first_hit(xlsx_path):
    ## load data into a dataframe
    data = pd.read_excel(xlsx_path, header=0, engine="openpyxl")
    data = data.rename(columns={"You searched for": "ID"})

    ## clean data from punctuation and numbers before selecting any hit
    ## second data cleaning step
    specials = punctuation + digits
    levels = ["Phylum", "Class", "Order", "Family", "Genus", "Species"]

    for level in levels:
        data[level] = np.where(
            data[level].str.contains("[{}]".format(specials)), "", data[level]
        )

    ## if there are more than two words in the species column, only keep the first one
    ## first data cleaning step, add a workaroung for the No Match strings to not break
    ## backwards compability
    data["Species"] = data["Species"].replace("No Match", "NoMatch")
    data["Species"] = data["Species"].str.split(" ").str[0]
    data["Species"] = data["Species"].replace("NoMatch", "No Match")

    ## open workbook for checking the type and create writer to save data later
    wb = openpyxl.load_workbook(xlsx_path)
    ws = wb.active

    ## check if coi or its / rbcl
    type = "coi" if ws.cell(row=1, column=11).value == "Process ID" else "its_rbcl"

    ## top hit is every 20th hit
    if type == "coi":
        data = data.iloc[::20]

    ## there can be any number of hit between 1 and 99, so lookup is more complicated
    if type == "its_rbcl":
        ## must include nomatch, so we dont lose OTUS
        first_hits = [1, "No Match"]

        ## remove everything that is not a top hit or a NoMatch
        ## remove nomatch duplices, drop the first non duplicate Nomatch
        data = data[data["Rank"].isin(first_hits)]
        data = data.drop_duplicates()
        data = data.dropna(subset=["ID"])

    ## close and save the writer
    with pd.ExcelWriter(
        Path(xlsx_path), mode="a", if_sheet_exists="replace", engine="openpyxl"
    ) as writer:
        data.to_excel(writer, sheet_name="First hit", index=False)


## main function to control GUI and flow
def main(xlsx_path):
    ## define a layout for the new window
    layout = [[sg.Multiline(size=(50, 10), key="out", autoscroll=True)]]

    ## run the download loop only once. After that only run event loop
    window = sg.Window("Adding top hits", layout)
    ran = False

    while True:
        event, values = window.read(timeout=100)

        if not ran:
            window["out"].print(
                "%s: Opening resultfile." % datetime.datetime.now().strftime("%H:%M:%S")
            )
            window.Refresh()

            ## run first hit function
            window["out"].print(
                "%s: Filtering data." % datetime.datetime.now().strftime("%H:%M:%S")
            )
            window.Refresh()
            first_hit(xlsx_path)

            window["out"].print(
                "%s: Saving result to new tab."
                % datetime.datetime.now().strftime("%H:%M:%S")
            )
            window.Refresh()

            window["out"].print(
                "%s: Done. Close to continue."
                % datetime.datetime.now().strftime("%H:%M:%S")
            )
            window.Refresh()

            ran = True

        if event == None:
            break

    window.Close()
