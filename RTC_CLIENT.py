#coding: utf-8
import re
import requests
import collections
import xml2obj
from config import host_name, auth_url, auth_data

headers_global = {'Accept': 'text/xml', 'OSLC-Core-Version': '1.0'}
headers_oslc_2_0_global = {'Accept': 'text/xml', 'OSLC-Core-Version': '2.0'}

class RtcClient(object):
	session = None
	def __init__(self):
		self.session = requests.session()
		self.session.get('%s/authenticated/identity' %(host_name), headers=headers_global)
		self.session.post(auth_url, auth_data)

	def getDocFromUrl(self, url, headers=headers_global):
		resp = self.session.get(url, headers=headers)
		doc = resp.content
		obj = xml2obj.xml2obj(doc)
		parsedObject = list(obj)
		return parsedObject[0]

	def getProjectAreas(self):
		list_project_area = {}
		project_areas = self.getDocFromUrl('%s/oslc/workitems/catalog' %(host_name))
		count = 0
		for project_area_raw in project_areas['oslc_disc_entry']:
			list_project_area[count] = self.__getProjectArea(project_area_raw)
			count += 1
		return list_project_area

	def __getProjectArea(self, project_area_raw):
		project_area = {}
		title = project_area_raw['oslc_disc_ServiceProvider']['dc_title']
		project_area_id = project_area_raw['oslc_disc_ServiceProvider']['oslc_disc_details']['rdf_resource']
		project_area_id = project_area_id[53:76]
		project_area['ProjectAreaId'] = project_area_id
		project_area['Title'] = title
		return project_area

	def getProjectAreaTypes(self, list_project_area):
		count = 0
		list_types = {}
		for project_area in list_project_area.values():
			types = self.getDocFromUrl('%s/oslc/types/%s' %(host_name, project_area['ProjectAreaId']), headers_oslc_2_0_global)
			types = types['oslc_ResponseInfo'][0]['rdfs_member']
			if types is not None:
				for type_raw in types:
					list_types[count] = self.__getType(type_raw, project_area)
					count += 1
		return list_types

	def __getType(self, type_raw, project_area):
		type_obj = {}
		type_obj['WorkitemTypeId'] = type_raw['rtc_cm_Type']['dcterms_identifier'].data
		type_obj['Title'] = type_raw['rtc_cm_Type']['dcterms_title']
		type_obj['ProjectArea'] = project_area
		return type_obj

	def getProjectAreaStatuses(self, list_types):
		count = 0
		list_statuses = {}
		for type_obj in list_types.values():
			types_url = '%s/oslc/context/%s/shapes/workitems/%s/property/internalState/allowedValues' % (host_name, type_obj['ProjectArea']['ProjectAreaId'], type_obj['WorkitemTypeId'])
			stat_type_url = self.getDocFromUrl(types_url, headers_oslc_2_0_global)
			stat_type_url = stat_type_url['oslc_AllowedValues'][0]['oslc_allowedValue'][0]['rdf_resource']
			stat_type_url = stat_type_url[:stat_type_url.rfind('/')]
			statuses = self.getDocFromUrl(stat_type_url, headers_oslc_2_0_global)
			statuses = statuses['oslc_ResponseInfo'][0]['rdfs_member']
			for status_raw in statuses:
				list_statuses[count] = self.__getStatus(status_raw, type_obj)
				count += 1
		return list_statuses

	def __getStatus(self, status_raw, type_obj):
		status = {}
		status['WorkitemStatusId'] = status_raw['rtc_cm_Status']['dcterms_identifier'].data
		status['Title'] = status_raw['rtc_cm_Status']['dcterms_title'].data
		status['ProjectArea'] = type_obj['ProjectArea']
		status['Type'] = type_obj
		return status

	def getProjectAreaWorkitems(self, project_area, lastModified=None):
		list_workitem = collections.OrderedDict([])
		conditions = '?oslc_cm.properties=*&oslc.query=dc:identifier>1&oslc_cm.pageSize=100&_startIndex=0'
		if lastModified is not None:
			conditions = '?oslc_cm.properties=*&oslc_cm.query=dc:modified>\"%s.000Z\"&oslc_cm.pageSize=100&_startIndex=0' % (lastModified.replace(' ', 'T'))
		workitems = self.getDocFromUrl('%s/oslc/contexts/%s/workitems/%s' %(host_name, project_area['ProjectAreaId'], conditions))
		if workitems['oslc_cm_totalCount'] is not None and workitems['oslc_cm_totalCount'] != '0':
			while workitems is not None:
				if workitems['oslc_cm_ChangeRequest'] is not None:
					for wi in workitems['oslc_cm_ChangeRequest']:
						workitem = self.__getWorkitem(wi)
						self.__setParentWorkitem(list_workitem, wi, workitem)
						list_workitem['%s' %(workitem['WorkitemId'])] = workitem
					if workitems['oslc_cm_next'] is not None:
						workitems = self.getDocFromUrl(workitems['oslc_cm_next'])
						workitems = workitems[0]
					else:
						workitems = None
		return list_workitem

	def __setParentWorkitem(self, list_workitem, wi, workitem):
		if wi['rtc_cm_com_ibm_team_workitem_linktype_parentworkitem_parent'] is not None:
			wi_parent_url = wi['rtc_cm_com_ibm_team_workitem_linktype_parentworkitem_parent']['oslc_cm_collref']
			parent_workitem = self.getDocFromUrl(wi_parent_url)
			parent_workitem = parent_workitem[0]
			if parent_workitem['oslc_cm_totalCount'] != '0':
				p_wi = parent_workitem['oslc_cm_ChangeRequest'][0]
				workitem['ParentWorkitemId'] = p_wi['dc_identifier']
				parent = self.__getWorkitem(p_wi)
				if p_wi['rtc_cm_com_ibm_team_workitem_linktype_parentworkitem_parent'] is not None:
					self.__setParentWorkitem(list_workitem, p_wi, parent)
				list_workitem['%s' %(parent['WorkitemId'])] = parent

	def __getWorkitem(self, wi):
		workitem = {}
		workitem['WorkitemId'] = wi['dc_identifier']
		workitem['Modified'] = wi['dc_modified']
		workitem['PidProjectArea'] = wi['rtc_cm_contextId']
		workitem['Estimate'] = wi['rtc_cm_estimate']
		workitem['CorrectedEstimate'] = wi['rtc_cm_correctedEstimate']
		workitem['TimeSpent'] = wi['rtc_cm_timeSpent']
		workitem['Title'] = u'%s' % (wi['dc_title'])
		workitem['Resolved'] = wi['rtc_cm_resolved']
		workitem['ParentWorkitemId'] = ''
		owner = wi['rtc_cm_ownedBy']
		if owner is not None:
			owner = owner['rdf_resource']
			owner = owner[ owner.rfind('/')+1: ]
			if owner != 'unassigned':
				workitem['Owner'] = owner[ 3: ]

		status = wi['rtc_cm_state']
		if status is not None:
			status = status['rdf_resource']
			workitem['WorkitemStatusPid'] = status[ status.rfind('/')+1: ]

		wi_type = wi['dc_type']
		if wi_type is not None:
			wi_type = wi_type['rdf_resource']
			workitem['WorkitemTypePid'] = wi_type[ wi_type.rfind('/')+1: ]

		workitem['TimeSheet'] = self.__getTimeSheetList(wi)
		return workitem

	def __getTimeSheetList(self, wi):
		list_timesheet = {}
		if wi['rtc_cm_timeSheet'] is not None:
			wi_timesheet_entry_url = '%s/rtc_cm:entry' %(wi['rtc_cm_timeSheet']['rdf_resource'])
			timesheet = self.getDocFromUrl(wi_timesheet_entry_url)
			timesheet = timesheet[0]
			count = 0
			if timesheet['oslc_cm_totalCount'] != '0':
				for entry_raw in timesheet['rtc_cm_TimeSheetEntry']:
					list_timesheet[count] = self.__getTimeSheetEntry(entry_raw, wi['WorkitemId'])
					count += 1
		return list_timesheet

	def __getTimeSheetEntry(self, entry_raw, workitemId):
		entry = {}
		entry['WorkitemId'] = workitemId
		entry['StartDate'] = entry_raw['rtc_cm_startDate']
		entry['TimeSpent'] = entry_raw['rtc_cm_timeSpent']
		return entry
