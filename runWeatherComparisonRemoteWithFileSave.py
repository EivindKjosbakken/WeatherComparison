#imports
import requests
from bs4 import BeautifulSoup
import time
from datetime import date
import requests
import datetime as dt
import schedule
import pymongo
import tweepy
import json
from os import path


API_KEY = 'NcyNNM5K7MOE8VNXLd8OAlJIh'
API_SECRET = 'yJu3LHHrN0RxyRT9Zuy8Uh6aZryqShJ6Yb2OaHaKNfSlliDwuf'
ACCESS_KEY = '524480388-Si4HsxqdcWwACIgRV2pXMqEZY7TDb7idlwfPXvVW'
ACCESS_SECRET = 'BjMqiNGIJG9oMKzw2iAQft87tUsaSYYaBiwvIMOpYlqRm'


def getSoup(url):
    response = requests.get(url=url)
    soup = BeautifulSoup(response.content, 'lxml')
    return soup

def getRainNext24HoursStorm(url):
    soup = getSoup(url)

    eachHourSpan = soup.find_all('tr', {'class' : 'DailyForecastRow_row__mFays'})

    #the headers for each span:
    # informationHeaders = ["Time", "Temperature", "Feels like temp", "Precipitation", "Air humidity", "Wind speed"]

    result = []

    for i in range(len(eachHourSpan)):
        temp = []
        for idx, ele in enumerate(eachHourSpan[i]):
            # print(informationHeaders[idx], "->", ele.text)
            if (idx == 0):
                if (len(ele.text) >= 3): #do not want anything that is over several hours, only specific hours, example where this hits is : "20-23"
                    return result
                temp.append(int(ele.text)) #convert time to int
            if (idx == 3):
                temp.append(float(ele.text.split(" ")[0].replace(",", "."))) #only want the number, not "mm", and want it as float, to convert to float it needs to have "." and not ","
        result.append(temp)

    return result

def getRainNext24HoursYr(url):

    response=requests.get(url, headers={"User-Agent":"oieivind@gmail.com sitename-TBD"})
    responseDict = response.json()

    responseDict["properties"]["timeseries"]

    result = [] #(time in norwegian time, rain in mm)

    for idx, row in enumerate(responseDict["properties"]["timeseries"]):
        if (idx >= 24): #don't need more than 24 hours
            break
        time = (int(row["time"][11:13])+1)%24 #[11:13] to only get hours, modulo 24 in case it surpasses midnight, +1 to convert from uk to norwegian time
        precipitation = row["data"]["next_1_hours"]["details"]["precipitation_amount"]
        result.append([time, precipitation])
    
    return result

def getResultsNext3Hours(stormUrl, yrUrl):
    stormRes = getRainNext24HoursStorm(stormUrl)
    yrRes = getRainNext24HoursYr(yrUrl)
    maxHour = max(stormRes[0][0], yrRes[0][0]) #need to sync the hours we are looking at

    stormPreds = []
    for time, precipitation in (stormRes):
        if (time >= maxHour):
            stormPreds.append((time,precipitation))
    yrPreds = []
    for time, precipitation in (yrRes):
        if (time >= maxHour):
            yrPreds.append((time,precipitation))

    #choose max 3 hours and convert to dictionaries
    stormPredsDict, yrPredsDict = dict(), dict()

    if (len(stormPreds) >= 3 and len(yrPreds) >= 3):
        for i in range(3):
            stormPredsDict[str(stormPreds[i][0])] = stormPreds[i][1]
            yrPredsDict[str(yrPreds[i][0])] = yrPreds[i][1]
        return stormPredsDict, yrPredsDict
    
    minLength = min(len(stormPreds), len(yrPreds))
    for i in range(minLength):
        stormPredsDict[str(stormPreds[i][0])] = stormPreds[i][1]
        yrPredsDict[str(yrPreds[i][0])] = yrPreds[i][1]
    return stormPredsDict, yrPredsDict

def getPrecipitationLast24Hours(url):
    soup = getSoup(url)
    
    eachHourSpan = soup.find_all('tr', {'class' : 'fluid-table__row'})

    #gets all spans for last 24 hours
    #cols: time, weather, min temp, maks temp, measured temp, precipitation mm, snowdepth, wind, most powerful gust of wind, air humidity
    cols = ["time", "weather", "min temp", "maks temp", "measured temp", "precipitation mm", "snowdepth", "wind", "most powerful gust of wind", "air humidity"]

    result = dict() #store results in hm for quick access
    for i in range(24):
        temp = []
        for idx, ele in enumerate(eachHourSpan[i]):
            # print(cols[idx], "->", ele.text)
            # print("\n\n")
            if (idx == 0): #time
                temp.append(int(ele.text))
            if (idx == 5): #precipitation mm
                temp.append(float(ele.text.replace(",", "."))) #convert from , to . to be able to convert string to float
        result[str(temp[0])] = temp[1]
    return result

def saveToDict(stormRes, yrRes, historicDataRes, location):
    #save to dict with time request was sent, and the results
    hm = dict()
    currentTime = dt.datetime.today()
    currentTime = dt.datetime.today()
    date_time = currentTime.strftime("%d/%m/%Y,%H:%M:%S") #must be in string format to save as key
    date, timeOfDay = date_time.split(",")
    hm = {"date": date, "timeOfDay": timeOfDay, "location": location, "storm": stormRes, "yr": yrRes, "historic": historicDataRes}
    return hm

