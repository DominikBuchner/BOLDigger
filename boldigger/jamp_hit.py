import openpyxl, datetime
import pandas as pd
import PySimpleGUI as sg
import numpy as np

## function to return the threshold for an OTU dataframe, returns No Match for No Matches
## also returns a level to group by for later use
def get_threshold(df):
    threshold = df['Similarity'][0]

    if threshold == 'placeholder':
        return 'No Match', None
    elif threshold >= 98:
        return 98, 'Species'
    elif threshold >= 95:
        return 95, 'Genus'
    elif threshold >= 90:
        return 90, 'Family'
    elif threshold >= 85:
        return 85, 'Order'
    else:
        return 50, 'Class'

## function to move the treshold one level up if no hit is found, also return the new tax level
def move_threshold_up(thresh):
    thresholds = [98, 95, 90, 85, 50]
    levels = ['Species', 'Genus', 'Family', 'Order', 'Class']
    return thresholds[thresholds.index(thresh) + 1], levels[thresholds.index(thresh) + 1]

## function to extract the data from the xlsx path and do some formatting
def get_data(xlsx_path):
    ## open excel file
    ## skip subspecies and process ID, rename 'You searched for to ID'
    data = pd.read_excel(xlsx_path, usecols = 'A:G,I:J', engine = 'openpyxl')
    data = data.rename(index = str, columns={'You searched for': 'ID'})

    ## check file format
    if list(data.columns.values)[1] != 'Phylum':
        return 'Wrong file'

    ## slice the dataframe in one df for each otu and reset the indexes on resultig dfs
    ## rename id after first value in the ID column e.g. > OTUXX
    slices = [data.iloc[i : i + 20] for i in range(0, len(data), 20)]
    slices = [otu.reset_index(drop = True) for otu in slices]
    slices = [otu.assign(ID = otu.iloc[0][0]) for otu in slices]

    return slices

## accepts a OTU dataframe and returns the JAMP hit as df
def jamp_hit(df):
    ## put a placeholder to all empty cells
    df = df.fillna('placeholder')

    ## get the threshold and level to look for
    threshold, level = get_threshold(df)

    ## if no match simply return a nomatch df
    if threshold == 'No Match':
        return df.query("Species == 'No Match'").head(1).replace('placeholder', np.nan)

    ## loop through thresholds and levels until a true hit is found
    while True:
        ## cut all values below the threshold
        out_df = df.copy()
        out_df = out_df.loc[out_df['Similarity'] >= threshold]

        ## group the data by level and count appearence
        out_df = pd.DataFrame({'count': out_df.groupby(['Phylum', 'Class', 'Order', 'Family', 'Genus', 'Species'], sort = False).size()}).reset_index()
        out_df = out_df.sort_values('count', ascending = False)

        ## replace placeholder to to drop possible np.nan values at the designated level that mask real hits
        ## if already at the highest level 'class' there is nothing to drop, then continue
        out_df = out_df.replace('placeholder', np.nan)
        if level != 'Class':
            out_df = out_df.dropna(subset = [level])
        out_df = out_df.fillna('placeholder')

        ## if no hit remains after removing np.nans, move up one level
        if out_df.empty:
            threshold, level = move_threshold_up(threshold)
            continue
        ## else return the top hit
        else:
            hit = out_df.head(1)
            hit = df.query("Class == '{}' and Order == '{}' and Family == '{}' and Genus == '{}' and Species == '{}'".format(
                           hit['Class'].item(), hit['Order'].item(), hit['Family'].item(), hit['Genus'].item(), hit['Species'].item())).head(1)
            break

    ## remove the placeholder
    hit = hit.replace('placeholder', np.nan)

    ## define level to remove them from low level hits
    levels = ['Class', 'Order', 'Family', 'Genus', 'Species']

    ## return species level information if similarity is high enough
    ## else remove higher level information form output depending on level
    if threshold == 98:
        return hit
    else:
        hit = hit.assign(**{k: '' for k in levels[levels.index(level) + 1:]})
        return hit

def save_results(xlsx_path, dataframe):

    ## open workbook to save to
    wb = openpyxl.load_workbook(xlsx_path)
    writer = pd.ExcelWriter(xlsx_path, engine = 'openpyxl')
    writer.book = wb

    ## close and save the writer
    dataframe.to_excel(writer, sheet_name = 'JAMP hit', index = False)
    wb.save(xlsx_path)
    writer.close()

## main function
def main(xlsx_path):

    ## define a layout for the new window
    layout = [
    [sg.Multiline(size = (50, 10), key = 'out', autoscroll = True)]
    ]

    ## run the sorting loop only once. After that only run event loop
    window = sg.Window('Adding top hits with JAMP method', layout)
    ran = False

    while True:

        event, values = window.read(timeout = 100)

        if not ran:

            window['out'].print('%s: Opening resultfile.' % datetime.datetime.now().strftime("%H:%M:%S"))
            window.Refresh()
            otu_dfs = get_data(xlsx_path)

            if otu_dfs != 'Wrong file':
                window['out'].print('%s: Filtering data.' % datetime.datetime.now().strftime("%H:%M:%S"))
                window.Refresh()
                jamp_hits = [jamp_hit(otu) for otu in otu_dfs]
                output = pd.concat(jamp_hits).reset_index(drop = True)

                window['out'].print('%s: Saving result to new tab.' % datetime.datetime.now().strftime("%H:%M:%S"))
                window.Refresh()
                save_results(xlsx_path, output)

                window['out'].print('%s: Done. Close to continue.' % datetime.datetime.now().strftime("%H:%M:%S"))
                window.Refresh()

                ran = True
            else:
                window['out'].print('%s: Wrong file format. Close to continue.' % datetime.datetime.now().strftime("%H:%M:%S"))
                window.Refresh()

                ran = True

        if event == None:
            break

    window.Close()
