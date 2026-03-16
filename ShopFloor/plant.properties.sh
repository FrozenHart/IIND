#!/usr/bin/sh

echo "
# This file is part of ShopFloorSimulator.
# 
# ShopFloorSimulator is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# ShopFloorSimulator is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# You should have received a copy of the GNU General Public License
# along with ShopFloorSimulator.  If not, see <http://www.gnu.org/licenses/>.


#### Para gravar simulações...
####  java -jar sfs.jar --record teste1
####  java -jar sfs.jar --playback teste1


#### Imprimir ficheiro com os ids dos sensores todos.
####  java -jar sfs.jar --map ficheiro.txt
####  java -jar sfs.jar --csv teste.csv




#Size of factory in meters
configuration.width = 20
configuration.height = 44

#Floor color
floor.color = 55AA33

#How many meters one pixel represents
configuration.pixelsize = 0.05
#Block size in meters
configuration.blocksize = 1

#Radius of conveyor middle sensors in meters
configuration.sensorradius = 0.5

#Miliseconds between each simulation step
configuration.simulationtime = 20

#Miliseconds before error occurs when forcing
configuration.errortime = 2000

#Miliseconds before piece on the floor disappears
configuration.floortime = 2000

#Conveyor speed in meters/second
configuration.conveyorspeed = 4
configuration.conveyorspeeddelta = 0

#Rotator rotation speed in degrees/second
configuration.rotationspeed = 180

#Pusher speed in meters/second
configuration.pushspeed = 1

#Machine tool rotation speed in degrees/second
configuration.toolrotationspeed = 4

#Machine tool move speed in meters/second
configuration.toolmovespeed = 0.05

#Modbus Port
configuration.port = 5502
#Set to true if you want to use address 127.0.0.1
configuration.loopback = true
#configuration.loopback = false

#Blocktypes
"
Brown="8B4513"
Red='FF0000'
Orange='F88017'
Yellow='FFFF00'
Green='00FF00'
Blue='1E90FF'
Violet='FF00FF'
Grey='888888'
White='FFFFFF'
LightBlue='8EF6FF'
OldPink='FFB3B3'
echo "

blocktype.1.name = Wood
blocktype.1.color = $Brown
blocktype.1.shape = rounded
#blocktype.1.shape = circle
#blocktype.1.shape = square

blocktype.2.name = Metal
blocktype.2.color = $Blue
blocktype.2.shape = rounded

blocktype.3.name = RTopW
blocktype.3.color = $OldPink
blocktype.3.shape = circle

blocktype.4.name = STopW
blocktype.4.color = $OldPink
blocktype.4.shape = square

blocktype.5.name = LegW
blocktype.5.color = $OldPink
blocktype.5.shape = rounded

blocktype.6.name = RTopM
blocktype.6.color = $LightBlue
blocktype.6.shape = circle

blocktype.7.name = STopM
blocktype.7.color = $LightBlue
blocktype.7.shape = square

blocktype.8.name = LegM
blocktype.8.color = $LightBlue
blocktype.8.shape = rounded

blocktype.9.name = RWW
blocktype.9.color = $Red
blocktype.9.shape = circle

blocktype.10.name = SWW
blocktype.10.color = $Orange
blocktype.10.shape = square

blocktype.11.name = RWM
blocktype.11.color = $Yellow
blocktype.11.shape = circle

blocktype.12.name = SWM
blocktype.12.color = $Green
blocktype.12.shape = square

blocktype.13.name = RMM
blocktype.13.color = $White
blocktype.13.shape = circle

blocktype.14.name = SMM
blocktype.14.color = $Grey
blocktype.14.shape = square



#################
#    Tools      #
#################
"

# Original Tool colours
#tool.1.color = 880000
#tool.2.color = 008800
#tool.3.color = 000088
#tool.4.color = FF8888
#tool.5.color = 88FF88
#tool.6.color = 8888FF
#tool.7.color = 008888
#tool.8.color = 880088
#tool.9.color = 888800

echo "

tool.1.color = $Brown
tool.2.color = $Red
tool.3.color = $Orange
tool.4.color = $Yellow
tool.5.color = $Green
tool.6.color = $Blue
tool.7.color = $Violet
tool.8.color = $White
tool.9.color = $Grey
tool.10.color = $LightBlue
tool.11.color = $OldPink



#Transformations (tool number, initial block type, final block type and duration in miliseconds)
"
TID=0

TID=$((TID+1))
echo "
transformation.$(( TID )).initial  = 1
transformation.$(( TID )).final    = 3
transformation.$(( TID )).tool     = 1
transformation.$(( TID )).duration = 30000
"
TID=$((TID+1))
echo "
transformation.$(( TID )).initial  = 1
transformation.$(( TID )).final    = 4
transformation.$(( TID )).tool     = 2
transformation.$(( TID )).duration = 20000
"
TID=$((TID+1))
echo "
transformation.$(( TID )).initial  = 1
transformation.$(( TID )).final    = 5
transformation.$(( TID )).tool     = 3
transformation.$(( TID )).duration = 10000
"
TID=$((TID+1))
echo "
transformation.$(( TID )).initial  = 1
transformation.$(( TID )).final    = 5
transformation.$(( TID )).tool     = 10
transformation.$(( TID )).duration = 30000
"
TID=$((TID+1))
echo "
transformation.$(( TID )).initial  = 2
transformation.$(( TID )).final    = 6
transformation.$(( TID )).tool     = 4
transformation.$(( TID )).duration = 35000
"
TID=$((TID+1))
echo "
transformation.$(( TID )).initial  = 2
transformation.$(( TID )).final    = 7
transformation.$(( TID )).tool     = 5
transformation.$(( TID )).duration = 25000
"
TID=$((TID+1))
echo "
transformation.$(( TID )).initial  = 2
transformation.$(( TID )).final    = 8
transformation.$(( TID )).tool     = 6
transformation.$(( TID )).duration = 20000
"
TID=$((TID+1))
echo "
transformation.$(( TID )).initial  = 2
transformation.$(( TID )).final    = 8
transformation.$(( TID )).tool     = 11
transformation.$(( TID )).duration = 40000
"
TID=$((TID+1))
echo "
transformation.$(( TID )).initial  = 3
transformation.$(( TID )).join     = 5,5
transformation.$(( TID )).final    = 9
transformation.$(( TID )).tool     = 8
transformation.$(( TID )).duration = 10000
"
TID=$((TID+1))
echo "
transformation.$(( TID )).initial  = 4
transformation.$(( TID )).join     = 5,5
transformation.$(( TID )).final    = 10
transformation.$(( TID )).tool     = 8
transformation.$(( TID )).duration = 10000
"
TID=$((TID+1))
echo "
transformation.$(( TID )).initial  = 3
transformation.$(( TID )).join     = 8,8
transformation.$(( TID )).final    = 11
transformation.$(( TID )).tool     = 9
transformation.$(( TID )).duration = 10000
"
TID=$((TID+1))
echo "
transformation.$(( TID )).initial  = 4
transformation.$(( TID )).join     = 8,8
transformation.$(( TID )).final    = 12
transformation.$(( TID )).tool     = 9
transformation.$(( TID )).duration = 10000
"
TID=$((TID+1))
echo "
transformation.$(( TID )).initial  = 6
transformation.$(( TID )).join     = 8,8
transformation.$(( TID )).final    = 13
transformation.$(( TID )).tool     = 8
transformation.$(( TID )).duration = 10000
"
TID=$((TID+1))
echo "
transformation.$(( TID )).initial  = 7
transformation.$(( TID )).join     = 8,8
transformation.$(( TID )).final    = 14
transformation.$(( TID )).tool     = 8
transformation.$(( TID )).duration = 10000
"

