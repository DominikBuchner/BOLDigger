import openpyxl, datetime
import pandas as pd
import PySimpleGUI as sg
from boldigger.jamp_hit import get_data, jamp_hit, get_threshold


## function to get the full dataset including metadata
def get_full_data(path):
        ## open excel file
        ## skip subspecies and process ID, rename 'You searched for to ID'
        full_data = pd.read_excel(path, usecols = 'A:G,I:T')
        full_data = full_data.rename(index = str, columns={'You searched for': 'ID'})

        ## check file format, check if metadata was added
        if list(full_data.columns.values)[1] != 'Phylum':
            return 'Wrong file'
        if len(full_data.columns.values) != 19:
            return 'No metadata'
        ## slice the dataframe in one df for each otu and reset the indexes on resultig dfs
        ## rename id after first value in the ID column e.g. > OTUXX
        slices = [full_data.iloc[i : i + 20] for i in range(0, len(full_data), 20)]
        slices = [otu.reset_index(drop = True) for otu in slices]
        slices = [otu.assign(ID = otu.iloc[0][0]) for otu in slices]

        return slices

## function to add flags, jamp hits are generated the with the jamp_hit module
def add_flags(jamp_hit, full_data_df):

    ## add a placeholder to all empty cells
    full_data_df = full_data_df.fillna('placeholder')

    ## get threshold and leven
    threshold, level = get_threshold(full_data_df)

    ## return NONE if NoMatch df is the input
    if threshold == 'No Match':
        return ''

    ## cut all values below the threshold
    otu_df = full_data_df.loc[full_data_df['Similarity'] >= threshold]

    ## remove all data below the threshold
    ## define level to remove them from low level hits
    levels = ['Class', 'Order', 'Family', 'Genus', 'Species']

    if threshold != 98:
        otu_df = otu_df.assign(**{k: '' for k in levels[levels.index(level[0]) + 1:]})

    ## group the data by level and count appearence
    out = pd.DataFrame({'count': otu_df.groupby(level, sort = False).size()}).reset_index()
    out = out.sort_values('count', ascending = False)
    out = out.iloc[0].tolist()

    ## find the hit in the otu dataframe
    if len(out) == 3:
        hit = otu_df.query("%s == '%s' and %s == '%s'" % (level[0], out[0], level[1], out[1]))
    else:
        hit = otu_df.query("%s == '%s'" % (level[0], out[0]))

    flags = [False, False, False, False]
    ## FLAG 1: Reverse BIN taxonomy detected ##
    id_method = hit['Identification Method']

    ## flags in the identication method column are "BOLD ID-Engine", "BIN Taxonomy Match" and "Tree based identification"
    if id_method.str.startswith('BOLD').any() or id_method.str.startswith('ID').any() or id_method.str.startswith('Tree').any():
        flags[0] = True

    ## FLAG 2: More than 1 taxonomic group above the selected threshold
    ## group the data by level and count appearence, get a copy of the original data first
    out = pd.DataFrame({'count': otu_df.groupby(level, sort = False).size()}).reset_index()
    if len(out) > 1:
        flags[1] = True

    ## FLAG 3: all entrys for the selected hit are private
    if hit['Status'].isin(['Private', 'Early-Release']).all():
        flags[2] = True

    ## FLAG 4: the top hit represents only one hit of the top 20 list
    if len(hit) == 1:
        flags[3] = True

    ## replace bool values by numbers (flag values) so the output is better to read
    flags = ' '.join([str(i + 1) if flags[i] else ' ' for i in range(len(flags))])

    return flags

## function to save the results to a new sheet
def save_results(xlsx_path, dataframe):

    ## open workbook to save to
    wb = openpyxl.load_workbook(xlsx_path)
    writer = pd.ExcelWriter(xlsx_path, engine = 'openpyxl')
    writer.book = wb

    ## close and save the writer
    dataframe.to_excel(writer, sheet_name = 'BOLDigger hit', index = False)
    writer.save()
    writer.close()

def main(xlsx_path):

    ## define a layout for the new window
    layout = [
    [sg.Multiline(size = (50, 10), key = 'out', autoscroll = True)]
    ]

    ## run the sorting loop only once. After that only run event loop
    window = sg.Window('Adding top hits with BOLDigger method', layout)
    ran = False

    while True:

        event, values = window.read(timeout = 100)

        if not ran:
            ## determine hits the JAMP way
            window['out'].print('%s: Opening resultfile.' % datetime.datetime.now().strftime("%H:%M:%S"))
            window.Refresh()
            otu_dfs = get_data(xlsx_path)

            if otu_dfs != 'Wrong file':
                window['out'].print('%s: Filtering data for JAMP hits.' % datetime.datetime.now().strftime("%H:%M:%S"))
                window.Refresh()
                jamp_hits = [jamp_hit(otu) for otu in otu_dfs]

                ## get the full data for flagging
                window['out'].print('%s: Extracting additional data.' % datetime.datetime.now().strftime("%H:%M:%S"))
                window.Refresh()
                full_data = get_full_data(xlsx_path)

                if get_full_data(xlsx_path) != 'No metadata':
                    ## flag every hit
                    window['out'].print('%s: Flagging the hits.' % datetime.datetime.now().strftime("%H:%M:%S"))
                    window.Refresh()
                    for i in range(len(jamp_hits)):
                        jamp_hits[i]['Flags'] = add_flags(jamp_hits[i], full_data[i])

                    ## save results
                    window['out'].print('%s: Saving result to new tab.' % datetime.datetime.now().strftime("%H:%M:%S"))
                    window.Refresh()
                    output = pd.concat(jamp_hits).reset_index(drop = True)
                    save_results(xlsx_path, output)

                    window['out'].print('%s: Done. Close to continue.' % datetime.datetime.now().strftime("%H:%M:%S"))
                    window.Refresh()

                    ran = True

                else:
                    window['out'].print('%s: No additional data found. Run again after the additional data download. Close to continue.' % datetime.datetime.now().strftime("%H:%M:%S"))
                    window.Refresh()
                    ran = True

            else:
                window['out'].print('%s: Wrong file format. Close to continue.' % datetime.datetime.now().strftime("%H:%M:%S"))
                window.Refresh()
                ran = True

        if event == None:
            break

    window.Close()
