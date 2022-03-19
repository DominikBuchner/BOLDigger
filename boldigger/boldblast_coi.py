import requests_html, openpyxl, ntpath, os, datetime, asyncio, operator
import PySimpleGUI as sg
import numpy as np
import pandas as pd
from pathlib import Path
from bs4 import BeautifulSoup as BSoup
from openpyxl.utils.dataframe import dataframe_to_rows
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from requests.exceptions import ReadTimeout
from requests.exceptions import ConnectionError
from functools import reduce

## function to return slices of a list as a list of lists
## slices([1, 2, 3, 4, 5], 2) --> [[1,2], [3,4], [5]]
def slices(list, slice):
    for i in range(0, len(list), slice):
        yield list[i : i + slice]

## function to read the fasta file you want to blast
## returns content of the file as list of query strings of a length of 250 sequences
## returns the names of the sequences you searched to later pass them in to the result list
def fasta_to_string(fasta_path, query_size):

    ## open fasta file and read content
    with open(fasta_path, 'r') as input:
        query = input.read()

    ## extract the sequence names from the fasta file
    sequence_names = list(slices(query.split('\n')[::2][:-1], query_size))

    ## split query into different lists each containing 250 sequences, which is fast to blast
    ## join them to strings afterwards because bold post methods expects a single string
    query = query.split('\n')[:-1]
    query = list(slices(query, query_size * 2))
    query = ['\n'.join(sublist) for sublist in query]

    ## return query for blasting later and sequence names for adding to the results later
    return query, sequence_names

## function to generate links from a list
def post_request(query, session):

    seq_data = {
    'tabtype': 'animalTabPane',
    'historicalDB': '',
    'searchdb': 'COX1',
    'sequence': query
    }

    ## send search request
    r = session.post('https://boldsystems.org/index.php/IDS_IdentificationRequest', data = seq_data, timeout = 300)

    ## extract Top20 table links from the BOLD Result page
    soup = BSoup(r.text, 'html5lib')
    data = soup.find_all('span', style = 'text-decoration: none')
    data = ['http://boldsystems.org' + data[i].get('result') for i in range(len(data))]

    ## return the data
    return data

## asynchronous request code to send all requests at once
async def as_request(url, as_session):
    ## add all requests to the eventloop, in case of a malformed response readd them to the event loop until
    ## a correct response can be scraped
    while True:
        try:
            r = await as_session.get(url, timeout = 300)
            tables = pd.read_html(r.text, header = 0, converters = {'Similarity (%)': float}, flavor = 'html5lib')
            break
        except ValueError:
            continue

    ## return No Match if there is no result table
    if len(tables) == 2:
        table = pd.DataFrame([['No Match'] * 7 + [np.nan] + [''] * 2] * 20,
                             columns = ['Phylum', 'Class', 'Order', 'Family', 'Genus', 'Species', 'Subspecies', 'Similarity', 'Status', 'Process_ID'])

    ## return result if there is one
    elif len(tables) == 3:
        table = tables[1]
        ids = BSoup(r.text, 'html5lib')
        ids = [tag.get('id') for tag in ids.find_all(class_ = 'publicrecord')]
        table.columns = ['Phylum', 'Class', 'Order', 'Family', 'Genus', 'Species', 'Subspecies', 'Similarity', 'Status']
        table['Process_ID'] = [ids.pop(0) if status else np.nan for status in np.where(table['Status'] == 'Published', True, False)]
        table[['Phylum', 'Class', 'Order', 'Family', 'Genus', 'Species', 'Subspecies', 'Status']] = table[['Phylum', 'Class', 'Order', 'Family', 'Genus', 'Species', 'Subspecies', 'Status']].fillna('')

    return table