echo "
#########################################
#                                       #
#  Facility types: conveyor,            #
#                  rotator,             #
#                  rail,                #
#                  warehousein,         #
#                  warehouseout,        #
#                  machine              #
#                                       #
#########################################
"

ID=0
WID=0


Xoff=0
Yoff=1
echo "
#########################
# Plate Load            #
# Loading Docks         #
#########################
"

# a 'virtual' warehouse, representing the suppliers that will supply the raw materials
WID=$((WID+1))
echo "
warehouse.$(( WID )).show = false
warehouse.$(( WID )).length = 1
warehouse.$(( WID )).width = 1
warehouse.$(( WID )).orientation = horizontal
warehouse.$(( WID )).center.x = $(( $Xoff + 1 ))
warehouse.$(( WID )).center.y = $(( $Yoff + 1 ))
warehouse.$(( WID )).block.1.stock = 10000
warehouse.$(( WID )).block.2.stock = 10000
warehouse.$(( WID )).block.3.stock = 0
warehouse.$(( WID )).block.4.stock = 0
warehouse.$(( WID )).block.5.stock = 0
warehouse.$(( WID )).block.6.stock = 0
warehouse.$(( WID )).mintime = 0
warehouse.$(( WID )).maxtime = 0
"

ID=$((ID+1))
CID=0
# CID=$((CID+1))
echo "
facility.$(( ID )).type = warehouseout
facility.$(( ID )).length = 4
facility.$(( ID )).width = 2
facility.$(( ID )).orientation = vertical
facility.$(( ID )).center.x = $(( $Xoff + 2 ))
facility.$(( ID )).center.y = $(( $Yoff + 2 ))
facility.$(( ID )).warehouse = $(( WID ))
facility.$(( ID )).alias = Cin$(( CID ))
"
ID=$((ID+1))
CID=$((CID+1))
echo "
facility.$(( ID )).type = warehouseout
facility.$(( ID )).length = 4
facility.$(( ID )).width = 2
facility.$(( ID )).orientation = vertical
facility.$(( ID )).center.x = $(( $Xoff + 6 ))
facility.$(( ID )).center.y = $(( $Yoff + 2 ))
facility.$(( ID )).warehouse = $(( WID ))
facility.$(( ID )).alias = Cin$(( CID ))
"
ID=$((ID+1))
CID=$((CID+1))
echo "
facility.$(( ID )).type = warehouseout
facility.$(( ID )).length = 4
facility.$(( ID )).width = 2
facility.$(( ID )).orientation = vertical
facility.$(( ID )).center.x = $(( $Xoff + 10 ))
facility.$(( ID )).center.y = $(( $Yoff +  2 ))
facility.$(( ID )).warehouse = $(( WID ))
facility.$(( ID )).alias = Cin$(( CID ))
"
ID=$((ID+1))
CID=$((CID+1))
echo "
facility.$(( ID )).type = warehouseout
facility.$(( ID )).length = 4
facility.$(( ID )).width = 2
facility.$(( ID )).orientation = vertical
facility.$(( ID )).center.x = $(( $Xoff + 14 ))
facility.$(( ID )).center.y = $(( $Yoff +  2 ))
facility.$(( ID )).warehouse = $(( WID ))
facility.$(( ID )).alias = Cin$(( CID ))
"
ID=$((ID+1))
CID=$((CID+1))
echo "
facility.$(( ID )).type = warehouseout
facility.$(( ID )).length = 4
facility.$(( ID )).width = 2
facility.$(( ID )).orientation = vertical
facility.$(( ID )).center.x = $(( $Xoff + 18 ))
facility.$(( ID )).center.y = $(( $Yoff +  2 ))
facility.$(( ID )).warehouse = $(( WID ))
facility.$(( ID )).alias = Cin$(( CID ))
"



