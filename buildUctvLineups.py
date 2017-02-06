#builds lineups based on lineup ids given in config.lineups. Caution. This will erase all previous lineups from db

import sqlite3
from tvMediaApi_dev import TvMedia
import config

conn = sqlite3.connect(config.DATABASE)
conn.row_factory = sqlite3.Row
c = conn.cursor()


lineupList = config.LINEUPS
api = TvMedia(config.APIKEY,config.BASE_URL)

for i in lineupList:
    print i

availableLineups = [api.lineup_details(id) for id in lineupList]

# c.execute('DELETE FROM uctvLineups')

# conn.commit()

for lineup in availableLineups:
    if lineup:
     
        for i in lineup['stations']:
            print lineup['lineupID'],lineup['providerName'],i['channelNumber'],i['name'],i['stationID']

            c.execute('''INSERT INTO uctvLineups(lineupID,providerName,channelNumber,channelName,stationID)
                    VALUES (?,?,?,?,?)''',(lineup['lineupID'],lineup['providerName'],i['channelNumber'],i['name'],i['stationID']))


conn.commit()





    


