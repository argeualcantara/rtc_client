from RTC_CLIENT import RtcClient

rtc_client = RtcClient()

#the project areas are necessary for almost all other methods
list_project_areas = rtc_client.getProjectAreas()

list_types = rtc_client.getProjectAreaTypes(list_project_areas)

list_statuses = rtc_client.getProjectAreaStatuses(list_types)

#lastModified is a date that you pass as a string like 'yyyy-mm-dd hh24:mi:ss'
#if it's none it'll search for workitems with identifier greater or equals to 1
lastModified = None
lastModified = '2015-02-15 15:15:15'
for project_area in list_project_areas.values():
	list_workitems = rtc_client.getProjectAreaWorkitems(project_area, lastModified)
	print ('%s -> %i' %(project_area['Title'], len(list_workitems)))