def saveToFile(hm, filename = "weatherData.json"):
    if path.isfile(filename) is False:
        print("file does not exist, writing to file") 
        with open(filename, 'w') as json_file:
            json.dump([hm], json_file, 
                                indent=4,  
                                separators=(',',': '))
        json_file.close()
        return
    with open(filename) as fp:
        listObj = json.load(fp)

    #check if date already exists in object
    for obj in listObj:
        if (obj["date"] == hm["date"]):
            print("date already exists in file, not writing to file")
            return
    listObj.append(hm)
    with open(filename, 'w') as json_file:
        json.dump(listObj, json_file, 
                            indent=4,  
                            separators=(',',': '))
    
    json_file.close()
    print("saved to file")

def findAccuracyForYesterday(currDate, weatherData):
    todayDateString = currDate.strftime("%d/%m/%Y")
    yesterdayDate = currDate - dt.timedelta(days=1)
    yesterdayDateString = yesterdayDate.strftime("%d/%m/%Y")
    yesterdayRes, todayRes = None, None
    for day in weatherData:
        if (day["date"] == yesterdayDateString):
            yesterdayRes = day
        if (day["date"] == todayDateString):
            todayRes = day
    if (yesterdayRes is None or todayRes is None): #then we have no earlier info
        print("Have no earlier information. Also prints this if it works if it is at last available date")
        return 

    #now compare yr and storm, get accuracy for each hour they predicted

    yesterdayYrPreds = yesterdayRes["yr"]
    yesterdayStormPreds = yesterdayRes["storm"]
    yesterdayHistoricData = todayRes["historic"] #yesterday historic data is taken from today (since today has the true information)

    numCorrectYr = 0
    numCorrectStorm = 0

    for key in yesterdayYrPreds:
        yrPred = yesterdayYrPreds[key]
        stormPred = yesterdayStormPreds[key]
        historicData = yesterdayHistoricData[key]
        #give correct as binary, either there was rain or there was not rain
        if (yrPred > 0 and historicData > 0) or (yrPred == 0 and historicData == 0):
            numCorrectYr += 1
        if (stormPred > 0 and historicData > 0) or (stormPred == 0 and historicData == 0):
            numCorrectStorm += 1
    
    return numCorrectYr, numCorrectStorm, len(yesterdayYrPreds)

def getTodayTweetString(weatherData):
    currDate = dt.datetime.today()
    res  = findAccuracyForYesterday(currDate, weatherData)
    if (res is None):
        return
    numCorrectYr, numCorrectStorm, numTotal = res
    tweetString = (f"I går korrekte:\nYr: {numCorrectYr}/{numTotal}, Storm: {numCorrectStorm}/{numTotal}.\nI går presison -> Yr: {round(numCorrectYr*100/numTotal, 2)}%, Storm: {round(numCorrectStorm*100/numTotal, 2)}%")
    return tweetString

def findAllTimeAccuracy(weatherData): #find accuracy for all days in total
    currDate = dt.datetime.today()
    totCorrectYr = 0
    totCorrectStorm = 0
    totTotal = 0
    while True:
        res = findAccuracyForYesterday(currDate, weatherData)
        if (res is None):
            break
        numCorrectYr, numCorrectStorm, numTotal = res
        totCorrectYr += numCorrectYr
        totCorrectStorm += numCorrectStorm  
        totTotal += numTotal
        currDate = currDate - dt.timedelta(days=1)
    
    tweetString = (f"Totalt korrekte:\nYr: {totCorrectYr}/{totTotal}, Storm: {totCorrectStorm}/{totTotal}.\nTotal presisjon -> Yr: {round(totCorrectYr*100/totTotal, 2)}%, Storm: {round(totCorrectStorm*100/totTotal, 2)}%")
    return tweetString

def tweetResults(location, filename = "weatherData.json"):
    with open(filename) as json_file:
        weatherData = json.load(json_file)
    json_file.close()

    startString = f"Ser på antall timer Yr/Storm korrekt melder regn i {location} for timene kl 13, 14 og 15:"
    todayTweetString = getTodayTweetString(weatherData)
    if (todayTweetString is None):
        print("Lacking historical data, add one day prior to be able to check results")
        return 
    taggingString = " @storm_no @Meteorologene"
    totalTweetString = findAllTimeAccuracy(weatherData)

    totalString = startString + "\n\n" + todayTweetString + "\n\n" + totalTweetString + "\n\n" + taggingString
    
    auth = tweepy.OAuthHandler(API_KEY, API_SECRET)
    auth.set_access_token(ACCESS_KEY, ACCESS_SECRET)
    api = tweepy.API(auth)
    # api.update_status(totalString)
    print("TOTAL TWEET: \n\n", totalString)
    print("len av tweet: ", len(totalString))


def job():
    stormUrl = "https://www.storm.no/Bergen"
    yrUrl = "https://api.met.no/weatherapi/locationforecast/2.0/compact?lat=60.39&lon=5.32"
    historicDataUrl = "https://www.yr.no/nb/historikk/tabell/1-92416/Norge/Vestland/Bergen/Bergen?q=siste-24-timer"

    stormRes, yrRes = getResultsNext3Hours(stormUrl, yrUrl)
    historicRes = getPrecipitationLast24Hours(historicDataUrl)

    location = "Bergen"
    hm = saveToDict(stormRes, yrRes, historicRes, location)
    saveToFile(hm)
    print("result in hm: ")
    print(hm)
    tweetResults(location)


# job()
schedule.every().day.at("12:01").do(job)
while True:
    schedule.run_pending()
    time.sleep(1)
