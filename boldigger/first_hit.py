import openpyxl, datetime
import pandas as pd
import PySimpleGUI as sg

def first_hit(xlsx_path):

    ## open workbook for checking the type and create writer to save data later
    wb = openpyxl.load_workbook(xlsx_path)
    ws = wb.active
    writer = pd.ExcelWriter(xlsx_path, engine = 'openpyxl')
    writer.book = wb

    ## load data into a dataframe
    data = pd.read_excel(xlsx_path, header = 0)
    data = data.rename(columns = {'You searched for': 'ID'})

    ## check if coi or its / rbcl
    type = 'coi' if ws.cell(row = 1, column = 11).value == 'Process ID' else 'its_rbcl'

    ## top hit is every 20th hit
    if type == 'coi':
        data = data.iloc[::20]

    ## there can be any number of hit between 1 and 99, so lookup is more complicated
    if type == 'its_rbcl':
        ## must include nomatch, so we dont lose OTUS
        first_hits = [1, 'No Match']

        ## remove everything that is not a top hit or a NoMatch
        ## remove nomatch duplices, drop the first non duplicate Nomatch
        data = data[data['Rank'].isin(first_hits)]
        data = data.drop_duplicates()
        data = data.dropna(subset=['ID'])

    ## close and save the writer
    data.to_excel(writer, sheet_name = 'First hit', index = False)
    writer.save()
    writer.close()

## main function to control GUI and flow
def main(xlsx_path):

    ## define a layout for the new window
    layout = [
    [sg.Multiline(size = (50, 10), key = 'out', autoscroll = True)]
    ]

    ## run the download loop only once. After that only run event loop
    window = sg.Window('Adding top hits', layout)
    ran = False

    while True:

        event, values = window.read(timeout = 100)

        if not ran:
            window['out'].print('%s: Opening resultfile.' % datetime.datetime.now().strftime("%H:%M:%S"))
            window.Refresh()

            ## run first hit function
            window['out'].print('%s: Filtering data.' % datetime.datetime.now().strftime("%H:%M:%S"))
            window.Refresh()
            first_hit(xlsx_path)

            window['out'].print('%s: Saving result to new tab.' % datetime.datetime.now().strftime("%H:%M:%S"))
            window.Refresh()

            window['out'].print('%s: Done. Close to continue.' % datetime.datetime.now().strftime("%H:%M:%S"))
            window.Refresh()

            ran = True

        if event == None:
            break

    window.Close()