Xoff=0
Yoff=4
echo "
#########################
# Plate W1              #
# Warehouse             #
#########################
"
WID=$((WID+1))
echo "
warehouse.$(( WID )).show = true
warehouse.$(( WID )).length = 19
warehouse.$(( WID )).width = 2
warehouse.$(( WID )).orientation = horizontal
warehouse.$(( WID )).center.x = $(( $Xoff + 1 + 9 ))
warehouse.$(( WID )).center.y = $(( $Yoff +     4 ))
warehouse.$(( WID )).block.1.stock = 0
warehouse.$(( WID )).block.2.stock = 0
warehouse.$(( WID )).block.3.stock = 0
warehouse.$(( WID )).block.4.stock = 0
warehouse.$(( WID )).block.5.stock = 0
warehouse.$(( WID )).block.6.stock = 0
warehouse.$(( WID )).mintime = 100
warehouse.$(( WID )).maxtime = 100
"
ID=$((ID+1))
echo "
facility.$(( ID )).type = warehousein
facility.$(( ID )).length = 2
facility.$(( ID )).width = 2
facility.$(( ID )).orientation = vertical
facility.$(( ID )).center.x = $(( $Xoff + 2 ))
facility.$(( ID )).center.y = $(( $Yoff + 2 ))
facility.$(( ID )).warehouse = $(( WID ))
facility.$(( ID )).alias = AT1_in0
"
ID=$((ID+1))
echo "
facility.$(( ID )).type = warehousein
facility.$(( ID )).length = 2
facility.$(( ID )).width = 2
facility.$(( ID )).orientation = vertical
facility.$(( ID )).center.x = $(( $Xoff + 6 ))
facility.$(( ID )).center.y = $(( $Yoff + 2 ))
facility.$(( ID )).warehouse = $(( WID ))
facility.$(( ID )).alias = AT1_in1
"
ID=$((ID+1))
echo "
facility.$(( ID )).type = warehousein
facility.$(( ID )).length = 2
facility.$(( ID )).width = 2
facility.$(( ID )).orientation = vertical
facility.$(( ID )).center.x = $(( $Xoff + 10 ))
facility.$(( ID )).center.y = $(( $Yoff +  2 ))
facility.$(( ID )).warehouse = $(( WID ))
facility.$(( ID )).alias = AT1_in2
"
ID=$((ID+1))
echo "
facility.$(( ID )).type = warehousein
facility.$(( ID )).length = 2
facility.$(( ID )).width = 2
facility.$(( ID )).orientation = vertical
facility.$(( ID )).center.x = $(( $Xoff + 14 ))
facility.$(( ID )).center.y = $(( $Yoff +  2 ))
facility.$(( ID )).warehouse = $(( WID ))
facility.$(( ID )).alias = AT1_in3
"
ID=$((ID+1))
echo "
facility.$(( ID )).type = warehousein
facility.$(( ID )).length = 2
facility.$(( ID )).width = 2
facility.$(( ID )).orientation = vertical
facility.$(( ID )).center.x = $(( $Xoff + 18 ))
facility.$(( ID )).center.y = $(( $Yoff +  2 ))
facility.$(( ID )).warehouse = $(( WID ))
facility.$(( ID )).alias = AT1_in4
"
ID=$((ID+1))
echo "
facility.$(( ID )).type = warehousein
facility.$(( ID )).length = 2
facility.$(( ID )).width = 2
facility.$(( ID )).orientation = vertical
facility.$(( ID )).center.x = $(( $Xoff + 2 ))
facility.$(( ID )).center.y = $(( $Yoff + 6 ))
facility.$(( ID )).warehouse = $(( WID ))
facility.$(( ID )).alias = AT1_in5
"
ID=$((ID+1))
echo "
facility.$(( ID )).type = warehouseout
facility.$(( ID )).length = 2
facility.$(( ID )).width = 2
facility.$(( ID )).orientation = vertical
facility.$(( ID )).center.x = $(( $Xoff +  6 ))
facility.$(( ID )).center.y = $(( $Yoff +  6 ))
facility.$(( ID )).warehouse = $(( WID ))
facility.$(( ID )).alias = AT1_out1
"
ID=$((ID+1))
echo "
facility.$(( ID )).type = warehouseout
facility.$(( ID )).length = 2
facility.$(( ID )).width = 2
facility.$(( ID )).orientation = vertical
facility.$(( ID )).center.x = $(( $Xoff +  10 ))
facility.$(( ID )).center.y = $(( $Yoff +  6 ))
facility.$(( ID )).warehouse = $(( WID ))
facility.$(( ID )).alias = AT1_out2
"
ID=$((ID+1))
echo "
facility.$(( ID )).type = warehouseout
facility.$(( ID )).length = 2
facility.$(( ID )).width = 2
facility.$(( ID )).orientation = vertical
facility.$(( ID )).center.x = $(( $Xoff +  14 ))
facility.$(( ID )).center.y = $(( $Yoff +  6 ))
facility.$(( ID )).warehouse = $(( WID ))
facility.$(( ID )).alias = AT1_out3
"
ID=$((ID+1))
echo "
facility.$(( ID )).type = warehouseout
facility.$(( ID )).length = 2
facility.$(( ID )).width = 2
facility.$(( ID )).orientation = vertical
facility.$(( ID )).center.x = $(( $Xoff +  18 ))
facility.$(( ID )).center.y = $(( $Yoff +  6 ))
facility.$(( ID )).warehouse = $(( WID ))
facility.$(( ID )).alias = AT1_out4
"