## generate an async session and add adapters to it
## gather all tasks for the event loop
async def as_session(url_list):
    as_session = requests_html.AsyncHTMLSession()
    as_session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.82 Safari/537.36"})
    retry_strategy = Retry(total = 15, status_forcelist = [400, 401, 403, 404, 413, 429, 500, 502, 503, 504], backoff_factor = 1)
    adapter = HTTPAdapter(max_retries = retry_strategy)
    as_session.mount('https://', adapter)
    as_session.mount('http://', adapter)
    tasks = (as_request(url, as_session) for url in url_list)
    return await asyncio.gather(*tasks)

## function to concat the returned dataframes
def save_as_df(tables, sequence_names):

    ## concat the resulting tables from the requested resultpages
    result = pd.concat(tables, axis = 0)

    ## add sequence names to the results
    result.insert(0,'You_searched_for', reduce(operator.concat, [[name] + [np.nan] * 19 for name in sequence_names]))

    ## return the resulting dataframe
    return result

## function to save results to hdf format. This greatly increased writing and reading times
def save_results(dataframe, fasta_path, output_path):

    ## savename is always BOLDResults_ + name of fasta that is searched for
    ## savepath is always the result folder in the boldigger path
    ## files are saved in hdf format while runtime, will be transformed to excel as soon as requests are done
    savename = 'BOLDResults_{}.h5.lz'.format(ntpath.splitext(ntpath.basename(fasta_path))[0])

    ## set size limits for the columns, maybe need to change in the future but should cover most taxa names
    sizes = {'You_searched_for': 100,
             'Phylum': 80,
             'Class': 80,
             'Order': 80,
             'Family': 80,
             'Genus': 80,
             'Species': 80,
             'Subspecies': 80,
             'Status' : 15,
             'Process_ID': 25}

    ## apend results to the hdf output file, compress result
    with pd.HDFStore(os.path.join(output_path, savename), mode = 'a', complib = 'blosc:blosclz', complevel = 9) as storage:
        storage.append('results', dataframe, format = 't', data_columns = True, min_itemsize = sizes, complib = 'blosc:blosclz', complevel = 9)

## function to move query size sequences to the same file with the extension _done
## in case of crash of the script you can just start it again without changing
## anything in the fasta file
def fasta_rewrite(fasta_path, query_size):

    ## read input
    with open(fasta_path, 'r') as input:
        data = input.read().splitlines(True)

    ## create out put name
    name, ext = Path(fasta_path).stem, Path(fasta_path).suffix
    output_name = '{}_done{}'.format(name, ext)
    output_path = Path(fasta_path).parents[0].joinpath(output_name)

    ## write output
    with open(output_path, 'a') as output:
        output.writelines(data[:query_size * 2])

    ## remove found lines from input fasta
    with open(fasta_path, 'w') as input:
        input.writelines(data[query_size * 2:])

    ## remove the empty fasta in the end
    if os.stat(fasta_path).st_size == 0:
        os.remove(fasta_path)

## function to convert downloaded h5 data to excel in the end
def excel_converter(fasta_path, output_path):

    ## generate both savenames
    savename_h5 = 'BOLDResults_{}.h5.lz'.format(ntpath.splitext(ntpath.basename(fasta_path))[0])

    ## read the data, rename the columns for backwards compability
    data = pd.read_hdf(os.path.join(output_path, savename_h5))
    data.columns = ['You searched for', 'Phylum', 'Class', 'Order', 'Family', 'Genus', 'Species', 'Subspecies', 'Similarity', 'Status', 'Process ID']

    ## split the data in 1 million row parts to fit in excel
    parts = enumerate(slices(range(len(data.index)), 1000000))
    ## push the data to excel file
    for idx, r in parts:
        savename_excel = 'BOLDResults_{}_part_{}.xlsx'.format(ntpath.splitext(ntpath.basename(fasta_path))[0], idx + 1)
        k, l = list(r)[0], list(r)[-1] + 1
        data.iloc[k: l].to_excel(os.path.join(output_path, savename_excel), index = False, sheet_name = "Run {}".format(datetime.datetime.now().strftime("%d-%m-%Y %H.%M")))

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
