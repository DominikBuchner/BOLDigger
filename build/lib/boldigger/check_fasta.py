import PySimpleGUI as sg
import datetime
from pathlib import Path
from Bio import SeqIO
from Bio.Seq import Seq

## function to check a fasta file for valid characters and correct ID lengths
def fasta_check(fasta_path):
    ## list of all valid chars that are accepted by the BOLD IDS
    valid_chars = ['A', 'C', 'G', 'T', 'M', 'R', 'W', 'S', 'Y', 'K', 'V', 'H', 'D', 'B', 'X', 'N']

    ## set values in case header and or sequences should be changed
    ## in case of error count for user output
    headers = [0, False]
    seqs = [0, False]

    ## save the output here
    output = []

    ## go through the file and check all sequence headers and sequences
    for record in SeqIO.parse(fasta_path, 'fasta'):
        ## trim records headers in case they are too long
        if len(record.id) >= 99:
            record.id = record.id[:99]
            headers[0] += 1
            headers[1] = 'True'


        ## loop through the sequence and do inplace changes with N if needed
        if len([c for c in record.seq.upper() if c in valid_chars]) != len(record.seq):
            record.seq = Seq(''.join(c if c in valid_chars else 'N' for c in record.seq))
            seqs[0] += 1
            seqs[1] = 'True'

        ## append the corrected record to the output, overwrite name and description
        record.name = ''
        record.description = ''

        output.append(record)
    ## find out name of file and extension to create an output path
    name, ext = Path(fasta_path).stem, Path(fasta_path).suffix
    output_name = '{}_with_modifications{}'.format(name, ext)
    output_path = Path(fasta_path).parents[0].joinpath(output_name)

    ## if changes are done, write modified output
    if headers[1] or seqs[1]:
        with open(output_path, 'w') as output_handle:
            SeqIO.write(output, output_path, 'fasta-2line')

    return headers, seqs, output_name

## main function to control GUI and flow
def main(fasta_path):

    ## define a layout for the new window
    layout = [
    [sg.Multiline(size = (50, 10), key = 'out', autoscroll = True)]
    ]

    ## run the download loop only once. After that only run event loop
    window = sg.Window('Fasta check', layout)
    ran = False

    ## main loop
    while True:

        event, values = window.read(timeout = 100)

        if not ran:
            window['out'].print('%s: Opening fasta file.' % datetime.datetime.now().strftime("%H:%M:%S"))
            window.Refresh()

            ## run first hit function
            window['out'].print('%s: Checking headers and sequences.' % datetime.datetime.now().strftime("%H:%M:%S"))
            window.Refresh()
            headers, seqs, output_name = fasta_check(fasta_path)

            ## ## give output to the user
            if headers[1]:
                window['out'].print('{}: {} invalid header(s) were found.'.format(datetime.datetime.now().strftime("%H:%M:%S"), headers[0]))
                window.Refresh()

            if seqs[1]:
                window['out'].print('{}: {} invalid sequence(s) were found.'.format(datetime.datetime.now().strftime("%H:%M:%S"), seqs[0]))
                window.Refresh()

            if headers[1] or seqs[1]:
                window['out'].print('{}: A correctly formatted copy of your fasta file was saved as {}. You can use this to run BOLDigger.'.format(datetime.datetime.now().strftime("%H:%M:%S"), output_name))
                window.Refresh()
            else:
                window['out'].print('{}: Your fasta file looks fine. You can run BOLDigger.'.format(datetime.datetime.now().strftime("%H:%M:%S"), output_name))
                window.Refresh()

            ran = True

        if event == None:
            break

    window.Close()