Xoff=0
Yoff=30
echo "
#########################
# Plate W2              #
# Warehouse             #
#########################
"
WID=$((WID+1))
echo "
warehouse.$(( WID )).show = true
warehouse.$(( WID )).length = 19
warehouse.$(( WID )).width = 2
warehouse.$(( WID )).orientation = horizontal
warehouse.$(( WID )).center.x = $(( $Xoff + 1 + 9 ))
warehouse.$(( WID )).center.y = $(( $Yoff +     4 ))
warehouse.$(( WID )).block.1.stock = 0
warehouse.$(( WID )).block.2.stock = 0
warehouse.$(( WID )).block.3.stock = 0
warehouse.$(( WID )).block.4.stock = 0
warehouse.$(( WID )).block.5.stock = 0
warehouse.$(( WID )).block.6.stock = 0
warehouse.$(( WID )).block.7.stock = 0
warehouse.$(( WID )).block.8.stock = 0
warehouse.$(( WID )).block.9.stock = 0
warehouse.$(( WID )).mintime = 100
warehouse.$(( WID )).maxtime = 100
"
ID=$((ID+1))
echo "
facility.$(( ID )).type = warehouseout
facility.$(( ID )).length = 2
facility.$(( ID )).width = 2
facility.$(( ID )).orientation = vertical
facility.$(( ID )).center.x = $(( $Xoff + 2 ))
facility.$(( ID )).center.y = $(( $Yoff + 6 ))
facility.$(( ID )).warehouse = $(( WID ))
facility.$(( ID )).alias = AT2_out0
"
ID=$((ID+1))
echo "
facility.$(( ID )).type = warehouseout
facility.$(( ID )).length = 2
facility.$(( ID )).width = 2
facility.$(( ID )).orientation = vertical
facility.$(( ID )).center.x = $(( $Xoff + 6 ))
facility.$(( ID )).center.y = $(( $Yoff + 6 ))
facility.$(( ID )).warehouse = $(( WID ))
facility.$(( ID )).alias = AT2_out1
"
ID=$((ID+1))
echo "
facility.$(( ID )).type = warehouseout
facility.$(( ID )).length = 2
facility.$(( ID )).width = 2
facility.$(( ID )).orientation = vertical
facility.$(( ID )).center.x = $(( $Xoff + 10 ))
facility.$(( ID )).center.y = $(( $Yoff + 6 ))
facility.$(( ID )).warehouse = $(( WID ))
facility.$(( ID )).alias = AT2_out2
"
ID=$((ID+1))
echo "
facility.$(( ID )).type = warehouseout
facility.$(( ID )).length = 2
facility.$(( ID )).width = 2
facility.$(( ID )).orientation = vertical
facility.$(( ID )).center.x = $(( $Xoff + 14 ))
facility.$(( ID )).center.y = $(( $Yoff + 6 ))
facility.$(( ID )).warehouse = $(( WID ))
facility.$(( ID )).alias = AT2_out3
"
ID=$((ID+1))
echo "
facility.$(( ID )).type = warehouseout
facility.$(( ID )).length = 2
facility.$(( ID )).width = 2
facility.$(( ID )).orientation = vertical
facility.$(( ID )).center.x = $(( $Xoff + 18 ))
facility.$(( ID )).center.y = $(( $Yoff + 6 ))
facility.$(( ID )).warehouse = $(( WID ))
facility.$(( ID )).alias = AT2_out4
"
ID=$((ID+1))
echo "
facility.$(( ID )).type = warehouseout
facility.$(( ID )).length = 2
facility.$(( ID )).width = 2
facility.$(( ID )).orientation = vertical
facility.$(( ID )).center.x = $(( $Xoff + 2 ))
facility.$(( ID )).center.y = $(( $Yoff + 2 ))
facility.$(( ID )).warehouse = $(( WID ))
facility.$(( ID )).alias = AT2_out5
"
ID=$((ID+1))
echo "
facility.$(( ID )).type = warehousein
facility.$(( ID )).length = 2
facility.$(( ID )).width = 2
facility.$(( ID )).orientation = vertical
facility.$(( ID )).center.x = $(( $Xoff +  6 ))
facility.$(( ID )).center.y = $(( $Yoff +  2 ))
facility.$(( ID )).warehouse = $(( WID ))
facility.$(( ID )).alias = AT2_in1
"
ID=$((ID+1))
echo "
facility.$(( ID )).type = warehousein
facility.$(( ID )).length = 2
facility.$(( ID )).width = 2
facility.$(( ID )).orientation = vertical
facility.$(( ID )).center.x = $(( $Xoff +  10 ))
facility.$(( ID )).center.y = $(( $Yoff +  2 ))
facility.$(( ID )).warehouse = $(( WID ))
facility.$(( ID )).alias = AT2_in2
"
ID=$((ID+1))
echo "
facility.$(( ID )).type = warehousein
facility.$(( ID )).length = 2
facility.$(( ID )).width = 2
facility.$(( ID )).orientation = vertical
facility.$(( ID )).center.x = $(( $Xoff +  14 ))
facility.$(( ID )).center.y = $(( $Yoff +  2 ))
facility.$(( ID )).warehouse = $(( WID ))
facility.$(( ID )).alias = AT2_in3
"
ID=$((ID+1))
echo "
facility.$(( ID )).type = warehousein
facility.$(( ID )).length = 2
facility.$(( ID )).width = 2
facility.$(( ID )).orientation = vertical
facility.$(( ID )).center.x = $(( $Xoff +  18 ))
facility.$(( ID )).center.y = $(( $Yoff +  2 ))
facility.$(( ID )).warehouse = $(( WID ))
facility.$(( ID )).alias = AT2_in4
"


Xoff=2
Yoff=13
Cell=0
echo "
#########################
# Plate $Cell               #
# Serial Conveyors      #
#########################
"
ID=$((ID+1))
echo "
facility.$(( ID )).type = conveyor
facility.$(( ID )).length = 4
facility.$(( ID )).width = 2
facility.$(( ID )).orientation = vertical
facility.$(( ID )).center.x = $(( $Xoff ))
facility.$(( ID )).center.y = $(( $Yoff +   0 ))
facility.$(( ID )).alias = Cell$(( Cell ))_Ctop
"
ID=$((ID+1))
echo "
facility.$(( ID )).type = conveyor
facility.$(( ID )).length = 4
facility.$(( ID )).width = 2
facility.$(( ID )).orientation = vertical
facility.$(( ID )).center.x = $(( $Xoff ))
facility.$(( ID )).center.y = $(( $Yoff +  4 ))
facility.$(( ID )).alias = Cell$(( Cell ))_Cmid
"
ID=$((ID+1))
echo "
facility.$(( ID )).type = conveyor
facility.$(( ID )).length = 4
facility.$(( ID )).width = 2
facility.$(( ID )).orientation = vertical
facility.$(( ID )).center.x = $(( $Xoff ))
facility.$(( ID )).center.y = $(( $Yoff +  8 ))
facility.$(( ID )).alias = Cell$(( Cell ))_Cbot
"
ID=$((ID+1))
echo "
facility.$(( ID )).type = conveyor
facility.$(( ID )).length = 4
facility.$(( ID )).width = 2
facility.$(( ID )).orientation = vertical
facility.$(( ID )).center.x = $(( $Xoff ))
facility.$(( ID )).center.y = $(( $Yoff +  12 ))
facility.$(( ID )).alias = Cell$(( Cell ))_Cmid
"
ID=$((ID+1))
echo "
facility.$(( ID )).type = conveyor
facility.$(( ID )).length = 4
facility.$(( ID )).width = 2
facility.$(( ID )).orientation = vertical
facility.$(( ID )).center.x = $(( $Xoff ))
facility.$(( ID )).center.y = $(( $Yoff +  16 ))
facility.$(( ID )).alias = Cell$(( Cell ))_Cbot
"


