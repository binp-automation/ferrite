#!../../bin/linux-x86_64/PSC

#- You may have to change PSC to something else
#- everywhere it appears in this file

< envPaths

cd "${TOP}"

## Register all support components
dbLoadDatabase("dbd/PSC.dbd",0,0)
PSC_registerRecordDeviceDriver(pdbbase) 

## Load record instances
dbLoadRecords("db/devPSC.db")

cd "${TOP}/iocBoot/${IOC}"
iocInit()

## Start any sequence programs
#seq sncPSC
