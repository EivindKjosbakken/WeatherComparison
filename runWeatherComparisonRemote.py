#imports
import requests
from bs4 import BeautifulSoup
import time
from datetime import date
import requests
import datetime as dt
import schedule
import pymongo


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

	result = [] #(time in UK time, rain in mm)

	for idx, row in enumerate(responseDict["properties"]["timeseries"]):
		if (idx >= 24): #don't need more than 24 hours
			break
		time = row["time"]
		precipitation = row["data"]["next_1_hours"]["details"]["precipitation_amount"]
		result.append([time, precipitation])

	#convert the time to norwegian time and only the hours
	for idx, row in enumerate(result):
		time = row[0]
		timeInHours = int(time[11:13])+1
		result[idx][0] = timeInHours
	
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

	if (len(stormPreds) >= 3 and len(yrPreds) >= 3):
		return stormPreds[:3], yrPreds[:3]
	
	minLength = min(len(stormPreds), len(yrPreds))
	return stormPreds[:minLength], yrPreds[:minLength]

def saveToDict(stormRes, yrRes):
    #save to dict with time request was sent, and the results
	hm = dict()
	currentTime = dt.datetime.today()
	date_time = currentTime.strftime("%m/%d/%Y, %H:%M:%S") #must have time in string format to save as key
	resultsHm = {"storm": stormRes, "yr": yrRes}
	hm[date_time] = resultsHm
	return hm

def saveToDB(hm):
	mongo_client = pymongo.MongoClient("mongodb://127.0.0.1:27017/?directConnection=true&serverSelectionTimeoutMS=2000&appName=mongosh+1.7.1")
	database = mongo_client["weatherComparisonDB"]
	weatherData = database["weatherData"]
	weatherData.insert_one(hm)


def job():
	stormUrl = "https://www.storm.no/Bergen"
	yrUrl = "https://api.met.no/weatherapi/locationforecast/2.0/compact?lat=60.39&lon=5.32"

	stormRes, yrRes = getResultsNext3Hours(stormUrl, yrUrl)
	hm = saveToDict(stormRes, yrRes)
	saveToDB(hm)
	print("result in hm: ")
	print(hm)


schedule.every().day.at("12:00").do(job)
while True:
    schedule.run_pending()
    time.sleep(1)
