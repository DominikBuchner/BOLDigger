import datetime, contextlib, requests_html, joblib, json, openpyxl, psutil
import PySimpleGUI as sg
import pandas as pd
import numpy as np
from tqdm import tqdm
from joblib import Parallel, delayed
from Bio.SeqIO.FastaIO import SimpleFastaParser
from boldigger.boldblast_coi import slices

## function to make tqdm work with parallelized code
@contextlib.contextmanager
def tqdm_joblib(tqdm_object):
    """Context manager to patch joblib to report into tqdm progress bar given as argument"""
    class TqdmBatchCompletionCallback(joblib.parallel.BatchCompletionCallBack):
        def __call__(self, *args, **kwargs):
            tqdm_object.update(n=self.batch_size)
            return super().__call__(*args, **kwargs)

    old_batch_callback = joblib.parallel.BatchCompletionCallBack
    joblib.parallel.BatchCompletionCallBack = TqdmBatchCompletionCallback
    try:
        yield tqdm_object
    finally:
        joblib.parallel.BatchCompletionCallBack = old_batch_callback
        tqdm_object.close()

## function to extract needed data from the input
def extract_data(xlsx_path, fasta_path):
    ## read in the raw data, extract data that needs to be queried
    try:
        raw_data = pd.read_excel(xlsx_path, sheet_name = 'BOLDigger hit', engine = 'openpyxl')
    except ValueError:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    data_to_check = raw_data.loc[raw_data['Similarity'].astype(str) != 'No Match']
    data_to_check = data_to_check.loc[(data_to_check['Similarity'] >= 98) & (data_to_check['Species'].isnull())].copy()

    ## collect the sequences to query API
    seq_dict = dict(SimpleFastaParser(open(fasta_path, 'r')))
    seq_dict = {k: v for k, v in seq_dict.items() if '>{}'.format(k) in data_to_check['ID'].to_list()}

    return raw_data, data_to_check, seq_dict

## function to send a request to the bold species identification api
## item is a dict entry from the seq_dict {OTU: Sequence}
def request(item, session):
    ## request BOLD API
    r = session.get('http://boldsystems.org/index.php/Ids_xml?db=COX1_SPECIES_PUBLIC&sequence={}'.format(item[1]))
    try:
        r = pd.read_xml(r.text)
        ## this is the species name
        most_common = r.loc[r['similarity'] >= 0.98]['taxonomicidentification'].mode().item()
        ## look up BOLD ID to query API again in case of missing higher taxonomic identification
        bold_id = r.loc[r['taxonomicidentification'] == most_common].iloc[0][0]
        return item[0], most_common, bold_id
    except ValueError:
        return None

## refreshes the dataset with the collected hits
def refresh_data(result, raw_data, data_to_check, session):
    result = pd.DataFrame(result, columns = ['ID', 'tax', 'BOLD_ID'])
    result['ID'] = ('>' + result['ID'])
    result['genus'], result['species'] = result['tax'].str.split(' ', n = 1).str[0], result['tax'].str.split(' ', n = 1).str[1]
    result['Status'] = 'Published'
    result['Flags'] = '5'

    ## filter species names that contain more than one word --> probably garbage, not usefull
    result = result.loc[result['species'].str.split(' ').str.len() == 1]

    ## generate dicts to map to the input table
    genus = dict(zip(result['ID'], result['genus']))
    species = dict(zip(result['ID'], result['species']))
    bold_ids = dict(zip(result['ID'], result['BOLD_ID']))
    status = dict(zip(result['ID'], result['Status']))
    flags = dict(zip(result['ID'], result['Flags']))

    ## correct the original dataframe
    data_to_check['Genus'] = data_to_check['ID'].map(genus).fillna(data_to_check['Genus'])
    data_to_check['Species'] = data_to_check['ID'].map(species).fillna(data_to_check['Species'])
    data_to_check['Status'] = data_to_check['ID'].map(status).fillna(data_to_check['Status'])
    data_to_check['Flags'] = data_to_check['ID'].map(flags).fillna(data_to_check['Flags'])

    ## collect remaining higher level taxonomy for species where it is missing
    remaining_data = data_to_check[data_to_check.isnull().any(axis = 1)]
    remaining_data = remaining_data.loc[~((remaining_data['Genus'].isnull()) | (remaining_data['Species'].isnull()))]

    ## collect the ids to request again via api
    bold_ids = {k: v for k, v in bold_ids.items() if k in remaining_data['ID'].to_list()}
    id_values = list(slices(list(bold_ids.values()), 100))

    ## collect responses here
    responses =  []
    ## request ids
    for id_pack in id_values:
        r = session.get('http://www.boldsystems.org/index.php/API_Public/specimen?ids={}&format=json'.format('|'.join(id_pack)))
        r = json.loads(r.text)['bold_records']['records']
        ## loop through the ids of the response, collect data, append to responses, handle responses with missing data
        for key in id_pack:
            ## create an temporary list to collect the data
            temp = []
            for tax_level in ['phylum', 'class', 'order', 'family']:
                try:
                    temp.append(r[key]['taxonomy'][tax_level]['taxon']['name'])
                except KeyError:
                    temp.append(np.nan)
            responses.append(temp)

    ## write the additional taxonomic information to a new dataframe and concat it to the one that's missing the data
    additional_tax = pd.DataFrame(responses,
                                  columns = ['Phylum', 'Class', 'Order', 'Family'],
                                  index = remaining_data.index)

    remaining_data = pd.concat([remaining_data.iloc[:, :1], additional_tax, remaining_data.iloc[:, 5:]], axis = 1)

    ## restore the original dataframe with all the data
    data_to_check.loc[remaining_data.index, :] = remaining_data[:]
    raw_data.loc[data_to_check.index, :] = data_to_check[:]

    return raw_data