Xoff=6
Yoff=13
Cell=1
echo "
#########################
# Plate $Cell               #
# Serial Machines       #
#########################
"
ID=$((ID+1))
echo "
facility.$(( ID )).type = machine
facility.$(( ID )).length = 4
facility.$(( ID )).width = 2
facility.$(( ID )).orientation = vertical
facility.$(( ID )).center.x = $(( $Xoff ))
facility.$(( ID )).center.y = $(( $Yoff +   0 ))
facility.$(( ID )).tool1 = 1
facility.$(( ID )).tool2 = 2
facility.$(( ID )).tool3 = 3
facility.$(( ID )).alias = Cell$(( Cell ))_Mtop
"
ID=$((ID+1))
echo "
facility.$(( ID )).type = conveyor
facility.$(( ID )).length = 4
facility.$(( ID )).width = 2
facility.$(( ID )).orientation = vertical
facility.$(( ID )).center.x = $(( $Xoff ))
facility.$(( ID )).center.y = $(( $Yoff +  4 ))
facility.$(( ID )).alias = Cell$(( Cell ))_Cmid
"
ID=$((ID+1))
echo "
facility.$(( ID )).type = machine
facility.$(( ID )).length = 4
facility.$(( ID )).width = 2
facility.$(( ID )).orientation = vertical
facility.$(( ID )).center.x = $(( $Xoff ))
facility.$(( ID )).center.y = $(( $Yoff +  8 ))
facility.$(( ID )).tool1 = 1
facility.$(( ID )).tool2 = 2
facility.$(( ID )).tool3 = 3
facility.$(( ID )).alias = Cell$(( Cell ))_Mbot
"
ID=$((ID+1))
echo "
facility.$(( ID )).type = conveyor
facility.$(( ID )).length = 4
facility.$(( ID )).width = 2
facility.$(( ID )).orientation = vertical
facility.$(( ID )).center.x = $(( $Xoff ))
facility.$(( ID )).center.y = $(( $Yoff +  12 ))
facility.$(( ID )).alias = Cell$(( Cell ))_Cmid
"
ID=$((ID+1))
echo "
facility.$(( ID )).type = machine
facility.$(( ID )).length = 4
facility.$(( ID )).width = 2
facility.$(( ID )).orientation = vertical
facility.$(( ID )).center.x = $(( $Xoff ))
facility.$(( ID )).center.y = $(( $Yoff +  16 ))
facility.$(( ID )).tool1 = 8
facility.$(( ID )).tool2 = 9
facility.$(( ID )).tool3 = 11
facility.$(( ID )).alias = Cell$(( Cell ))_Mbot
"


Xoff=10
Yoff=13
Cell=2
echo "
#########################
# Plate $Cell               #
# Serial Machines       #
#########################
"
ID=$((ID+1))
echo "
facility.$(( ID )).type = machine
facility.$(( ID )).length = 4
facility.$(( ID )).width = 2
facility.$(( ID )).orientation = vertical
facility.$(( ID )).center.x = $(( $Xoff ))
facility.$(( ID )).center.y = $(( $Yoff +   0 ))
facility.$(( ID )).tool1 = 1
facility.$(( ID )).tool2 = 2
facility.$(( ID )).tool3 = 3
facility.$(( ID )).alias = Cell$(( Cell ))_Mtop
"
ID=$((ID+1))
echo "
facility.$(( ID )).type = conveyor
facility.$(( ID )).length = 4
facility.$(( ID )).width = 2
facility.$(( ID )).orientation = vertical
facility.$(( ID )).center.x = $(( $Xoff ))
facility.$(( ID )).center.y = $(( $Yoff +  4 ))
facility.$(( ID )).alias = Cell$(( Cell ))_Cmid
"
ID=$((ID+1))
echo "
facility.$(( ID )).type = machine
facility.$(( ID )).length = 4
facility.$(( ID )).width = 2
facility.$(( ID )).orientation = vertical
facility.$(( ID )).center.x = $(( $Xoff ))
facility.$(( ID )).center.y = $(( $Yoff +  8 ))
facility.$(( ID )).tool1 = 1
facility.$(( ID )).tool2 = 2
facility.$(( ID )).tool3 = 3
facility.$(( ID )).alias = Cell$(( Cell ))_Mbot
"
ID=$((ID+1))
echo "
facility.$(( ID )).type = conveyor
facility.$(( ID )).length = 4
facility.$(( ID )).width = 2
facility.$(( ID )).orientation = vertical
facility.$(( ID )).center.x = $(( $Xoff ))
facility.$(( ID )).center.y = $(( $Yoff +  12 ))
facility.$(( ID )).alias = Cell$(( Cell ))_Cmid
"
ID=$((ID+1))
echo "
facility.$(( ID )).type = machine
facility.$(( ID )).length = 4
facility.$(( ID )).width = 2
facility.$(( ID )).orientation = vertical
facility.$(( ID )).center.x = $(( $Xoff ))
facility.$(( ID )).center.y = $(( $Yoff +  16 ))
facility.$(( ID )).tool1 = 8
facility.$(( ID )).tool2 = 9
facility.$(( ID )).tool3 = 10
facility.$(( ID )).alias = Cell$(( Cell ))_Mbot
"


Xoff=14
Yoff=13
Cell=3
echo "
#########################
# Plate $Cell               #
# Serial Machines       #
#########################
"
ID=$((ID+1))
echo "
facility.$(( ID )).type = machine
facility.$(( ID )).length = 4
facility.$(( ID )).width = 2
facility.$(( ID )).orientation = vertical
facility.$(( ID )).center.x = $(( $Xoff ))
facility.$(( ID )).center.y = $(( $Yoff +   0 ))
facility.$(( ID )).tool1 = 4
facility.$(( ID )).tool2 = 5
facility.$(( ID )).tool3 = 6
facility.$(( ID )).alias = Cell$(( Cell ))_Mtop
"
ID=$((ID+1))
echo "
facility.$(( ID )).type = conveyor
facility.$(( ID )).length = 4
facility.$(( ID )).width = 2
facility.$(( ID )).orientation = vertical
facility.$(( ID )).center.x = $(( $Xoff ))
facility.$(( ID )).center.y = $(( $Yoff +  4 ))
facility.$(( ID )).alias = Cell$(( Cell ))_Cmid
"
ID=$((ID+1))
echo "
facility.$(( ID )).type = machine
facility.$(( ID )).length = 4
facility.$(( ID )).width = 2
facility.$(( ID )).orientation = vertical
facility.$(( ID )).center.x = $(( $Xoff ))
facility.$(( ID )).center.y = $(( $Yoff +  8 ))
facility.$(( ID )).tool1 = 4
facility.$(( ID )).tool2 = 5
facility.$(( ID )).tool3 = 6
facility.$(( ID )).alias = Cell$(( Cell ))_Mbot
"
ID=$((ID+1))
echo "
facility.$(( ID )).type = conveyor
facility.$(( ID )).length = 4
facility.$(( ID )).width = 2
facility.$(( ID )).orientation = vertical
facility.$(( ID )).center.x = $(( $Xoff ))
facility.$(( ID )).center.y = $(( $Yoff +  12 ))
facility.$(( ID )).alias = Cell$(( Cell ))_Cmid
"
ID=$((ID+1))
echo "
facility.$(( ID )).type = machine
facility.$(( ID )).length = 4
facility.$(( ID )).width = 2
facility.$(( ID )).orientation = vertical
facility.$(( ID )).center.x = $(( $Xoff ))
facility.$(( ID )).center.y = $(( $Yoff +  16 ))
facility.$(( ID )).tool1 = 8
facility.$(( ID )).tool2 = 9
facility.$(( ID )).tool3 = 11
facility.$(( ID )).alias = Cell$(( Cell ))_Mbot
"


