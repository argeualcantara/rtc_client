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
		project_area_url = '%s/oslc/workitems/catalog' %(host_name)
		project_areas = self.getDocFromUrl(project_area_url)
		list_project_area = {}
		count = 0
		for pa in project_areas['oslc_disc_entry']:
			project_area = {}
			title = pa['oslc_disc_ServiceProvider']['dc_title']
			project_area_id = pa['oslc_disc_ServiceProvider']['oslc_disc_details']['rdf_resource']
			project_area_id = project_area_id[53:76]
			project_area['ProjectAreaId'] = project_area_id
			project_area['Title'] = title
			list_project_area[count] = project_area
			count += 1
		return list_project_area

	def getProjectAreaTypes(self, list_project_area):
		count = 0
		list_types = {}
		for project_area in list_project_area.values():
			id_area_projeto = project_area['ProjectAreaId']
			types_url = '%s/oslc/types/%s' %(host_name, id_area_projeto)
			types = self.getDocFromUrl(types_url, headers_oslc_2_0_global)
			types = types['oslc_ResponseInfo'][0]['rdfs_member']
			if not types is None:
				for tp in types:
					type_obj = {}
					type_obj['WorkitemTypeId'] = tp['rtc_cm_Type']['dcterms_identifier'].data
					type_obj['Title'] = tp['rtc_cm_Type']['dcterms_title']
					type_obj['ProjectArea'] = project_area
					list_types[count] = type_obj
					count += 1
		return list_types

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
			for l in statuses:
				status = {}
				status['WorkitemStatusId'] = l['rtc_cm_Status']['dcterms_identifier'].data
				status['Title'] = l['rtc_cm_Status']['dcterms_title'].data
				status['ProjectArea'] = type_obj['ProjectArea']
				status['Type'] = type_obj
				list_statuses[count] = status
				count += 1
				
		return list_statuses

	def getProjectAreaWorkitems(self, project_area, lastModified=None):
		list_workitem = collections.OrderedDict([])
		id_project_area = project_area['ProjectAreaId']
		conditions = '?oslc_cm.properties=*&oslc.query=dc:identifier>1&oslc_cm.pageSize=100&_startIndex=0'
		if lastModified is not None:
			conditions = '?oslc_cm.properties=*&oslc_cm.query=dc:modified>\"%s.000Z\"&oslc_cm.pageSize=100&_startIndex=0' % (lastModified.replace(' ', 'T'))
		workitem_url = '%s/oslc/contexts/%s/workitems/%s' %(host_name, id_project_area, conditions)
		workitems = self.getDocFromUrl(workitem_url)
		if workitems['oslc_cm_totalCount'] is not None and workitems['oslc_cm_totalCount'] != '0':
			while workitems is not None:
				if workitems['oslc_cm_ChangeRequest'] is not None:
					for wi in workitems['oslc_cm_ChangeRequest']:
						workitem = self.getWorkitem(wi)

						workitem['ParentWorkitemId'] = ''
						if wi['rtc_cm_com_ibm_team_workitem_linktype_parentworkitem_parent'] is not None:
							wi_parent_url = wi['rtc_cm_com_ibm_team_workitem_linktype_parentworkitem_parent']['oslc_cm_collref']
							parent_workitem = self.getDocFromUrl(wi_parent_url)
							parent_workitem = parent_workitem[0]
							if parent_workitem['oslc_cm_totalCount'] != '0':
								p_wi = parent_workitem['oslc_cm_ChangeRequest'][0]
								workitem['ParentWorkitemId'] = p_wi['dc_identifier']
								parent = self.getWorkitem(p_wi)
								list_workitem['%s' %(parent['WorkitemId'])] = parent

						list_workitem['%s' %(workitem['WorkitemId'])] = workitem
					if workitems['oslc_cm_next'] is not None:
						workitems = self.getDocFromUrl(workitems['oslc_cm_next'])
						workitems = workitems[0]
					else:
						workitems = None

		return list_workitem

	def getWorkitem(self, wi):
		workitem = {}
		workitem['WorkitemId'] = wi['dc_identifier']
		workitem['Modified'] = wi['dc_modified']
		workitem['PidProjectArea'] = wi['rtc_cm_contextId']
		workitem['Estimate'] = wi['rtc_cm_estimate']
		workitem['CorrectedEstimate'] = wi['rtc_cm_correctedEstimate']
		workitem['TimeSpent'] = wi['rtc_cm_timeSpent']
		workitem['Title'] = u'%s' % (wi['dc_title'])
		workitem['Resolved'] = wi['rtc_cm_resolved']

		owner = wi['rtc_cm_ownedBy']['rdf_resource']
		if owner is not None:
			owner = owner[ owner.rfind('/')+1: ]
			if owner != 'unassigned':
				workitem['Owner'] = owner[ 3: ]
		status = wi['rtc_cm_state']['rdf_resource']
		workitem['WorkitemStatusPid'] = status[ status.rfind('/')+1: ]
		wi_type = wi['dc_type']['rdf_resource']
		workitem['WorkitemTypePid'] = wi_type[ wi_type.rfind('/')+1: ]


		list_apontamentos = {}
		workitem['TimeSheet'] = list_apontamentos
		if wi['rtc_cm_timeSheet'] is not None:
			wi_apontamentos_url = '%s/rtc_cm:entry' %(wi['rtc_cm_timeSheet']['rdf_resource'])
			apontamentos = self.getDocFromUrl(wi_apontamentos_url)
			apontamentos = apontamentos[0]
			count = 0
			if apontamentos['oslc_cm_totalCount'] != '0':
				for ap in apontamentos['rtc_cm_TimeSheetEntry']:
					apontamento = {}
					apontamento['WorkitemId'] = wi['WorkitemId']
					apontamento['StartDate'] = ap['rtc_cm_startDate']
					apontamento['TimeSpent'] = ap['rtc_cm_timeSpent']
					list_apontamentos[count] = apontamento
					count += 1
				workitem['TimeSheet'] = list_apontamentos
		return workitem
