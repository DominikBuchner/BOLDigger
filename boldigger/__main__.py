import PySimpleGUI as sg
import pkgutil, json, ast, webbrowser, pkg_resources, os, sys
from boldigger import login, boldblast_coi, boldblast_its, boldblast_rbcl, additional_data
from boldigger import first_hit, jamp_hit, digger_sort
from contextlib import contextmanager
from johnnydep.lib import JohnnyDist

## function to supress standard out for Johnnydep
@contextmanager
def suppress_stdout():
    with open(os.devnull, "w") as devnull:
        old_stdout = sys.stdout
        sys.stdout = devnull
        try:
            yield
        finally:
            sys.stdout = old_stdout

## get most recent version with Johnnydep
with suppress_stdout():
    dist = JohnnyDist('boldigger')

## get image data for the GUI
logo = pkgutil.get_data(__name__, 'data/logo.png')
github = pkgutil.get_data(__name__, 'data/github.png')
userdata = ast.literal_eval(pkgutil.get_data(__name__, 'data/userdata').decode())
certs = pkg_resources.resource_filename(__name__, 'data/certs.pem')
version = pkg_resources.get_distribution('boldigger').version
with suppress_stdout():
    most_recent_version = dist.version_latest

## main function to handle the flow of boldigger
def main():
    ## defines a layout for the GUI
    layout =  [
              [sg.Image(data = logo, pad = (25, 0))],
              [sg.Frame(layout = [
              [sg.Text('Your results will be saved here')],
              [sg.Text('Output folder'), sg.InputText(size = (40, 1), do_not_clear = True, key = 'output_folder'), sg.FolderBrowse()]],
              title = 'Select an output folder')],
              [sg.Frame(layout = [
              [sg.Text('Username'), sg.InputText(userdata['username'], size = (25, 1), do_not_clear = True, key = 'username'),
              sg.Text('Password'), sg.InputText(userdata['password'], size = (25, 1), do_not_clear = True, password_char = '*', key = 'password'),
              sg.CB('Remember me', key = 'rem_pw', tooltip = 'This will save your userdata\non your computer without encryption!'),
              sg.Button('Login', key = 'login_check')]],
              title = 'User data')],
              [sg.Frame(layout = [
              [sg.Text('Select a database'), sg.Radio('COI', 'database', key = 'coi', default = True),
              sg.Radio('ITS', 'database', key = 'its'), sg.Radio('rbcL & matK', 'database', key = 'rbcl'),
              sg.Spin([i for i in range(1, 101)], initial_value = 100, size = (3, 1), key = 'batch_size'), sg.Text('Batch size')],
              [sg.Text('Select a fasta file'), sg.InputText(size = (40, 1), do_not_clear = True, key = 'fasta_path'), sg.FileBrowse(), sg.Button('Run', key = 'id_eng', button_color = ('white', 'red'))]],
              title = 'BOLD identification engine')],
              [sg.Frame(layout = [
              [sg.Text('Select a BOLDResults file'), sg.InputText(size = (40, 1), do_not_clear = True, key = 'resultpath'), sg.FileBrowse(), sg.Button('Run', key = 'add_data', button_color = ('white', 'red'))]],
              title = 'Search for additional data')],
              [sg.Frame(layout = [
              [sg.Text('Select a method to determine the top hit (BOLDigger method requires additional data)')],
              [sg.Radio('Use first hit', 'sort_method', key = 'firsthit', default = True), sg.Radio('JAMP Pipeline', 'sort_method', key = 'jamp'), sg.Radio('BOLDigger', 'sort_method', key = 'digger'), sg.Button('Run', key = 'tophit', button_color = ('white', 'red'))]],
              title = 'Add a list of top hits')],
              [sg.Button('Exit'), sg.Text('version: {}'.format(version)), sg.Button(image_data = github, key = 'github', pad = ((640, 0), 0))] #
              ]

    window = sg.Window('BOLDigger', layout)
    ## check for update once on startup
    update_check = True

    ## main loop
    while True:
        event, values = window.read(timeout = 100)

        ## check version on startup
        if version != most_recent_version and update_check:
            update_check = False
            sg.popup('A new version of BOLDigger is available.\nPlease close the application and update.', title = 'Update')

        if event == None or event == 'Exit':
            break
        if event == 'login_check':
            session = login.login(values['username'], values['password'], certs, values['rem_pw'])

        ## search engine for coi
        if event == 'id_eng' and values['coi']:
            if values['fasta_path'] == '' or values['output_folder'] == '':
                sg.popup('Please select input file and output folder.')
            elif 'session' in locals():
                window.Hide()
                boldblast_coi.main(session, values['fasta_path'], values['output_folder'], values['batch_size'])
                window.UnHide()
            else:
                sg.popup('Please log in first.')

        ## search engine for its
        if event == 'id_eng' and values['its']:
            if values['fasta_path'] == '' or values['output_folder'] == '':
                sg.popup('Please select input file and output folder.')
            elif 'session' in locals():
                window.Hide()
                boldblast_its.main(session, values['fasta_path'], values['output_folder'], values['batch_size'])
                window.UnHide()
            else:
                sg.popup('Please log in first.')

        ## search engine for rbcl
        if event == 'id_eng' and values['rbcl']:
            if values['fasta_path'] == '' or values['output_folder'] == '':
                sg.popup('Please select input file and output folder.')
            elif 'session' in locals():
                window.hide()
                boldblast_rbcl.main(session, values['fasta_path'], values['output_folder'], values['batch_size'])
                window.UnHide()
            else:
                sg.popup('Please log in first.')

        ## additional data code
        if event == 'add_data' and values['resultpath'] == '':
            sg.popup('Please select a resultfile first.')
        if event == 'add_data' and values['resultpath'] != '':
            window.Hide()
            additional_data.main(values['resultpath'])
            window.UnHide()

        ## addint top hits code
        if event == 'tophit':
            if values['resultpath'] == '':
                sg.popup('Please select a resultfile first.')
            elif values['firsthit']:
                window.Hide()
                first_hit.main(values['resultpath'])
                window.UnHide()
            elif values['jamp']:
                window.Hide()
                jamp_hit.main(values['resultpath'])
                window.UnHide()
            elif values['digger']:
                window.Hide()
                digger_sort.main(values['resultpath'])
                window.UnHide()

        if event == 'github':
            webbrowser.open('https://github.com/DominikBuchner/BOLDigger')


    window.Close()
## run only if called as a toplevel script
if __name__ == "__main__":
    main()