Xoff=18
Yoff=13
Cell=4
echo "
#########################
# Plate $Cell               #
# Serial Machines       #
#########################
"
ID=$((ID+1))
echo "
facility.$(( ID )).type = machine
facility.$(( ID )).length = 4
facility.$(( ID )).width = 2
facility.$(( ID )).orientation = vertical
facility.$(( ID )).center.x = $(( $Xoff ))
facility.$(( ID )).center.y = $(( $Yoff +   0 ))
facility.$(( ID )).tool1 = 4
facility.$(( ID )).tool2 = 5
facility.$(( ID )).tool3 = 6
facility.$(( ID )).alias = Cell$(( Cell ))_Mtop
"
ID=$((ID+1))
echo "
facility.$(( ID )).type = conveyor
facility.$(( ID )).length = 4
facility.$(( ID )).width = 2
facility.$(( ID )).orientation = vertical
facility.$(( ID )).center.x = $(( $Xoff ))
facility.$(( ID )).center.y = $(( $Yoff +  4 ))
facility.$(( ID )).alias = Cell$(( Cell ))_Cmid
"
ID=$((ID+1))
echo "
facility.$(( ID )).type = machine
facility.$(( ID )).length = 4
facility.$(( ID )).width = 2
facility.$(( ID )).orientation = vertical
facility.$(( ID )).center.x = $(( $Xoff ))
facility.$(( ID )).center.y = $(( $Yoff +  8 ))
facility.$(( ID )).tool1 = 4
facility.$(( ID )).tool2 = 5
facility.$(( ID )).tool3 = 6
facility.$(( ID )).alias = Cell$(( Cell ))_Mbot
"
ID=$((ID+1))
echo "
facility.$(( ID )).type = conveyor
facility.$(( ID )).length = 4
facility.$(( ID )).width = 2
facility.$(( ID )).orientation = vertical
facility.$(( ID )).center.x = $(( $Xoff ))
facility.$(( ID )).center.y = $(( $Yoff +  12 ))
facility.$(( ID )).alias = Cell$(( Cell ))_Cmid
"
ID=$((ID+1))
echo "
facility.$(( ID )).type = machine
facility.$(( ID )).length = 4
facility.$(( ID )).width = 2
facility.$(( ID )).orientation = vertical
facility.$(( ID )).center.x = $(( $Xoff ))
facility.$(( ID )).center.y = $(( $Yoff +  16 ))
facility.$(( ID )).tool1 = 8
facility.$(( ID )).tool2 = 9
facility.$(( ID )).tool3 = 10
facility.$(( ID )).alias = Cell$(( Cell ))_Mbot
"



Xoff=2
Yoff=37
Cell=0
echo "
#########################
# Plate $Cell               #
# Output Rollers        #
#########################
"
ID=$((ID+1))
echo "
facility.$(( ID )).type = roller
facility.$(( ID )).length = 1
facility.$(( ID )).width = 2
facility.$(( ID )).orientation = vertical
facility.$(( ID )).center.x = $(( $Xoff ))
facility.$(( ID )).center.y = $(( $Yoff + 0 )).5
facility.$(( ID )).direction = 1
facility.$(( ID )).sensors = 1
facility.$(( ID )).alias = Roll$((Cell))a
"
ID=$((ID+1))
echo "
facility.$(( ID )).type = roller
facility.$(( ID )).length = 1
facility.$(( ID )).width = 2
facility.$(( ID )).orientation = vertical
facility.$(( ID )).center.x = $(( $Xoff ))
facility.$(( ID )).center.y = $(( $Yoff + 1 )).5
facility.$(( ID )).direction = 1
facility.$(( ID )).sensors = 1
facility.$(( ID )).alias = Roll$((Cell))b
"
ID=$((ID+1))
echo "
facility.$(( ID )).type = roller
facility.$(( ID )).length = 1
facility.$(( ID )).width = 2
facility.$(( ID )).orientation = vertical
facility.$(( ID )).center.x = $(( $Xoff ))
facility.$(( ID )).center.y = $(( $Yoff + 2 )).5
facility.$(( ID )).direction = 1
facility.$(( ID )).sensors = 1
facility.$(( ID )).alias = Roll$((Cell))c
"
ID=$((ID+1))
echo "
facility.$(( ID )).type = roller
facility.$(( ID )).length = 1
facility.$(( ID )).width = 2
facility.$(( ID )).orientation = vertical
facility.$(( ID )).center.x = $(( $Xoff ))
facility.$(( ID )).center.y = $(( $Yoff + 3 )).5
facility.$(( ID )).direction = 1
facility.$(( ID )).sensors = 1
facility.$(( ID )).alias = Roll$((Cell))d
"
ID=$((ID+1))
echo "
facility.$(( ID )).type = roller
facility.$(( ID )).length = 1
facility.$(( ID )).width = 2
facility.$(( ID )).orientation = vertical
facility.$(( ID )).center.x = $(( $Xoff ))
facility.$(( ID )).center.y = $(( $Yoff + 4 )).5
facility.$(( ID )).direction = 1
facility.$(( ID )).sensors = 1
facility.$(( ID )).alias = Roll$((Cell))e
"
ID=$((ID+1))
echo "
facility.$(( ID )).type = conveyor
facility.$(( ID )).length = 1
facility.$(( ID )).width = 2
facility.$(( ID )).orientation = vertical
facility.$(( ID )).center.x = $(( $Xoff ))
facility.$(( ID )).center.y = $(( $Yoff + 5 )).5
facility.$(( ID )).direction = 1
facility.$(( ID )).sensors = 1
facility.$(( ID )).alias = Roll$((Cell))f
"




