import requests_html, json, os
import PySimpleGUI as sg
from bs4 import BeautifulSoup as BSoup

## function to login to bold
def login(username, password, certificate, remember = False):
    ## start a new html session
    session = requests_html.HTMLSession(verify = certificate)

    ## data to push into the post request
    data = {
    'name': username,
    'password': password,
    'destination': 'MAS_Management_UserConsole',
    'loginType': ''
    }

    ## send a post request to log into boldsystems.org
    session.post('https://boldsystems.org/index.php/Login', data = data)

    ## test if the login was successfull
    url = session.get('https://boldsystems.org/')
    soup = BSoup(url.text, 'html.parser')
    content = soup.find(class_ = 'site-navigation nav navbar-nav')
    tags = content.find_all('a')
    if tags[5].text != 'Log out':
        sg.popup('Unable to login.\nPlease check your userdata.')
    else:
        sg.popup('Login successful.')
        ## save userdata only if login is successful and mark is set
        if remember:
            userdata = {"username": username, "password": password}
            abs_path = os.path.dirname(__file__)
            rel_path = os.path.join(abs_path, 'data/userdata')
            json.dump(userdata, open(rel_path, 'w'))

        ## return the session, not neccessary for this check but
        ## useful if you want to do other things with the login
        return session
