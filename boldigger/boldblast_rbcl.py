import requests_html, openpyxl, ntpath, os, datetime, asyncio
import PySimpleGUI as sg
import numpy as np
import pandas as pd
from bs4 import BeautifulSoup as BSoup
from openpyxl.utils.dataframe import dataframe_to_rows
from boldigger.boldblast_coi import slices, fasta_to_string, fasta_rewrite
from boldigger.boldblast_its import save_as_df, save_results, as_request, as_session, save_as_df, save_results, excel_converter
from requests.exceptions import ReadTimeout
from requests.exceptions import ConnectionError

## function to generate a link for every query
def post_request(query, session):

    seq_data = {
    'tabtype': 'plantTabPane',
    'searchdb': 'MATK_RBCL',
    'sequence': query
    }

    ## send search request
    r = session.post('http://boldsystems.org/index.php/IDS_BlastRequest', data = seq_data, timeout = 600)

    ## extract Top20 table links from the BOLD Result page
    soup = BSoup(r.text, 'html5lib')
    data = soup.find_all('span', style = 'text-decoration: none')
    data = ['http://boldsystems.org' + data[i].get('result') for i in range(len(data))]

    ## return the data
    return data

def main(session, fasta_path, output_path, query_length):
    ## define some variables needed for the layout
    querys, sequences_names = fasta_to_string(fasta_path, query_length)

    ## define a layout for the new window
    layout = [
    [sg.Text('Progress', size = (8, 1), key = 'bar_des1'), sg.ProgressBar(len(querys), orientation = 'h', size = (25, 20), key = 'bar1')],
    [sg.Multiline(size = (50, 10), key = 'out', autoscroll = True)]
    ]

    ## run the request loop only once set ran to True afterwards
    window = sg.Window('BOLD identification engine', layout)
    bar1 = window['bar1']
    ran = False

    ## main loop to control the window
    while True:

        ## if the loop has not run yet start it
        if not ran:

            ## request as long as there are querys left
            for query in querys:
                while True:
                    try:
                        event, values = window.read(timeout = 100)

                        ## update the window and give user output
                        window['out'].print('%s: Requesting BOLD. This will take a while.' % datetime.datetime.now().strftime("%H:%M:%S"))
                        window.Refresh()

                        ## collect IDS result urls from BOLD
                        links = post_request(query, session)

                        ## updat the first progress bar
                        bar1.UpdateBar(querys.index(query) + 1)

                        ## download the data from the links
                        window['out'].print('%s: Downloading results.' % datetime.datetime.now().strftime("%H:%M:%S"))
                        window.Refresh()

                        ## get all urls at the same time
                        tables = asyncio.run(as_session(links))

                        ## parse the returned html
                        window['out'].print('%s: Parsing html.' % datetime.datetime.now().strftime("%H:%M:%S"))
                        window.Refresh()
                        result = save_as_df(tables, sequences_names[querys.index(query)])

                        ## save results in the results file
                        window['out'].print('%s: Saving results.' % datetime.datetime.now().strftime("%H:%M:%S"))
                        window.Refresh()
                        save_results(result, fasta_path, output_path)
                    except (ValueError, ReadTimeout, ConnectionError):
                        window['out'].print('%s: BOLD did not respond! Retrying.' % datetime.datetime.now().strftime("%H:%M:%S"))
                        continue
                    break

                ## remove found OTUS from fasta and write it into a new one
                window['out'].print('%s: Removing finished OTUs from fasta.' % datetime.datetime.now().strftime("%H:%M:%S"))
                window.Refresh()
                fasta_rewrite(fasta_path, query_length)

            ## convert results to excel when download is finished
            window['out'].print('%s: Converting the data to excel.' % datetime.datetime.now().strftime("%H:%M:%S"))
            excel_converter(fasta_path, output_path)

            ran = True

        window['out'].print('%s: Done. Close to continue.' % datetime.datetime.now().strftime("%H:%M:%S"))
        window.Refresh()
        event, values = window.read()

        if event == None:
            break

    window.Close()