Xoff=6
Yoff=37
Cell=1
echo "
#########################
# Plate $Cell               #
# Output Rollers        #
#########################
"
ID=$((ID+1))
echo "
facility.$(( ID )).type = roller
facility.$(( ID )).length = 1
facility.$(( ID )).width = 2
facility.$(( ID )).orientation = vertical
facility.$(( ID )).center.x = $(( $Xoff ))
facility.$(( ID )).center.y = $(( $Yoff + 0 )).5
facility.$(( ID )).direction = 1
facility.$(( ID )).sensors = 1
facility.$(( ID )).alias = Roll$((Cell))a
"
ID=$((ID+1))
echo "
facility.$(( ID )).type = roller
facility.$(( ID )).length = 1
facility.$(( ID )).width = 2
facility.$(( ID )).orientation = vertical
facility.$(( ID )).center.x = $(( $Xoff ))
facility.$(( ID )).center.y = $(( $Yoff + 1 )).5
facility.$(( ID )).direction = 1
facility.$(( ID )).sensors = 1
facility.$(( ID )).alias = Roll$((Cell))b
"
ID=$((ID+1))
echo "
facility.$(( ID )).type = roller
facility.$(( ID )).length = 1
facility.$(( ID )).width = 2
facility.$(( ID )).orientation = vertical
facility.$(( ID )).center.x = $(( $Xoff ))
facility.$(( ID )).center.y = $(( $Yoff + 2 )).5
facility.$(( ID )).direction = 1
facility.$(( ID )).sensors = 1
facility.$(( ID )).alias = Roll$((Cell))c
"
ID=$((ID+1))
echo "
facility.$(( ID )).type = roller
facility.$(( ID )).length = 1
facility.$(( ID )).width = 2
facility.$(( ID )).orientation = vertical
facility.$(( ID )).center.x = $(( $Xoff ))
facility.$(( ID )).center.y = $(( $Yoff + 3 )).5
facility.$(( ID )).direction = 1
facility.$(( ID )).sensors = 1
facility.$(( ID )).alias = Roll$((Cell))d
"
ID=$((ID+1))
echo "
facility.$(( ID )).type = roller
facility.$(( ID )).length = 1
facility.$(( ID )).width = 2
facility.$(( ID )).orientation = vertical
facility.$(( ID )).center.x = $(( $Xoff ))
facility.$(( ID )).center.y = $(( $Yoff + 4 )).5
facility.$(( ID )).direction = 1
facility.$(( ID )).sensors = 1
facility.$(( ID )).alias = Roll$((Cell))e
"
ID=$((ID+1))
echo "
facility.$(( ID )).type = conveyor
facility.$(( ID )).length = 1
facility.$(( ID )).width = 2
facility.$(( ID )).orientation = vertical
facility.$(( ID )).center.x = $(( $Xoff ))
facility.$(( ID )).center.y = $(( $Yoff + 5 )).5
facility.$(( ID )).direction = 1
facility.$(( ID )).sensors = 1
facility.$(( ID )).alias = Roll$((Cell))f
"




Xoff=10
Yoff=37
Cell=2
echo "
#########################
# Plate $Cell               #
# Output Rollers        #
#########################
"
ID=$((ID+1))
echo "
facility.$(( ID )).type = roller
facility.$(( ID )).length = 1
facility.$(( ID )).width = 2
facility.$(( ID )).orientation = vertical
facility.$(( ID )).center.x = $(( $Xoff ))
facility.$(( ID )).center.y = $(( $Yoff + 0 )).5
facility.$(( ID )).direction = 1
facility.$(( ID )).sensors = 1
facility.$(( ID )).alias = Roll$((Cell))a
"
ID=$((ID+1))
echo "
facility.$(( ID )).type = roller
facility.$(( ID )).length = 1
facility.$(( ID )).width = 2
facility.$(( ID )).orientation = vertical
facility.$(( ID )).center.x = $(( $Xoff ))
facility.$(( ID )).center.y = $(( $Yoff + 1 )).5
facility.$(( ID )).direction = 1
facility.$(( ID )).sensors = 1
facility.$(( ID )).alias = Roll$((Cell))b
"
ID=$((ID+1))
echo "
facility.$(( ID )).type = roller
facility.$(( ID )).length = 1
facility.$(( ID )).width = 2
facility.$(( ID )).orientation = vertical
facility.$(( ID )).center.x = $(( $Xoff ))
facility.$(( ID )).center.y = $(( $Yoff + 2 )).5
facility.$(( ID )).direction = 1
facility.$(( ID )).sensors = 1
facility.$(( ID )).alias = Roll$((Cell))c
"
ID=$((ID+1))
echo "
facility.$(( ID )).type = roller
facility.$(( ID )).length = 1
facility.$(( ID )).width = 2
facility.$(( ID )).orientation = vertical
facility.$(( ID )).center.x = $(( $Xoff ))
facility.$(( ID )).center.y = $(( $Yoff + 3 )).5
facility.$(( ID )).direction = 1
facility.$(( ID )).sensors = 1
facility.$(( ID )).alias = Roll$((Cell))d
"
ID=$((ID+1))
echo "
facility.$(( ID )).type = roller
facility.$(( ID )).length = 1
facility.$(( ID )).width = 2
facility.$(( ID )).orientation = vertical
facility.$(( ID )).center.x = $(( $Xoff ))
facility.$(( ID )).center.y = $(( $Yoff + 4 )).5
facility.$(( ID )).direction = 1
facility.$(( ID )).sensors = 1
facility.$(( ID )).alias = Roll$((Cell))e
"
ID=$((ID+1))
echo "
facility.$(( ID )).type = conveyor
facility.$(( ID )).length = 1
facility.$(( ID )).width = 2
facility.$(( ID )).orientation = vertical
facility.$(( ID )).center.x = $(( $Xoff ))
facility.$(( ID )).center.y = $(( $Yoff + 5 )).5
facility.$(( ID )).direction = 1
facility.$(( ID )).sensors = 1
facility.$(( ID )).alias = Roll$((Cell))f
"




