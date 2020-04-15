import requests_html, openpyxl, ntpath, os, datetime
import PySimpleGUI as sg
import numpy as np
import pandas as pd
from bs4 import BeautifulSoup as BSoup
from requests.exceptions import ConnectionError
from requests.exceptions import ReadTimeout
from openpyxl.utils.dataframe import dataframe_to_rows
from boldigger.boldblast_coi import slices, fasta_to_string, requests, fasta_rewrite
from boldigger.boldblast_its import save_as_df, save_results

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
    [sg.Text('', size = (15, 1), key = 'bar_des1'), sg.ProgressBar(len(querys), orientation = 'h', size = (20, 20), key = 'bar1')],
    [sg.Text('', size = (15, 1), key = 'bar_des2'), sg.ProgressBar(100, orientation = 'h', size = (20, 20), key = 'bar2')],
    [sg.Multiline(size = (50, 10), key = 'out', autoscroll = True)]
    ]

    ## run the request loop only once set ran to True afterwards
    window = sg.Window('BOLD identification engine', layout)
    bar1 = window['bar1']
    bar2 = window['bar2']
    ran = False
    error = False

    ## main loop to control the window
    while True:

        ## if the loop has not run yet start it
        if not ran:

            ## request as long as there are querys left
            for query in querys:
                event, values = window.read(timeout = 10)

                ## stop if there are 3 connectionerrors or timeouts
                error_count = 0
                ## request until you get a good answer from the server
                while True:

                    ## update the window and give user output
                    window['out'].print('%s: Requesting BOLD. This will take a while.' % datetime.datetime.now().strftime("%H:%M:%S"))
                    window['bar_des1'].update('Requesting BOLD')
                    window.Refresh()

                    ## try to get a answer from bold server, repeat in case of timeout
                    try:
                        links = post_request(query, session)
                    except ConnectionError:
                        window['out'].print('%s: ConnectionError, BOLD did not respond properly: Trying to reconnect.' % datetime.datetime.now().strftime("%H:%M:%S"))
                        window.Refresh()
                        error_count += 1
                        continue
                    except ReadTimeout:
                        window['out'].print('%s: Readtimeout, BOLD did not respond in time: Trying to reconnect.' % datetime.datetime.now().strftime("%H:%M:%S"))
                        window.Refresh()
                        error_count += 1
                        continue
                    break
                else:
                    error = True
                    ran = True

                if not error:
                    ## updat the first progress bar
                    bar1.UpdateBar(querys.index(query) + 1)

                    ## download the data from the links
                    window['bar_des2'].update('Downloading results')
                    window['out'].print('%s: Downloading results.' % datetime.datetime.now().strftime("%H:%M:%S"))
                    window.Refresh()
                    html_list = requests(links, bar2)


                    ## parse the returned html
                    window['out'].print('%s: Parsing html.' % datetime.datetime.now().strftime("%H:%M:%S"))
                    window.Refresh()
                    dataframes = save_as_df(html_list, sequences_names[querys.index(query)])

                    ## save results in the results file
                    window['out'].print('%s: Saving results.' % datetime.datetime.now().strftime("%H:%M:%S"))
                    window.Refresh()
                    save_results(dataframes, fasta_path, output_path)

                    ## remove found OTUS from fasta and write it into a new one
                    window['out'].print('%s: Removing finished OTUs from fasta.' % datetime.datetime.now().strftime("%H:%M:%S"))
                    window.Refresh()
                    fasta_rewrite(fasta_path, query_length)

                    ## set download bar to 0
                    bar2.UpdateBar(0)
                else:
                    window['out'].print('%s: Too many bad connections. Try a smaller batch size. Close to continue.' % datetime.datetime.now().strftime("%H:%M:%S"))
                    break

            ran = True

        if not error:
            window['out'].print('%s: Done. Close to continue.' % datetime.datetime.now().strftime("%H:%M:%S"))
        window.Refresh()
        event, values = window.read()

        if event == None:
            break

    window.Close()
