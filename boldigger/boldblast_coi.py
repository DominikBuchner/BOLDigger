import requests_html, openpyxl, ntpath, os, datetime, asyncio
import PySimpleGUI as sg
import numpy as np
import pandas as pd
from pathlib import Path
from bs4 import BeautifulSoup as BSoup
from openpyxl.utils.dataframe import dataframe_to_rows
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

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
    r = await as_session.get(url, timeout = 300)
    return r.text

## generate an async session and add adapters to it
## gather all tasks for the event loop
async def as_session(url_list):
    as_session = requests_html.AsyncHTMLSession()
    as_session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.82 Safari/537.36"})
    retry_strategy = Retry(total = 10, status_forcelist = [400, 401, 403, 404, 429, 500, 502, 503, 504], backoff_factor = 1)
    adapter = HTTPAdapter(max_retries = retry_strategy)
    as_session.mount('https://', adapter)
    as_session.mount('http://', adapter)
    tasks = (as_request(url, as_session) for url in url_list)
    return await asyncio.gather(*tasks)

## function to convert returned html in dataframes
def save_as_df(html_list, sequence_names):

    ## create a soup of every result page that is returned by requests
    soups = [BSoup(html, 'html5lib') for html in html_list]
    ## find the resulttable in the html
    tables = [soup.find('table', class_ = 'resultsTable noborder') for soup in soups]

    ## if None is returned add a NoMatch table instead
    ## create nomatch table before creating rest of dataframes
    nomatch_array = np.array([['No Match'] * 9 + [''] for i in range(20)])
    nomatch_df = pd.DataFrame(nomatch_array)
    nomatch_df.columns = ['Phylum', 'Class', 'Order', 'Family', 'Genus', 'Species', 'Subspecies', 'Similarity (%)', 'Status', 'Process ID']

    ## read the table to a data frame, is no table is there soup.find returns None and a Nomatch dataframe is added
    dataframes = [pd.read_html(str(table), header = 0)[0] if table != None else nomatch_df for table in tables]

    ## extract the process ids from the html
    process_id_lists = [soup.find_all(class_ = 'publicrecord') for soup in soups]
    process_id_lists = [[process_id_list[i] for i in range(len(process_id_list))] for process_id_list in process_id_lists]
    process_id_lists = [[tag.get('id') for tag in process_id_list] for process_id_list in process_id_lists]

    ## add process IDs to published sequence
    for index in range(len(dataframes)):
        if process_id_lists[index]:
            statuslist = list(np.where(dataframes[index]['Status'] == 'Published', True, False))
            statuslist = [process_id_lists[index].pop(0) if status else '' for status in statuslist]
            dataframes[index]['Process ID'] = statuslist
        else:
            dataframes[index]['Process ID'] = ''

    ## save columns before to sort them after
    cols = dataframes[index].columns.tolist()
    ## add sequence names to dataframes
    for index in range(len(dataframes)):
        ## add sequence names
        dataframes[index].at[0, 'You searched for:'] = sequence_names[index]
        dataframes[index] = dataframes[index][['You searched for:'] + cols]

    ## return all dataframe --> One dataframe per requestes sequences is returned
    return dataframes

## function to save results to an excel file as output
def save_results(dataframes, fasta_path, output_path):

    ## savename is always BOLDResults_ + name of fasta that is searched for
    ## savepath is always the result folder in the boldigger path
    savename = 'BOLDResults_' + ntpath.splitext(ntpath.basename(fasta_path))[0] + '.xlsx'

    ## open resultsfile if it exists, create if it does not
    try:
        wb = openpyxl.load_workbook(os.path.join(output_path, savename))
    except FileNotFoundError:
        wb = openpyxl.Workbook()

    ## select and name worksheet
    ws = wb.active
    ws.title = "Run %s" % datetime.datetime.now().strftime("%d-%m-%Y %H.%M")

    ## wirte data to sheet
    for df in dataframes:
        for r in dataframe_to_rows(df, index = False, header = False):
            ws.append(r)

    ## finalize only once with a header
    if ws.cell(row = 1, column = 1).value != 'You searched for':
        ## add a row and a column at for header and otus
        ws.insert_rows(1)

        ## add header to resultfile
        header = ['You searched for', 'Phylum', 'Class', 'Order', 'Family', 'Genus', 'Species', 'Subspecies', 'Similarity', 'Status', 'Process ID']

        for column in range(len(header)):
            ws.cell(row = 1, column = column + 1).value = header[column]

    ## save workbook
    wb.save(os.path.join(output_path, savename))

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
                html_list = asyncio.run(as_session(links))

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

            ran = True

        window['out'].print('%s: Done. Close to continue.' % datetime.datetime.now().strftime("%H:%M:%S"))
        window.Refresh()
        event, values = window.read()

        if event == None:
            break

    window.Close()
