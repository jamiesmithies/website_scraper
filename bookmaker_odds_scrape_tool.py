#!/usr/bin/env python
# coding: utf-8

##  This module is designed to scrape football match betting odds from a website called oddsportal.com
##  It reads in football match fixtures from a spreadsheet and collects the odds for each fixture
##  Three types of betting odds are collected; win prices, over/under goals prices, and asian handicap prices
##  Data is scraped using Selenium to simulate a web driver, and BeautifulSoup to parse the data

# Initialise & setup
from bs4 import BeautifulSoup
import re
from urllib.request import urlparse
from selenium import webdriver
import pandas as pd
import time
import os

BASE_DIR = os.getcwd()

def import_excel(f_name, sheet_name, cols):
# imports archived odds table from master spreadsheet
# table slimmed down to only have games which require market odds to be extracted
    df = pd.read_excel(BASE_DIR + "/" + f_name,
                      sheet_name = sheet_name,
                      header = 0,
                      index_col = 0,
                      convert_float = True,
                      usecols = cols)
    #     if no value, change to 0. Only keep rows which are 0, i.e. which need market prices collected
    df = df[df['Home'].notna()]
    df['mkt_line'].fillna(0,inplace = True) 
    df = df[df["mkt_line"] == 0]
    
    #     add fixture column combining home and away
    df.insert(2,column = "Fixture", value = df['Home']+ " - " + df['Away'])

    return df


def initialise_driver(): 
# sets up selenium web driver

    link = 'https://www.oddsportal.com/soccer/sweden/allsvenskan-women/results/'
    linklog = 'https://www.oddsportal.com/login/'
    driver = webdriver.Chrome('/Users/jamiesmithies/documents/Python/chromedriver')
    driver.get(linklog)

    USERNAME = "jamiesmithies"
    PASSWORD = "***"

    login = driver.find_element_by_xpath("//*[@id='login-username1']").send_keys(USERNAME)
    password = driver.find_element_by_xpath("//*[@id='login-password1']").send_keys(PASSWORD)
    submit = driver.find_element_by_xpath("//*[@id='col-content']/div[3]/div/form/div[3]/button/span/span").click()
    driver.get(link)

    res = driver.execute_script("return document.documentElement.outerHTML")
    soup = BeautifulSoup(res,'lxml')
    host = urlparse(link)[1]
    return (soup, host, driver)


def get_game_urls(soup, host):
#get url links for each game

    game_urls = []
    t = soup.find('table', class_ = "table-main")
    for tr in t.find_all('tr'):
        td = tr.find('td',class_= "name table-participant")
        if td:
            a = td.find('a', href = True)['href']
            game_urls.append("https://"+ host + a)


def get_price(tb, price_type, h):
#     Find the kick-off price of book makers. "AsianOdds" is the preferred bookie price to extract.
#     If not available, next best is "188BET" etc.

    #     get list of all bookies offering odds
    ancs = []
    for a in tb.find_all('a', class_ = "name"):
        ancs.append(a.text)
    
    #     List of preferred book makers
    bookies = ["Asianodds","188BET","Pinnacle","bet365","Unibet","Marathonbet"]
    for book in bookies:     
        if book in ancs:
            price_type(tb, df, h, book)
            b_found = True
            continue #if preferred book maker is found, exit loop as don't need to search for the next best
    if not b_found:
        print(h + " has found no prices")


def get_asia(tb, df, h, Book): #feeding in web page table, dataframe, fixture and bookie
#   get asian handicap prices
#   Bookie prices include an 'overround', meaning the sum of the probabilities add up to more than 100%.
#   Therefore, prices are 'demarginated'

    for tr in tb.find_all('tr'):
        a = tr.find('a', class_= "name")
        if a:
            if a.text == Book:
                #marginated prices
                marg_home = float(tr.find_all('td', class_ = True)[1].text)
                marg_away = float(tr.find_all('td', class_ = True)[2].text)
                
                #demarginated prices
                df.loc[df.Fixture == h, "mkt_line"] = tr.find_all('td', class_ = True)[0].text
                df.loc[df.Fixture == h, "mkt_h"] = (1/marg_home + 1/marg_away) * marg_home
                df.loc[df.Fixture == h, "mkt_a"] = (1/marg_home + 1/marg_away) * marg_away
    return df    


# MAIN
df = import_excel("xGData.xlsx", "Extract_Market", "A:F")
soup, host, driver = initialise_driver()
game_urls = get_game_urls(soup, host)

for game_url in game_urls:
    url = game_url + "#ah;2" #asianhandicap extension 
    driver.get(url)
    time.sleep(1)
    res = driver.execute_script("return document.documentElement.outerHTML")
    soup = BeautifulSoup(res,'lxml')  
    h = soup.find('h1').text
    # if fixture not required, go to next game
    if df.loc[df.Fixture == h].empty: 
        continue 
    divs = soup.find('div', id = "odds-data-table")

    
#     for each asian line
#     Find asian line which has both teams as close to evens (0.5 probability) as possible.
#     Closer to 0.5 probability the smaller the error. line which has smallest total 
#     error will be true asian line
    true_line_error = 2
    for i, div in enumerate(divs.find_all('div', class_ = "table-container")):
        #         all relevent rows have anchor tag
        a = div.find('a', href = "")
        if a:
            home_price = div.find_all('span', class_ = "avg chunk-odd nowrp")[1].text
            away_price = div.find_all('span', class_ = "avg chunk-odd nowrp")[0].text
            if (home_price!= '') & (away_price != ''):
                home_probability = 1/float(home_price)
                away_probability = 1/float(away_price)
                error = abs(home_probability - 0.5) + abs(away_probability - 0.5)
                if error < true_line_error:
                    true_line_error = error
                    #place holder for row of true line
                    elem = driver.find_element_by_xpath('//*[@id="odds-data-table"]/div[' + str(i+1) + ']/div/strong/a')

                
#     click on 'true' asian line and get odds
    t = None
    while (t == None):
#         while loop ensures web driver responds to element click and finds t
        element = elem
        element.click()
        time.sleep(1)
        res = driver.execute_script("return document.documentElement.outerHTML")
        soup = BeautifulSoup(res,'lxml')
        t = soup.find('table', class_ = "table-main detail-odds sortable")
    tb = t.find('tbody')
    print(get_price(tb,get_asia,h))


#   export results to excel file
df.to_excel(BASE_DIR + "/" + "Market Closing Odds.xlsx")