Xoff=14
Yoff=37
Cell=3
echo "
#########################
# Plate $Cell               #
# Output Rollers        #
#########################
"
ID=$((ID+1))
echo "
facility.$(( ID )).type = roller
facility.$(( ID )).length = 1
facility.$(( ID )).width = 2
facility.$(( ID )).orientation = vertical
facility.$(( ID )).center.x = $(( $Xoff ))
facility.$(( ID )).center.y = $(( $Yoff + 0 )).5
facility.$(( ID )).direction = 1
facility.$(( ID )).sensors = 1
facility.$(( ID )).alias = Roll$((Cell))a
"
ID=$((ID+1))
echo "
facility.$(( ID )).type = roller
facility.$(( ID )).length = 1
facility.$(( ID )).width = 2
facility.$(( ID )).orientation = vertical
facility.$(( ID )).center.x = $(( $Xoff ))
facility.$(( ID )).center.y = $(( $Yoff + 1 )).5
facility.$(( ID )).direction = 1
facility.$(( ID )).sensors = 1
facility.$(( ID )).alias = Roll$((Cell))b
"
ID=$((ID+1))
echo "
facility.$(( ID )).type = roller
facility.$(( ID )).length = 1
facility.$(( ID )).width = 2
facility.$(( ID )).orientation = vertical
facility.$(( ID )).center.x = $(( $Xoff ))
facility.$(( ID )).center.y = $(( $Yoff + 2 )).5
facility.$(( ID )).direction = 1
facility.$(( ID )).sensors = 1
facility.$(( ID )).alias = Roll$((Cell))c
"
ID=$((ID+1))
echo "
facility.$(( ID )).type = roller
facility.$(( ID )).length = 1
facility.$(( ID )).width = 2
facility.$(( ID )).orientation = vertical
facility.$(( ID )).center.x = $(( $Xoff ))
facility.$(( ID )).center.y = $(( $Yoff + 3 )).5
facility.$(( ID )).direction = 1
facility.$(( ID )).sensors = 1
facility.$(( ID )).alias = Roll$((Cell))d
"
ID=$((ID+1))
echo "
facility.$(( ID )).type = roller
facility.$(( ID )).length = 1
facility.$(( ID )).width = 2
facility.$(( ID )).orientation = vertical
facility.$(( ID )).center.x = $(( $Xoff ))
facility.$(( ID )).center.y = $(( $Yoff + 4 )).5
facility.$(( ID )).direction = 1
facility.$(( ID )).sensors = 1
facility.$(( ID )).alias = Roll$((Cell))e
"
ID=$((ID+1))
echo "
facility.$(( ID )).type = conveyor
facility.$(( ID )).length = 1
facility.$(( ID )).width = 2
facility.$(( ID )).orientation = vertical
facility.$(( ID )).center.x = $(( $Xoff ))
facility.$(( ID )).center.y = $(( $Yoff + 5 )).5
facility.$(( ID )).direction = 1
facility.$(( ID )).sensors = 1
facility.$(( ID )).alias = Roll$((Cell))f
"




Xoff=18
Yoff=37
Cell=4
echo "
#########################
# Plate $Cell               #
# Output Rollers        #
#########################
"
ID=$((ID+1))
echo "
facility.$(( ID )).type = roller
facility.$(( ID )).length = 1
facility.$(( ID )).width = 2
facility.$(( ID )).orientation = vertical
facility.$(( ID )).center.x = $(( $Xoff ))
facility.$(( ID )).center.y = $(( $Yoff + 0 )).5
facility.$(( ID )).direction = 1
facility.$(( ID )).sensors = 1
facility.$(( ID )).alias = Roll$((Cell))a
"
ID=$((ID+1))
echo "
facility.$(( ID )).type = roller
facility.$(( ID )).length = 1
facility.$(( ID )).width = 2
facility.$(( ID )).orientation = vertical
facility.$(( ID )).center.x = $(( $Xoff ))
facility.$(( ID )).center.y = $(( $Yoff + 1 )).5
facility.$(( ID )).direction = 1
facility.$(( ID )).sensors = 1
facility.$(( ID )).alias = Roll$((Cell))b
"
ID=$((ID+1))
echo "
facility.$(( ID )).type = roller
facility.$(( ID )).length = 1
facility.$(( ID )).width = 2
facility.$(( ID )).orientation = vertical
facility.$(( ID )).center.x = $(( $Xoff ))
facility.$(( ID )).center.y = $(( $Yoff + 2 )).5
facility.$(( ID )).direction = 1
facility.$(( ID )).sensors = 1
facility.$(( ID )).alias = Roll$((Cell))c
"
ID=$((ID+1))
echo "
facility.$(( ID )).type = roller
facility.$(( ID )).length = 1
facility.$(( ID )).width = 2
facility.$(( ID )).orientation = vertical
facility.$(( ID )).center.x = $(( $Xoff ))
facility.$(( ID )).center.y = $(( $Yoff + 3 )).5
facility.$(( ID )).direction = 1
facility.$(( ID )).sensors = 1
facility.$(( ID )).alias = Roll$((Cell))d
"
ID=$((ID+1))
echo "
facility.$(( ID )).type = roller
facility.$(( ID )).length = 1
facility.$(( ID )).width = 2
facility.$(( ID )).orientation = vertical
facility.$(( ID )).center.x = $(( $Xoff ))
facility.$(( ID )).center.y = $(( $Yoff + 4 )).5
facility.$(( ID )).direction = 1
facility.$(( ID )).sensors = 1
facility.$(( ID )).alias = Roll$((Cell))e
"
ID=$((ID+1))
echo "
facility.$(( ID )).type = conveyor
facility.$(( ID )).length = 1
facility.$(( ID )).width = 2
facility.$(( ID )).orientation = vertical
facility.$(( ID )).center.x = $(( $Xoff ))
facility.$(( ID )).center.y = $(( $Yoff + 5 )).5
facility.$(( ID )).direction = 1
facility.$(( ID )).sensors = 1
facility.$(( ID )).alias = Roll$((Cell))f
"
