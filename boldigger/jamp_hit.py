import openpyxl, datetime
import pandas as pd
import PySimpleGUI as sg

## function to return the threshold for an OTU dataframe, returns No Match for No Matches
## also returns a level to group by for later use
def get_threshold(df):
    threshold = df['Similarity'][0]

    if threshold == 'No Match':
        return 'No Match', None
    elif threshold >= 98:
        return 98, ['Genus', 'Species']
    elif threshold >= 95:
        return 95, ['Genus']
    elif threshold >= 90:
        return 90, ['Family']
    elif threshold >= 85:
        return 85, ['Order']
    else:
        return 50, ['Class']

## function to extract the data from the xlsx path and do some formatting
def get_data(xlsx_path):
    ## open excel file
    ## skip subspecies and process ID, rename 'You searched for to ID'
    data = pd.read_excel(xlsx_path, usecols = 'A:G,I:J')
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

    threshold, level = get_threshold(df)

    ## if no match simply return a nomatch df
    if threshold == 'No Match':
        return df.query("Species == 'No Match'").head(1)

    ## cut all values below the threshold
    otu_df = df.loc[df['Similarity'] >= threshold]

    ## group the data by level and count appearence
    out = pd.DataFrame({'count': otu_df.groupby(level, sort = False).size()}).reset_index()
    out = out.sort_values('count', ascending = False)
    out = out.iloc[0].tolist()

    ## find the hit in the otu dataframe
    if len(out) == 3:
        hit = otu_df.query("%s == '%s' and %s == '%s'" % (level[0], out[0], level[1], out[1])).head(1)
    else:
        hit = otu_df.query("%s == '%s'" % (level[0], out[0])).head(1)

    ## remove the placeholder
    hit = hit.replace('placeholder', '')

    ## define level to remove them from low level hits
    levels = ['Class', 'Order', 'Family', 'Genus', 'Species']

    ## return species level information if similarity is high enough
    ## else remove higher level information form output depending on level
    if threshold == 98:
        return hit
    else:
        hit = hit.assign(**{k: '' for k in levels[levels.index(level[0]) + 1:]})
        return hit

def save_results(xlsx_path, dataframe):

    ## open workbook to save to
    wb = openpyxl.load_workbook(xlsx_path)
    writer = pd.ExcelWriter(xlsx_path, engine = 'openpyxl')
    writer.book = wb

    ## close and save the writer
    dataframe.to_excel(writer, sheet_name = 'JAMP hit', index = False)
    writer.save()
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