## main function to control the flow of the program
def main(xlsx_path, fasta_path):

    ## define a layout for the new window
    layout = [[sg.Multiline(size = (50, 10), key = 'out', autoscroll = True)]]

    ## run the download loop only once. After that only run event loop
    window = sg.Window('API verification', layout)
    ran = False

    while True:
        event, values = window.read(timeout = 10)

        if not ran:
            window['out'].print('{}: Starting API verification.'.format(datetime.datetime.now().strftime("%H:%M:%S")))
            window.Refresh()

            window['out'].print('{}: Collection OTUs without species level identification and high similarity.'.format(datetime.datetime.now().strftime("%H:%M:%S")))
            window.Refresh()
            raw_data, data_to_check, seq_dict = extract_data(xlsx_path, fasta_path)

            if not raw_data.empty:
                ## start a HTML session
                window['out'].print('{}: Starting to query the API.'.format(datetime.datetime.now().strftime("%H:%M:%S")))
                window['out'].print('{}: Output will be routed to the terminal.'.format(datetime.datetime.now().strftime("%H:%M:%S")))
                window['out'].print('{}: This window will freeze in the meantime.'.format(datetime.datetime.now().strftime("%H:%M:%S")))
                window.Refresh()

                session = requests_html.HTMLSession()

                with tqdm_joblib(tqdm(desc="Calling API", total = len(list(seq_dict.items())))) as progress_bar:
                    result = Parallel(n_jobs = psutil.cpu_count())(delayed(request)(item, session) for item in list(seq_dict.items()))

                ## remove all hits that did not match
                result = [res for res in result if res != None]
                window['out'].print('{}: Collected {} additional species names.'.format(datetime.datetime.now().strftime("%H:%M:%S"), len(result)))
                window['out'].print('{}: Starting to update the dataset.'.format(datetime.datetime.now().strftime("%H:%M:%S")))
                window.Refresh()

                corrected_data = refresh_data(result, raw_data, data_to_check, session)

                window['out'].print('{}: Saving the corrected dataset.'.format(datetime.datetime.now().strftime("%H:%M:%S")))
                window.Refresh()

                ## save output
                wb = openpyxl.load_workbook(xlsx_path)
                writer = pd.ExcelWriter(xlsx_path, engine = 'openpyxl')
                writer.book = wb

                corrected_data.to_excel(writer, sheet_name = 'BOLDigger hit - API corrected', index = False)
                wb.save(xlsx_path)
                writer.close()

                window['out'].print('{}: Done. Close to continue.'.format(datetime.datetime.now().strftime("%H:%M:%S")))
                window.Refresh()

                ran = True
            else:
                window['out'].print('%s: No BOLDigger hits found. Please add these tophits first. Close to continue.' % datetime.datetime.now().strftime("%H:%M:%S"))
                window.Refresh()
                ran = True

        if event == None:
            break

    window.close()
