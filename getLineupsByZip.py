from tvMediaApi_dev import TvMedia
import config
import sys
api = TvMedia(config.APIKEY,config.BASE_URL)



zip = sys.argv[1] or 606012

print ""
print "These are the lineups for the zip:  ", zip
print ""

try:
	for i in api.lineups(zip):
		print i['providerName'],i['lineupID'],i['serviceArea']
except Exception as e:
	print "The Following error occured  ",e.args
